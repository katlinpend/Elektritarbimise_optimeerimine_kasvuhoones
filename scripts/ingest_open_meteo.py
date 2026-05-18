"""Open-Meteo Forecast API allalaadimine ja salvestus CSV/JSON faili.

Skript toob tunnipõhise välistemperatuuri ja päikesekiirguse.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import URLError

from config import load_settings

# Open-Meteo forecast endpoint.
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def _get_json(url: str, params: dict) -> dict:
    """Tee GET päring ja tagasta JSON dict."""
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    with urllib.request.urlopen(full_url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_weather(lat: float, lon: float, tz_name: str) -> dict:
    """Lae järgmise 2 päeva tunniprognoos etteantud koordinaatidele."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,shortwave_radiation",
        "forecast_days": 2,
        "timezone": tz_name,
    }
    return _get_json(OPEN_METEO_URL, params)


def write_outputs(payload: dict, output_dir: Path) -> tuple[Path, Path]:
    """Kirjuta API vastus JSON ja CSV kujule."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "open_meteo_raw.json"
    csv_path = output_dir / "open_meteo_raw.csv"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    temp = hourly.get("temperature_2m", [])
    rad = hourly.get("shortwave_radiation", [])

    lines = ["time,temperature_2m,shortwave_radiation"]
    for t, tp, sr in zip(times, temp, rad):
        lines.append(f"{t},{tp},{sr}")

    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, csv_path


def main() -> None:
    """Ingest-run: loe settingud, lae API andmed, salvesta failidesse."""
    settings = load_settings()
    payload = fetch_weather(settings.latitude, settings.longitude, settings.timezone_name)
    json_path, csv_path = write_outputs(payload, Path(settings.output_dir))
    print(f"[OK] Open-Meteo JSON: {json_path}")
    print(f"[OK] Open-Meteo CSV : {csv_path}")


if __name__ == "__main__":
    try:
        main()
    except URLError as exc:
        print(f"[VIGA] API päring ebaõnnestus: {exc}")
        raise