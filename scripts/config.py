"""Ühine konfiguratsioon ingest-skriptidele.

Milleks see fail vajalik on?
- Üks koht, kust kõik ingest-skriptid loevad seaded.
- Väldib koodi dubleerimist eri skriptides.
- Teeb käivituse mugavaks: muudad .env faili, mitte Python koodi.

Näidis andmevoost ("kuidas väärtus liigub"):
1) `.env` sisaldab `LOOKBACK_HOURS=48`
2) `load_settings()` loeb selle ja teeb `settings.lookback_hours = 48`
3) `compute_window(48)` arvutab `start` ja `end` ajad
4) ingest skript kasutab neid API päringus (`start`, `end` query param)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class Settings:
    """Ingest-skriptide runtime seaded ühes objektis.

    Atribuudid:
        latitude: Open-Meteo laiuskraad
        longitude: Open-Meteo pikkuskraad
        timezone_name: ajavöönd (nt Europe/Tallinn)
        lookback_hours: mitu tundi ajas tagasi Eleringu hindasid küsida
        output_dir: kaust, kuhu kirjutatakse raw JSON/CSV failid
    """

    latitude: float
    longitude: float
    timezone_name: str
    lookback_hours: int
    output_dir: str


def _to_float(value: str, default: float) -> float:
    """Turvaline teisendus floatiks.

    Kui `.env` väärtus on puudu või vigane, tagastab `default`.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: str, default: int) -> int:
    """Turvaline teisendus int-iks.

    Kui `.env` väärtus on puudu või vigane, tagastab `default`.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_settings() -> Settings:
    """Loe seaded keskkonnamuutujatest ja tagasta `Settings` objekt.

    Vaikeväärtused:
    - asukoht: Tartu
    - timezone: Europe/Tallinn
    - lookback: 48 h
    - output dir: data/raw
    """
    return Settings(
        latitude=_to_float(os.getenv("OPEN_METEO_LAT", "58.3776"), 58.3776),
        longitude=_to_float(os.getenv("OPEN_METEO_LON", "26.7290"), 26.7290),
        timezone_name=os.getenv("OPEN_METEO_TIMEZONE", "Europe/Tallinn"),
        lookback_hours=_to_int(os.getenv("LOOKBACK_HOURS", "48"), 48),
        output_dir=os.getenv("RAW_OUTPUT_DIR", "data/raw"),
    )


def compute_window(hours: int) -> tuple[datetime, datetime]:
    """Arvuta ingest-akna algus ja lõpp UTC ajas.

    Näide:
        hours=48 -> start = (praegune UTC täistund - 48h),
                    end   = praegune UTC täistund.

    Miks täistund?
    - Eleringu NPS hind on tunnipõhine; ümardame minutid/sekundid nulli,
      et päringu aken klapiks tunniandmetega.
    """
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours)
    return start, end