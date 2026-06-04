# Elektritarbimise optimeerimine kasvuhoones (Greenhouse Energy Optimization)

## Projekti eesmärk
Selle projekti eesmärk on analüüsida, millal tasub kasvuhoones kasutada elektrit nõudvaid seadmeid (küte, ventilatsioon), et vähendada elektrikulusid börsihinnaga elektrilepingu korral.

## Äriküsimus
Millistel tundidel on kasvuhoones vaja kasutada elektrit nõudvaid seadmeid (küte ja ventilatsioon), arvestades hinnangulist sisetemperatuuri, ning kui palju väiksem on hinnanguline elektrikulu võrreldes olukorraga, kus seade töötaks kogu päeva jooksul pidevalt?

---

## Projekti allikas ja töörepo

- Kursuse juhised ja näidismaterjalid: https://github.com/KristoR/ut-andmeinseneeria-2026
- Projekti töörepo: https://github.com/sirja-hass/Elektritarbimise_optimeerimine_kasvuhoones

Projekt kasutab elektri börsihindu ja ilmaandmeid, et leida soodsaimad ajad elektri tarbimiseks.

---

## Projekti ulatus

Projekt on tehtud kursuse **UT andmeinseneride täiendkoolitusprogramm 2026** projektitöö nõuete järgi ning katab tervikliku andmetöövoo alates andmete kogumisest kuni visualiseerimiseni.

1. Andmete sissevõtt (ingest) Open-Meteo Forecast API-st ja Elering NPS API-st.
2. Andmete transformatsioon, mille käigus arvutatakse hinnanguline kasvuhoone sisetemperatuur, energiavajadus ning elektrikulu näitajad.
3. Andmekvaliteedi testid, mis kontrollivad lähteandmete olemasolu, korrektsust ja transformatsioonide tulemusi.
4. Streamlit Dashboard, mis kuvab KPI-d ja visualiseeringud kasvuhoone energiavajaduse ning elektrikulude kohta.
5. Automatiseeritud töövoog, kus cron scheduler käivitab andmete uuendamise regulaarselt.

---

## Lihtsustusmudel

Kuna sisetemperatuuri sensorit ei kasutata, lähtume baastaseme hinnangust:

```text
hinnanguline_sisetemp = välistemp + 5°C
```

Juhtimisreeglid:

- kui `hinnanguline_sisetemp < 12°C` → küte vajalik
- kui `hinnanguline_sisetemp > 28°C` → ventilatsioon vajalik
- muidu → temperatuur sobiv

Arvesse võetakse:

- elektri börsihind
- välistemperatuur

Mudelit kasutatakse demonstratsiooniks ning tegemist ei ole täpse agronoomilise simulatsiooniga.

---

## Andmekvaliteedi testid

Projekt sisaldab automatiseeritud andmekvaliteedi teste, mis käivitatakse pärast andmete laadimist ja transformatsioone. Testide tulemused salvestatakse tabelisse `quality.test_results`.

| Test | Eesmärk |
|--------|--------|
| `dim_location_has_active_rows` | Vähemalt üks aktiivne asukoht on olemas |
| `active_locations_have_coordinates` | Aktiivsetel asukohtadel peavad olema korrektsed koordinaadid |
| `weather_raw_has_rows` | Viimases edukas laadimises peab olema vähemalt üks ilmaandmete rida |
| `latest_run_has_active_locations` | Kõigi aktiivsete asukohtade kohta peavad viimases laadimises andmed olemas olema |
| `forecast_time_not_null` | Prognoosi aeg ei tohi puududa |
| `forecast_time_not_stale` | Vähemalt mõni prognoositund peab olema tulevikus |
| `unique_location_time_per_run` | Sama käivituse, asukoha ja tunni kohta tohib olla ainult üks rida |
| `temperature_reasonable` | Temperatuur peab jääma vahemikku −50°C kuni 50°C |
| `price_coverage_exists` | Vähemalt mõne tunni elektrihind peab olema olemas |
| `mart_price_not_null` | Mart-kihi faktitabelis ei tohi elektrihind olla NULL |
| `mart_hourly_score_has_rows` | Tunnipõhine skooritabel peab sisaldama ridu |
| `action_and_label_consistent` | `action_needed` ja `suitability_label` peavad omavahel vastama |
| `combined_score_range` | Kombineeritud sobivuse skoor peab jääma vahemikku 0 kuni 100 |
| `mart_daily_summary_has_rows` | Päevane koondtabel peab sisaldama näidikulaua ridu |
Viimases kontrollis läbisid kõik testid edukalt (`failed_tests = 0`).

---

## Andmeallikad

Projekt modelleerib kasvuhoone otsuseid 5 Eesti asukoha põhjal:

- Tallinn
- Tartu
- Pärnu
- Kohtla-Järve
- Kuressaare

Põhiandmeallikad:

- **Open-Meteo Forecast API** – tunnipõhine välistemperatuuri prognoos
- **Elering NPS API** – tunnipõhine elektri spot-hind Eestis

Oluline piirang:

Eleringi day-ahead hinnad on otsustamiseks usaldusväärselt kättesaadavad peamiselt tänase ja homse kohta, seetõttu kasutatakse lühikest otsustusakent:

```text
FORECAST_DAYS=2
```

---

## KPI-d / küsimused dashboardil

1. Kütte- ja ventilatsioonitundide arv päevas
2. Keskmine elektrihind reeglipõhise kasutuse tundidel võrreldes päeva keskmise hinnaga
3. Hinnanguline päevane elektrikulu reeglipõhises kasutuses vs pidev kasutus

---

## Tehnoloogiad

- Dashboard: Streamlit + Altair
- Andmebaas: PostgreSQL
- Andmete sissevõtt: Python + Requests
- Andmetöötlus: Python + SQL
- Konteinerid ja orkestreerimine: Docker Compose
- Ajastus: Cron
- Versioonihaldus: GitHub

---

## Tehniline voog

```mermaid
flowchart LR
    A[Open-Meteo API]
    B[Elering NPS API]

    A --> C[Python ingest]
    B --> C

    C --> D[(staging)]

    D --> E[SQL transformatsioonid]

    E --> F[(mart)]

    F --> G[Streamlit Dashboard]

    F --> H[Andmekvaliteedi testid]

    H --> I[(quality.test_results)]
```

---

## Planeeritud töövoog

1. Python pipeline pärib ilmaandmed Open-Meteo API-st ja elektrihinnad Elering NPS API-st.
2. Toorandmed salvestatakse PostgreSQL andmebaasi staging-kihti.
3. SQL transformatsioonid loovad mart-kihi tabelid ning arvutavad KPI-de jaoks vajalikud näitajad.
4. Andmekvaliteedi testid kontrollivad andmete korrektsust ja transformatsioonide tulemusi.
5. Streamlit dashboard kuvab KPI-d, visualiseerimised ja kvaliteeditestide tulemused.
6. Cron scheduler käivitab andmete uuendamise automaatselt.

---

## Projekti kaustastruktuur

```text
.
├── dashboard/
│   └── app.py
├── docs/
│   ├── arhitektuur.md
│   └── progress.md
├── init/
│   └── 01_create_objects.sql
├── scripts/
│   ├── 00_seed_dimensions.sql
│   ├── 01_transform.sql
│   ├── 02_quality_tests.sql
│   ├── 03_check_results.sql
│   ├── requirements.txt
│   ├── run_pipeline.py
│   └── start_cron.sh
├── .env.example
├── .gitignore
├── Dockerfile.app
├── README.md
└── compose.yml
```

---

## Käivitamine

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec pipeline python scripts/run_pipeline.py run-all
docker compose exec pipeline python scripts/run_pipeline.py check
```

Scheduleri logid:

```bash
docker compose logs -f scheduler
```

Dashboard:

```text
http://localhost:8501
```

---

## Projekti struktuur

| Kaust / fail | Kirjeldus |
|-------------|-----------|
| `docs/` | Projekti dokumentatsioon (arhitektuur, töö edenemine) |
| `scripts/` | Andmete sissevõtt, transformatsioonid, kvaliteeditestid ja scheduler |
| `dashboard/` | Streamlit dashboard ja visualiseerimised |
| `init/` | Andmebaasi objektide loomise SQL skriptid |
| `.env.example` | Keskkonnamuutujate näidisfail |
| `compose.yml` | Docker Compose konfiguratsioon |
| `README.md` | Projekti dokumentatsioon ja käivitusjuhend |

---

## Meeskond

Rollide jaotus on kirjeldatud failis:

```text
docs/arhitektuur.md
```
1. Sirja Hass
2. Piret Sults
3. Ave Kaare
4. Kätlin Pendarov

---

## Kokkuvõte

Kokkuvõttes valmis projekti käigus täielik andmetöövoog kasvuhoone elektritarbimise optimeerimise hindamiseks. 
Valmis said:

- Open-Meteo Forecast API ja Elering NPS API andmete automaatne sissevõtt.
- PostgreSQL andmebaasi staging- ja mart-kihi andmemudel.
- SQL transformatsioonid, mis arvutavad hinnangulise sisetemperatuuri, energiavajaduse ning elektrikulud.
- 14 automatiseeritud andmekvaliteedi testi.
- Streamlit dashboard kolme peamise KPI-ga.
- Docker Compose keskkond koos scheduleriga.
- Cron-põhine automaatne andmete uuendamine.
- Projekti dokumentatsioon ja käivitusjuhised.

---

## Puudused

- Kasvuhoone sisetemperatuuri hinnatakse lihtsustatud mudeliga (välistemperatuur + 5°C), mitte tegelike sensoriandmete põhjal.
- Küte ja ventilatsioon on modelleeritud lihtsustatud loogikaga ega arvesta seadmete erinevat võimsust või töörežiime.
- Elektrikulu arvutustes kasutatakse fikseeritud energiatarbimise eeldust (5 kWh tunnis).
- Eleringi day-ahead hinnad ei kata alati kogu ilmaennustuse perioodi, mistõttu kasutatakse ainult neid ridu, mille jaoks on elektrihind olemas.
- Dashboard keskendub peamiselt päevataseme KPI-dele ning ei sisalda detailsemaid analüütilisi vaateid.

---

## Võimalikud edasiarendused

Kui projekti edasi arendada, võiks:

- kasutada päris kasvuhoone sensoriandmeid sisetemperatuuri hindamise asemel;
- lisada niiskuse, päikesekiirguse ja muude keskkonnanäitajate mõju;
- luua täpsema energiatarbimise mudeli erinevate seadmete jaoks;
- lisada dashboardile rohkem filtreid ja võrdlusvaateid;
- lisada automaatsed teavitused kõrge elektrihinna või suure energiavajaduse korral;
- kasutada pikemaajalisi prognoose ja ajaloolisi andmeid trendide analüüsimiseks.

