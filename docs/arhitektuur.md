# Arhitektuur ja planeerimine (18.05–24.05)

<<<<<<< ours
# Arhitektuur (nädal 1)

## Äriküsimus
Millistel tundidel tasub kasvuhoones kasutada kütet/ventilatsiooni, et vähendada elektrikulu börsihinna tingimustes?

## Mõõdikud (KPI)
1. Soovitatud kütte- ja ventilatsioonitunnid päevas.
2. Keskmine börsihind soovitatud tundidel vs päeva keskmine.
3. Hinnanguline päevane energiakulu.

## Andmeallikad
1. **Open-Meteo Forecast API** (ajas muutuv)
2. **Elering NPS price API** (ajas muutuv, day-ahead)

## Oluline andmepiirang
Eleringi day-ahead hind tähendab, et praktiline otsustusaken on lühike (täna + homme).  
Seetõttu kasutame `FORECAST_DAYS=2`.

## Lihtsustusmudel
- `hinnanguline_sisetemp = välistemp + 5°C`
- `<12°C` → küte vajalik
- `>28°C` → ventilatsioon vajalik
- muidu sobiv

## Andmekihid
- `staging`: toorandmed API-dest
- `mart`: otsuseloogika ja koondid
- `quality`: testitulemused

## Tehniline voog
```mermaid
flowchart LR
    A[Open-Meteo API] --> B[Pipeline ingest]
    C[Elering API] --> B
    B --> D[(staging)]
    D --> E[SQL transform]
    E --> F[(mart)]
    F --> G[Dashboard]
    F --> H[Quality tests]

    ## 6) Andmekihid

### staging
API-dest laetud toorandmed (tunnipõhised kirjed).

### mart
Otsustamiseks vajalikud mudel- ja koondtabelid.

### quality
Andmekvaliteedi testide tulemused.

---

## 7) Tehniline voog (otsast lõpuni)

1. Scheduler või käsukäivitus alustab pipeline run’i.
2. Ingest loeb Open-Meteo ja Elering API andmed.
3. Toorandmed salvestatakse `staging` kihti.
4. Transformatsioon loob `mart` kihti otsusetabelid:
   - hinnanguline sisetemperatuur,
   - tegevussoovitus (`heating`, `ventilation`, `none`),
   - hinnapõhised võrdlused.
5. Quality testid kontrollivad andmete usaldusväärsust.
6. Dashboard kuvab KPI-d ja soovitused.

---

## 8) Rollid (4 liiget)

### Osaleja A – ingest + ajastus
- API ühendused (Open-Meteo + Elering)
- `.env` seadistus
- cron/scheduler käivituse kontroll

### Osaleja B – transformatsioonid
- SQL loogika `mart` kihti
- reeglite rakendus (`+5°C`, läved `12°C` / `28°C`)

### Osaleja C – andmekvaliteet
- vähemalt 3 sisukat testi
- testitulemuste jälgimine

### Osaleja D – dashboard + esitlus
- visualiseerimine KPI-de järgi
- README viimistlus ja demo/video

---

## 9) Andmekvaliteedi testid (esmane plaan)

### Kohustuslikud testid
- elektrihind ei tohi olla `NULL`;
- temperatuur peab jääma mõistlikku vahemikku (`-50..50`);
- sama käivituse, asukoha ja tunni kohta peab kirje olema unikaalne.

### Soovitatavad lisatestid
- otsusetabelis peab `action` olema ainult:
  - `heating`
  - `ventilation`
  - `none`
- hinnanguline sisetemperatuur peab jääma mõistlikku vahemikku.

---

## 10) Riskid ja leevendused

### API 502 / timeout vead
**Leevendus:** retry-loogika, väiksem `FORECAST_DAYS`, korduskäivitus.

### Hinna ja ilma ajaline mittekattuvus
**Leevendus:** otsustabelisse lähevad ainult tunnid, kus mõlemad andmed on olemas.

### Ajavööndi nihked
**Leevendus:** ühtne ajavöönd ja kontrollpäringud pärast ingestit.

### Liiga pikk prognoos, millele hinnad puuduvad
**Leevendus:** hoida otsustusaken day-ahead loogikaga kooskõlas (`FORECAST_DAYS=2`).q
=======
## Reposid
- Kursuse infoallikas: `https://github.com/KristoR/ut-andmeinseneeria-2026`
- Projekti töörepo: `https://github.com/sirja-hass/Elektritarbimise_optimeerimine_kasvuhoones`

## 1) Äriküsimus
Millistel tundidel tasub kasvuhoones kasutada elektrit nõudvaid seadmeid (küte, ventilatsioon), et vähendada elektrikulu börsihinna tingimustes, arvestades välistemperatuuri?

## 2) Mõõdikud (2–3)
1. **Soovitatud tunnid kütte ja ventilatsiooni kasutamiseks.**
2. **Keskmine spot-hind soovitatud tundidel** vs päeva keskmine spot-hind.
3. **Hinnanguline päevane kulu** (€) reeglipõhise juhtimise korral.

## 3) Lihtsustusmudel (baastase)
Kuna sisetemperatuuri sensorit ei kasutata, arvutame hinnangu:

`hinnanguline_sisetemp = välistemp + 5°C`

Reeglid:
- `hinnanguline_sisetemp < 12°C` → **küte vajalik**
- `hinnanguline_sisetemp > 28°C` → **ventilatsioon vajalik**
- muidu → **temperatuur sobiv**

Mudelit kasutatakse demonstratsiooniks ning tegemist ei ole täpse agronoomilise simulatsiooniga.

## 4) Andmeallikad ja muutuvus
- **Elektri spot-hind (API):** tunnipõhine, muutub ajas (põhiandmevoog).
- **Ilmaandmed (API):** tunnipõhine prognoos/ajalooline välistemperatuur + päikesekiirgus (põhiandmevoog).
- **Staatilised kõrvalandmed (vajadusel):** seadmete nimivõimsused (CSV seed), et arvutada kulu.

## 5) Arhitektuuriskeem (Mermaid)
```mermaid
flowchart LR
    A[Elering API] --> B[Python ingest]
    C[Ilma API] --> B

    B --> D[(PostgreSQL / Supabase)]

    D --> E[SQL transformatsioonid]

    E --> F[(Analytics tabel)]

    F --> G[Dashboard]

    F --> H[Andmekvaliteedi testid]
```

## 6) Tööjaotus (4 liiget)
1. **Liige A – Ingest & ajastus**
   - API connectorid (hind + ilm), `.env` seadistus, ajastus.
2. **Liige B – Andmemudel & transformatsioon**
   - Bronze/Silver/Gold mudelid, joinid, reeglite rakendus.
3. **Liige C – Andmekvaliteet**
   - Testid:
     - elektrihind ei tohi olla NULL
     - temperatuur peab jääma mõistlikku vahemikku
     - tunnikirjed peavad olema unikaalsed
4. **Liige D – Dashboard & esitlus**
   - KPI visualid, README viimistlus, demo-video.

## 7) Riskid (2–3)
1. API katkestused või päringupiirangud (rate limit).
2. Ajavööndite vastuolu (UTC vs Europe/Tallinn) tunniandmete joinimisel.
3. API andmete puudumine või vigased tunnikirjed.

## 8) Nädala väljundid
- `docs/arhitektuur.md` valmis.
- API-de testpäringud tehtud.
- Rollid ja esmane tehniline plaan paigas.
>>>>>>> theirs
