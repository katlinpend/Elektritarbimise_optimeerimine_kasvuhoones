"""Elering NPS hinna allalaadimine ja salvestus CSV/JSON faili.

Skript on mõeldud ingest-etapiks (toorandmed), mitte analüütikaks.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import URLError

from config import compute_window, load_settings

# Eleringu NPS API endpoint.
ELERING_URL = "https://dashboard.elering.ee/api/nps/price"


def _get_json(url: str, params: dict) -> dict:
    """Tee GET päring ja tagasta vastus JSON dictina.

    Args:
        url: API endpoint
        params: query-parameterid
    """
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"

    # urlopen viskab URLError, kui võrguühendus/API pole saadaval.
    with urllib.request.urlopen(full_url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_elering_prices(start_iso: str, end_iso: str) -> dict:
    """Lae etteantud ajavahemiku Eleringu hinnad."""
    return _get_json(ELERING_URL, {"start": start_iso, "end": end_iso})


def write_outputs(payload: dict, output_dir: Path) -> tuple[Path, Path]:
    """Kirjuta toorvastus JSON-i ja lihtsustatud tabel CSV-sse."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "elering_prices_raw.json"
    csv_path = output_dir / "elering_prices_raw.csv"

    # Täisvastus säilib JSON-failis auditiks/debugimiseks.
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Eesti hinnaseeria asub võtmes data.ee
    rows = payload.get("data", {}).get("ee", [])
    lines = ["timestamp,price_eur_mwh"]
    for row in rows:
        lines.append(f"{row.get('timestamp')},{row.get('price')}")

    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, csv_path


def main() -> None:
    """Ingest-run: arvuta ajavahemik, küsi API, salvesta failid."""
    settings = load_settings()
    start, end = compute_window(settings.lookback_hours)
    payload = fetch_elering_prices(start.isoformat(), end.isoformat())
    json_path, csv_path = write_outputs(payload, Path(settings.output_dir))
    print(f"[OK] Elering JSON: {json_path}")
    print(f"[OK] Elering CSV : {csv_path}")


if __name__ == "__main__":
    try:
        main()
    except URLError as exc:
        print(f"[VIGA] API päring ebaõnnestus: {exc}")
        raise
