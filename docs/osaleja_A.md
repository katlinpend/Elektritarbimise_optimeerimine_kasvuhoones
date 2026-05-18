# Osaleja A töö: andmete sissevõtt (Open-Meteo + Elering)

See on baastaseme ingest-osa, mis järgib näidisprojekti loogikat: kaks ajas muutuvat API-allikat, korduvkäivitatav skript ja toorandmete salvestus failidesse.

## Eesmärk
Tuua tunnipõhised andmed kahest allikast:
1. Elering NPS elektrihind (`/api/nps/price`)
2. Open-Meteo forecast (välistemperatuur + päikesekiirgus)

## Failid
- `scripts/config.py` – ühised seadistused ja ajavahemik
- `scripts/ingest_elering.py` – elektrihinna ingest
- `scripts/ingest_open_meteo.py` – ilma ingest
- `scripts/run_ingest.sh` – mõlema skripti käivitus
- `.env.example` – seadistuse näidis
- `data/raw/*` – väljund JSON/CSV kujul

## Käivitus
```bash
cp .env.example .env
set -a && source .env && set +a
bash scripts/run_ingest.sh
```

## Väljundfailid
- `data/raw/elering_prices_raw.json`
- `data/raw/elering_prices_raw.csv`
- `data/raw/open_meteo_raw.json`
- `data/raw/open_meteo_raw.csv`

## Märkused
- Skriptid kasutavad Python standardteeki (`urllib`), et vältida sõltuvuste probleeme.
- Kui API pole võrgupiirangute tõttu kättesaadav, skript lõpetab veateatega.

## Cron ajastus
Näidis-cron on failis `scripts/cron_example.txt`.
Soovitus: käivita ingest iga tunni alguses, logi väljund `logs/ingest.log` faili.