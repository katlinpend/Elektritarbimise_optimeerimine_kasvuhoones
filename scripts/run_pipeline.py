"""ETL pipeline runner (temperature + price scope).

Loeb aktiivsed asukohad dimensioonitabelist, pärib Open-Meteo API-st
tunnipõhise välistemperatuuri ja Elering API-st tunnihinna, salvestab andmed
staging kihti, käivitab transformid ja kvaliteeditestid.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import requests


SCRIPT_DIR = Path(__file__).resolve().parent
DIMENSIONS_SQL = SCRIPT_DIR / "00_seed_dimensions.sql"
TRANSFORM_SQL = SCRIPT_DIR / "01_transform.sql"
QUALITY_SQL = SCRIPT_DIR / "02_quality_tests.sql"


class UserFacingError(RuntimeError):
    """Viga, mille sõnum sobib otse õppijale näitamiseks."""


def log(message: str) -> None:
    print(message, flush=True)


def get_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def get_connection():
    return psycopg2.connect(
        host=get_env("DB_HOST", "db"),
        port=get_env("DB_PORT", "5432"),
        user=get_env("DB_USER", "praktikum"),
        password=get_env("DB_PASSWORD", "praktikum"),
        dbname=get_env("DB_NAME", "praktikum"),
    )


def get_forecast_days() -> int:
    value = get_env("FORECAST_DAYS", "2")
    try:
        days = int(value)
    except ValueError as exc:
        raise UserFacingError("FORECAST_DAYS peab olema täisarv.") from exc

    if days < 1 or days > 16:
        raise UserFacingError("FORECAST_DAYS peab jääma vahemikku 1 kuni 16.")

    return days


def seed_dimensions(conn) -> None:
    execute_sql_file(conn, DIMENSIONS_SQL)


def load_active_locations(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                location_id,
                location_name,
                latitude,
                longitude
            FROM mart.dim_location
            WHERE is_active
            ORDER BY display_order, location_name
            """
        )
        rows = cur.fetchall()

    if not rows:
        raise UserFacingError("Asukohtade dimensioonis ei ole ühtegi aktiivset rida.")

    return [
        {
            "location_id": location_id,
            "location_name": location_name,
            "latitude": float(latitude),
            "longitude": float(longitude),
        }
        for location_id, location_name, latitude, longitude in rows
    ]


def insert_pipeline_run(conn, *, run_id: uuid.UUID, fetched_at: datetime, forecast_days: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO staging.pipeline_runs (
                run_id,
                fetched_at,
                source_name,
                forecast_days,
                status,
                message
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                str(run_id),
                fetched_at,
                "Open-Meteo + Elering NPS API",
                forecast_days,
                "running",
                "Laadimine algas.",
            ),
        )
    conn.commit()


def update_pipeline_run(conn, *, run_id: uuid.UUID, status: str, message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE staging.pipeline_runs
            SET status = %s,
                message = %s
            WHERE run_id = %s
            """,
            (status, message, str(run_id)),
        )
    conn.commit()


def fetch_forecast(location: dict, *, forecast_days: int) -> tuple[str, dict]:
    source_api_url = get_env("SOURCE_API_URL", "https://api.open-meteo.com/v1/forecast")
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "hourly": "temperature_2m",
        "timezone": "Europe/Tallinn",
        "forecast_days": forecast_days,
    }

    last_exc = None
    for attempt in range(1, 4):
        try:
            response = requests.get(source_api_url, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            return response.url, payload
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(2 * attempt)

    raise UserFacingError(
        f"Open-Meteo päring ebaõnnestus asukoha {location['location_name']} jaoks: {last_exc}"
    )


def fetch_elering_prices(*, start_utc: datetime, end_utc: datetime) -> dict[datetime, float]:
    url = get_env("ELERING_API_URL", "https://dashboard.elering.ee/api/nps/price")
    params = {
        "start": start_utc.isoformat(),
        "end": end_utc.isoformat(),
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise UserFacingError(f"Elering päring ebaõnnestus: {exc}") from exc
    except ValueError as exc:
        raise UserFacingError("Elering vastus ei olnud loetav JSON.") from exc

    price_map: dict[datetime, float] = {}
    for row in payload.get("data", {}).get("ee", []):
        ts = row.get("timestamp")
        price = row.get("price")
        if ts is None or price is None:
            continue
        dt_utc = datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)
        price_map[dt_utc] = float(price)

    return price_map


def validate_hourly_payload(payload: dict, *, location_name: str) -> dict:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise UserFacingError(f"Asukoha {location_name} vastuses puudub `hourly` plokk.")

    required_keys = ["time", "temperature_2m"]
    missing = [key for key in required_keys if key not in hourly]
    if missing:
        joined = ", ".join(missing)
        raise UserFacingError(f"Asukoha {location_name} vastuses puuduvad väljad: {joined}.")

    row_count = len(hourly["time"])
    for key in required_keys:
        if len(hourly[key]) != row_count:
            raise UserFacingError(
                f"Asukoha {location_name} vastuses on välja `{key}` pikkus teistest erinev."
            )

    return hourly


def load_location_rows(
    conn,
    *,
    run_id: uuid.UUID,
    fetched_at: datetime,
    location: dict,
    source_url: str,
    hourly: dict,
    price_map: dict[datetime, float],
) -> int:
    rows_loaded = 0

    with conn.cursor() as cur:
        for index, time_value in enumerate(hourly["time"]):
            forecast_time = datetime.fromisoformat(time_value)
            forecast_time_utc = forecast_time.astimezone(timezone.utc).replace(tzinfo=None)
            price = price_map.get(forecast_time_utc)

            cur.execute(
                """
                INSERT INTO staging.weather_hourly_raw (
                    run_id,
                    location_id,
                    location_name,
                    latitude,
                    longitude,
                    forecast_time,
                    temperature_c,
                    price_eur_mwh,
                    fetched_at,
                    source_url
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id, location_id, forecast_time) DO UPDATE SET
                    temperature_c = EXCLUDED.temperature_c,
                    price_eur_mwh = EXCLUDED.price_eur_mwh,
                    fetched_at = EXCLUDED.fetched_at,
                    source_url = EXCLUDED.source_url
                """,
                (
                    str(run_id),
                    location["location_id"],
                    location["location_name"],
                    location["latitude"],
                    location["longitude"],
                    forecast_time.replace(tzinfo=None),
                    hourly["temperature_2m"][index],
                    price,
                    fetched_at,
                    source_url,
                ),
            )
            rows_loaded += 1

    conn.commit()
    return rows_loaded


def ingest() -> uuid.UUID:
    forecast_days = get_forecast_days()
    run_id = uuid.uuid4()
    fetched_at = datetime.now(timezone.utc)

    start_utc = fetched_at.replace(hour=0, minute=0, second=0, microsecond=0)
    end_utc = start_utc + timedelta(days=forecast_days)

    conn = get_connection()
    try:
        seed_dimensions(conn)
        locations = load_active_locations(conn)
        insert_pipeline_run(
            conn,
            run_id=run_id,
            fetched_at=fetched_at,
            forecast_days=forecast_days,
        )

        price_map = fetch_elering_prices(start_utc=start_utc, end_utc=end_utc)
        log(f"Eleringi hinnapunkte: {len(price_map)}")

        total_rows = 0
        missing_price_rows = 0

        for location in locations:
            log(f"Pärin ilmaandmeid: {location['location_name']}.")
            source_url, payload = fetch_forecast(location, forecast_days=forecast_days)
            hourly = validate_hourly_payload(payload, location_name=location["location_name"])

            for t in hourly["time"]:
                dt = datetime.fromisoformat(t).astimezone(timezone.utc).replace(tzinfo=None)
                if dt not in price_map:
                    missing_price_rows += 1

            rows_loaded = load_location_rows(
                conn,
                run_id=run_id,
                fetched_at=fetched_at,
                location=location,
                source_url=source_url,
                hourly=hourly,
                price_map=price_map,
            )
            total_rows += rows_loaded
            log(f"Laadisin {location['location_name']} kohta {rows_loaded} tunnirida.")

        update_pipeline_run(
            conn,
            run_id=run_id,
            status="success",
            message=(
                f"Laadimine õnnestus. Asukohti: {len(locations)}. "
                f"Ridu kokku: {total_rows}. Hinnata ridu: {missing_price_rows}."
            ),
        )
        log(f"Andmete vastuvõtt valmis. Käivituse ID: {run_id}.")
        return run_id
    except Exception as exc:
        conn.rollback()
        update_pipeline_run(conn, run_id=run_id, status="error", message=str(exc))
        raise
    finally:
        conn.close()


def execute_sql_file(conn, path: Path) -> None:
    log(f"Käivitan SQL-faili {path.name}.")
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def fetch_value(conn, query: str):
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchone()[0]


def transform() -> None:
    conn = get_connection()
    try:
        seed_dimensions(conn)
        execute_sql_file(conn, TRANSFORM_SQL)
        daily_rows = fetch_value(conn, "SELECT COUNT(*) FROM mart.daily_weather_summary;")
        latest_rows = fetch_value(conn, "SELECT COUNT(*) FROM mart.latest_daily_weather_summary;")
        log(f"Transformatsioon valmis. Päevaseid koondridu kokku: {daily_rows}.")
        log(f"Viimase laadimise päevaseid koondridu: {latest_rows}.")
    finally:
        conn.close()


def run_quality_tests() -> None:
    conn = get_connection()
    try:
        execute_sql_file(conn, QUALITY_SQL)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT test_name, status, failed_rows, message
                FROM quality.test_results
                ORDER BY test_name
                """
            )
            results = cur.fetchall()

        log("Andmekvaliteedi testid:")
        for test_name, status, failed_rows, message in results:
            log(f"- {test_name}: {status} ({failed_rows} vigast rida) - {message}")

        failed = [row for row in results if row[1] == "failed"]
        if failed:
            raise UserFacingError("Vähemalt üks andmekvaliteedi test ebaõnnestus.")
    finally:
        conn.close()


def print_query(conn, title: str, query: str) -> None:
    print()
    print(title)
    print("-" * len(title))
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]

    if not rows:
        print("Ridu ei ole.")
        return

    print(" | ".join(columns))
    for row in rows:
        print(" | ".join("" if value is None else str(value) for value in row))


def check_results() -> None:
    conn = get_connection()
    try:
        print_query(
            conn,
            "Viimased laadimised",
            """
            SELECT run_id, fetched_at, status, message
            FROM staging.pipeline_runs
            ORDER BY fetched_at DESC
            LIMIT 5
            """,
        )
        print_query(
            conn,
            "Aktiivsed asukohad dimensioonis",
            """
            SELECT location_id, location_name, county, latitude, longitude
            FROM mart.dim_location
            WHERE is_active
            ORDER BY display_order, location_name
            """,
        )
        
        print_query(
            conn,
            "Andmekvaliteedi testid",
            """
            SELECT test_name, status, failed_rows
            FROM quality.test_results
            ORDER BY test_name
            """,
        )
    finally:
        conn.close()


def reset_data() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE TABLE
                    staging.weather_hourly_raw,
                    staging.pipeline_runs,
                    mart.outdoor_activity_windows,
                    mart.hourly_weather_score,
                    mart.daily_weather_summary,
                    mart.fact_weather_forecast,
                    quality.test_results
                CASCADE
                """
            )
        conn.commit()
        seed_dimensions(conn)
        log("Andmetabelid on tühjendatud.")
    finally:
        conn.close()


def run_all() -> None:
    ingest()
    transform()
    run_quality_tests()
    log("Kogu töövoog õnnestus.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kasvuhoone energia ETL töövoog.")
    parser.add_argument(
        "command",
        choices=["ingest", "transform", "test", "check", "reset", "run-all"],
        help="Töövoo samm, mida käivitada.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "ingest":
            ingest()
        elif args.command == "transform":
            transform()
        elif args.command == "test":
            run_quality_tests()
        elif args.command == "check":
            check_results()
        elif args.command == "reset":
            reset_data()
        elif args.command == "run-all":
            run_all()
        return 0
    except UserFacingError as exc:
        print(f"Viga: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())