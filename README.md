# Elektritarbimise optimeerimine kasvuhoones

## Greenhouse Energy Optimization

## Projekti eesmärk

Selle projekti eesmärk on analüüsida, millal tasub kasvuhoones kasutada elektrit nõudvaid seadmeid (küte, ventilatsioon), et vähendada elektrikulusid börsihinnaga elektrilepingu korral.

Projekt kasutab elektri börsihindu ja ilmaandmeid, et leida soodsaimad ajad elektri tarbimiseks.

---

## Äriküsimus

Millistel tundidel tasub kasvuhoones elektrit tarbida (küte, ventilatsioon), et börsihinnaga lepingu korral minimeerida kulusid, arvestades välistemperatuuri ja päikesekiirgust?

### Millal on kõige soodsam kasutada kasvuhoones:
- kütet
- ventilatsiooni

### Arvestades:
- elektri börsihinda
- välistemperatuuri
- päikesekiirgust

---

## Projekti allikas ja töörepo

- Kursuse juhised ja näidismaterjalid pärinevad repost:  
  `https://github.com/KristoR/ut-andmeinseneeria-2026`

- Aktiivne töö käib selles repos:  
  `https://github.com/sirja-hass/Elektritarbimise_optimeerimine_kasvuhoones`

See projekt on tehtud kursuse **UT andmeinseneeria 2026** projektitöö nõuete järgi ning katab otsast-lõpuni andmetöövoo:

1. andmete sissevõtt
2. transformatsioon
3. andmekvaliteedi testid
4. dashboard

---

## Andmeallikad

Meie lihtsustus: kasvuhoone sisetemperatuuri sensorit ei kasutata.

### Elektrihinnad
- Elering API

### Ilmaandmed
- Ilmateenistuse API

### Hinnanguline sisetemperatuur

```text
hinnanguline_sisetemp = välistemp + 5°C
```

### Juhtimisreeglid

- kui `hinnanguline_sisetemp < 12°C` → küte vajalik
- kui `hinnanguline_sisetemp > 28°C` → ventilatsioon vajalik
- muidu → temperatuur sobiv

---

## KPI-d / küsimused dashboardil

1. Mitu tundi ööpäevas on küte/ventilatsioon vajalik?
2. Millised on odavaimad tunnid, mil vajalikku seadet käitada?
3. Päevane hinnanguline energiakulu (€), kui järgida soovitusreegleid.

---

## Tehnoloogiad

- Python
- PostgreSQL / Supabase
- SQL
- cron
- GitHub
- Metabase / Power BI

---

## Tehniline arhitektuur

- Ingest: Python skriptid / API päringud
- Bronze: toorandmed
- Silver: puhastatud ja ühendatud tunniandmed
- Gold: analüütiline faktitabel
- Dashboard: Metabase / Power BI / Superset

---

## Planeeritud töövoog

1. Python script küsib API-dest andmed
2. Andmed salvestatakse PostgreSQL andmebaasi
3. SQL päringud valmistavad andmed analüüsiks ette
4. Dashboard kuvab soovitused ja hinnainfo
5. cron käivitab andmete uuendamise automaatselt

---

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

---

## Käivituse üldskeem

1. Sea `.env` fail API võtmetega (ära commiti seda)
2. Käivita ingest-skriptid
3. Käivita transformatsioonid
4. Käivita andmekvaliteedi testid
5. Uuenda dashboardi andmemudel

---

## Meeskond

Projekt on planeeritud 4-liikmelisele grupile. Rollid jaotusena kirjeldatakse failis `docs/arhitektuur.md`.
