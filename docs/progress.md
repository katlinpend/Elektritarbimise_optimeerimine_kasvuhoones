# Progress (25.05-31.05)

## Algseis
- Projekt alustas kursuse näidisstruktuurist ja lokaalsest Docker Compose töövoost.
- Esmalt oli paigas andmebaas, pipeline konteiner, scheduler ja Streamlit dashboardi konteiner.
- Esialgne loogika oli üldisem ilmaandmete näidik; hiljem täpsustati fookus kasvuhoone elektritarbimise optimeerimisele.

## Valmis tehtud
- Andmeallikad on ühendatud:
  - Open-Meteo Forecast API annab tunnipõhise välistemperatuuri.
  - Elering NPS API annab Eesti piirkonna elektrihinna kujul EUR/MWh.
- Pipeline loeb aktiivsed asukohad tabelist `mart.dim_location`.
- Ingest salvestab toorandmed tabelisse `staging.weather_hourly_raw`.
- Transformatsioon loob mart-kihi tabelid:
  - `mart.fact_weather_forecast`
  - `mart.hourly_weather_score`
  - `mart.daily_weather_summary`
- Tunnipõhine otsuseloogika on valmis:
  - `estimated_inside_temp_c = temperature_c + 5`
  - alla 12 kraadi: `heating`
  - üle 28 kraadi: `ventilation`
  - muidu: `none`
- Elektrihind teisendatakse mart-kihis ka kujule `price_eur_kwh`, et kulude arvutamisel ei peaks EUR/MWh ja EUR/kWh teisendust igal pool käsitsi kordama.
- Päevakoond arvutab:
  - kütte- ja ventilatsioonitunnid
  - reeglipõhise kulu
  - pideva kasutuse võrdluskulu
  - hinnangulise säästu
- Andmekvaliteedi testid on lisatud ja kontrollivad muu hulgas:
  - aktiivsete asukohtade olemasolu
  - koordinaatide mõistlikkust
  - viimase eduka laadimise tooridade olemasolu
  - kõigi aktiivsete asukohtade olemasolu viimases laadimises
  - prognoosiaja olemasolu
  - tunni kirjete unikaalsust
  - temperatuuri mõistlikku vahemikku
  - hinna olemasolu mart-kihis
  - `action_needed` lubatud väärtuseid
  - päevakoondi olemasolu
- Dashboard on tehtud Streamlitiga ning kasutab Altairi graafikuid.
- Dashboard kuvab kolm KPI-d:
  - kütte- ja ventilatsioonitundide arv päevas
  - reeglipõhiste tundide keskmine hind võrreldes päeva keskmisega
  - päevane reeglipõhine kulu võrreldes pideva kasutusega
- Dashboardi KPI-kaardid kasutavad nüüd valitud asukohta ja valitud kuupäeva, et päevane sääst ei summeeriks ekslikult mitut asukohta ja mitut päeva kokku.
- Üleliigsed sademete, tuule ja päevavalguse tunnused eemaldati aktiivsest kasvuhoone energia loogikast.

## Kontrollitud seis
- `docker compose exec pipeline python scripts/run_pipeline.py run-all` käivitus edukalt.
- `docker compose exec pipeline python scripts/run_pipeline.py check` näitas tulemusi.
- Quality testide lõpptulemus oli `failed_tests = 0`.
- Viimases kontrollis täitusid staging ja mart tabelid ning pipeline jõudis lõpuni.

## Rollide seis
- A osa: ingest, API ühendused, `.env`, scheduler ja andmete laadimine on tehtud ning kontrollitud.
- B osa: SQL transformatsioon, tunnipõhine otsuseloogika, päevakoond ja kulude arvutus on tehtud.
- C osa: kvaliteeditestid ja kontrollpäringud on tehtud.
- D osa: Streamlit dashboard on tehtud ning KPI-de valik loogilisemaks parandatud.

## Teadaolevad tähelepanekud
- Eleringi day-ahead hinnad ei kata alati kogu ilmaennustuse akent; hinnata read jäävad stagingusse, kuid mart-kihis kasutatakse ainult ridu, kus hind on olemas.
- `FORECAST_DAYS=2` on teadlik valik, sest see sobib paremini Eleringi hinnainfo kättesaadavusega.
- Projekt kasutab lihtsustusmudelit, mitte täpset kasvuhoone füüsikalist simulatsiooni.

## Järgmised võimalikud parandused
1. Ühtlustada kõik tabelinimed lõplikult kasvuhoone energia sõnastusega, kui vanast näidisprojektist jäänud nimesid veel kasutatakse.
2. Vajadusel lisada dashboardi rohkem selgitavaid filtreid või eksport.
3. Enne lõplikku esitamist käivitada kogu töövoog uuesti puhtas Docker keskkonnas.
