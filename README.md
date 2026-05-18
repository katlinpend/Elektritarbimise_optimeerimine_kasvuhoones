# Elektritarbimise_optimeerimine_kasvuhoones
Millistel tundidel on kasvuhoones kõige mõistlikum kasutada elektrit nõudvaid seadmeid, et börsihinnaga lepingu korral kulusid vähendada, arvestades ilmaolusid?
# Greenhouse Energy Optimization

## Projekti eesmärk

Selle projekti eesmärk on analüüsida, millal tasub kasvuhoones kasutada elektrit nõudvaid seadmeid (küte, valgustus, ventilatsioon), et vähendada elektrikulusid börsihinnaga elektrilepingu korral.

Projekt kasutab elektri börsihindu ja ilmaandmeid, et leida soodsaimad ajad elektri tarbimiseks.
# Elektritarbimise optimeerimine kasvuhoones

## Äriküsimus
Millistel tundidel tasub kasvuhoones kasutada elektrit nõudvaid seadmeid (küte, ventilatsioon), et vähendada elektrikulu börsihinna tingimustes, arvestades välistemperatuuri?

Millal on kõige soodsam kasutada kasvuhoones:
- kütet
- lisavalgustust
- ventilatsiooni

arvestades:
- elektri börsihinda
- välistemperatuuri
- päikesekiirgust
## Projekti allikas ja töörepo
- Kursuse juhised ja näidismaterjalid pärinevad repost: `https://github.com/KristoR/ut-andmeinseneeria-2026`.
- Aktiivne töö käib selles repos: `https://github.com/sirja-hass/Elektritarbimise_optimeerimine_kasvuhoones`.

## Andmeallikad
See projekt on tehtud kursuse **UT andmeinseneeria 2026** projektitöö nõuete järgi ning katab otsast-lõpuni andmetöövoo:
1. andmete sissevõtt,
2. transformatsioon,
3. andmekvaliteedi testid,
4. dashboard.

### Elektrihinnad
- Elering API
Meie lihtsustus: kasvuhoone sisetemperatuuri sensorit ei kasutata.

### Ilmaandmed
- Ilmateenistuse API
**Hinnanguline sisetemperatuur:**
- `hinnanguline_sisetemp = välistemp + 5°C`

## Tehnoloogiad
**Juhtimisreeglid:**
- kui `hinnanguline_sisetemp < 12°C` → **küte vajalik**,
- kui `hinnanguline_sisetemp > 28°C` → **ventilatsioon vajalik**,
- muidu → **temperatuur sobiv**.

- Python
- PostgreSQL / Supabase
- SQL
- cron
- GitHub
- Metabase / Power BI
Mudelit kasutatakse demonstratsiooniks ning tegemist ei ole täpse agronoomilise simulatsiooniga.

## Planeeritud töövoog
## KPI-d / küsimused dashboardil
1. Soovitatud tunnid kütte ja ventilatsiooni kasutamiseks.
2. Millised on odavaimad tunnid, mil vajalikku seadet käitada?
3. Päevane hinnanguline energiakulu (€), kui järgida soovitusreegleid.

1. Python script küsib API-dest andmed
2. Andmed salvestatakse PostgreSQL andmebaasi
3. SQL päringud valmistavad andmed analüüsiks ette
4. Dashboard kuvab soovitused ja hinnainfo
5. cron käivitab andmete uuendamise automaatselt
## Andmeallikad
- **Elektri spot-hind (Elering/Nord Pool)** – ajas muutuv põhiandmeallikas.
- **Ilmaandmed (välistemperatuur + päikesekiirgus)** – ajas muutuv põhiandmeallikas.

## Projekti struktuur
## Tehniline arhitektuur (näidis)
- Ingest: Python skriptid/API päringud (ajadatud käivitus: cron või orchestrator).
- Bronze: toorandmed (JSON/CSV või staging tabelid).
- Silver: puhastatud ja joinitud tunniandmed.
- Gold: analüütiline faktitabel soovituse, hinna ja ilma tunnustega.
- Dashboard: Metabase / Power BI / Superset.

## Minimaalne kaustastruktuur
```text
docs/           dokumentatsioon
scripts/        Python scriptid
sql/            SQL päringud
dashboard/      visualiseeringud
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