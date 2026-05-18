#!/usr/bin/env bash
# Käivitab mõlemad ingest-skriptid järjest.
# Sobib cron job'i commandiks.
set -euo pipefail

python3 scripts/ingest_elering.py
python3 scripts/ingest_open_meteo.py

echo "[OK] Mõlemad ingest-skriptid lõpetasid edukalt."