<<<<<<< ours
# Kasvuhoone elektritarbimise optimeerimine
=======
# Elektritarbimise optimeerimine kasvuhoones
>>>>>>> theirs

## Äriküsimus
Millistel tundidel tasub kasvuhoones kasutada elektrit nõudvaid seadmeid (küte, ventilatsioon), et vähendada elektrikulu börsihinna tingimustes, arvestades välistemperatuuri?

<<<<<<< ours
## Lihtsustusmudel
- `hinnanguline_sisetemp = välistemp + 5°C`
- `< 12°C` → küte vajalik
- `> 28°C` → ventilatsioon vajalik
- muidu sobiv

Mudelit kasutatakse demonstratsiooniks.

## Andmeallikad
- Open-Meteo Forecast API
- Elering NPS API (`/api/nps/price`)

## Miks FORECAST_DAYS=2?
Elering day-ahead hinnad on otsustamiseks peamiselt tänase ja homse kohta.  
Seega ei ole 7 päeva ette forecast hinnaga hästi võrreldav.

## Käivitamine
```bash
cp .env.example .env
docker compose up -d --build
docker compose exec pipeline python scripts/run_pipeline.py run-all
docker compose exec pipeline python scripts/run_pipeline.py check
=======
## Projekti allikas ja töörepo
- Kursuse juhised ja näidismaterjalid pärinevad repost: `https://github.com/KristoR/ut-andmeinseneeria-2026`.
- Aktiivne töö käib selles repos: `https://github.com/sirja-hass/Elektritarbimise_optimeerimine_kasvuhoones`.

See projekt on tehtud kursuse **UT andmeinseneeria 2026** projektitöö nõuete järgi ning katab otsast-lõpuni andmetöövoo:
1. andmete sissevõtt,
2. transformatsioon,
3. andmekvaliteedi testid,
4. dashboard.

Meie lihtsustus: kasvuhoone sisetemperatuuri sensorit ei kasutata.

**Hinnanguline sisetemperatuur:**
- `hinnanguline_sisetemp = välistemp + 5°C`

**Juhtimisreeglid:**
- kui `hinnanguline_sisetemp < 12°C` → **küte vajalik**,
- kui `hinnanguline_sisetemp > 28°C` → **ventilatsioon vajalik**,
- muidu → **temperatuur sobiv**.

Mudelit kasutatakse demonstratsiooniks ning tegemist ei ole täpse agronoomilise simulatsiooniga.

## KPI-d / küsimused dashboardil
1. Soovitatud tunnid kütte ja ventilatsiooni kasutamiseks.
2. Millised on odavaimad tunnid, mil vajalikku seadet käitada?
3. Päevane hinnanguline energiakulu (€), kui järgida soovitusreegleid.

## Andmeallikad
- **Elektri spot-hind (Elering/Nord Pool)** – ajas muutuv põhiandmeallikas.
- **Ilmaandmed (välistemperatuur + päikesekiirgus)** – ajas muutuv põhiandmeallikas.

## Tehniline arhitektuur (näidis)
- Ingest: Python skriptid/API päringud (ajadatud käivitus: cron või orchestrator).
- Bronze: toorandmed (JSON/CSV või staging tabelid).
- Silver: puhastatud ja joinitud tunniandmed.
- Gold: analüütiline faktitabel soovituse, hinna ja ilma tunnustega.
- Dashboard: Metabase / Power BI / Superset.

## Minimaalne kaustastruktuur
```text
.
├── docs/
│   ├── arhitektuur.md
│   └── progress.md
├── scripts/
├── sql/
├── tests/
└── README.md
```

## Käivituse üldskeem
1. Sea `.env` fail API võtmetega (ära commiti seda).
2. Käivita ingest-skriptid (elektrihind + ilm).
3. Käivita transformatsioonid (sisetemp + otsusereeglid).
4. Käivita andmekvaliteedi testid (vähemalt 3 testi).
5. Uuenda dashboardi andmemudel.

## Meeskond
Projekt on planeeritud 4-liikmelisele grupile. Rollid jaotusena on kirjeldatud failis `docs/arhitektuur.md`.
>>>>>>> theirs
