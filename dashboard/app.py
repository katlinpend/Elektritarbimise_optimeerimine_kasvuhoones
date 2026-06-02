from __future__ import annotations

import os

import altair as alt
import pandas as pd
import psycopg2
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


st.set_page_config(
    page_title="Kasvuhoone elektritarbimise optimeerija",
    page_icon=None,
    layout="wide",
)

ACTION_DOMAIN = ["heating", "ventilation", "none"]
ACTION_COLORS = ["#e07b39", "#2f9e44", "#adb5bd"]
ACTION_LABELS = {
    "heating": "Küte",
    "ventilation": "Ventilatsioon",
    "none": "Temperatuur sobiv",
}
WEEKDAY_LABELS = ["E", "T", "K", "N", "R", "L", "P"]
DEFAULT_LOCATION_NAMES = ["Tallinn", "Tartu", "Pärnu", "Kohtla-Järve", "Kuressaare"]


def get_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


auto_refresh_seconds = get_int_env("DASHBOARD_AUTOREFRESH_SECONDS", 15)
if auto_refresh_seconds > 0 and st_autorefresh is not None:
    st_autorefresh(interval=auto_refresh_seconds * 1000, key="dashboard_autorefresh")

if st.sidebar.button("Värskenda vaade"):
    st.rerun()


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", "5432"),
        user=os.environ.get("DB_USER", "praktikum"),
        password=os.environ.get("DB_PASSWORD", "praktikum"),
        dbname=os.environ.get("DB_NAME", "praktikum"),
    )


def load_dataframe(query: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)


def format_date_label(value: pd.Timestamp) -> str:
    return f"{WEEKDAY_LABELS[value.weekday()]} {value:%d.%m}"


def action_color() -> alt.Color:
    return alt.Color(
        "action_needed:N",
        title="Olek",
        scale=alt.Scale(domain=ACTION_DOMAIN, range=ACTION_COLORS),
        legend=alt.Legend(
            orient="bottom",
            labelExpr="datum.value === 'heating' ? 'Küte' : datum.value === 'ventilation' ? 'Ventilatsioon' : 'Sobiv'",
        ),
    )


# ------------------------------------------------------------------
# Andmete laadimine
# ------------------------------------------------------------------
hourly = load_dataframe(
    """
    SELECT
        h.location_id,
        h.location_name,
        l.county,
        l.display_order,
        h.forecast_time,
        h.forecast_date,
        h.forecast_hour,
        h.temperature_c,
        h.estimated_inside_temp_c,
        h.price_eur_mwh,
        h.action_needed,
        h.combined_score,
        h.suitability_label,
        h.main_reason
    FROM mart.latest_hourly_weather_score AS h
    INNER JOIN mart.dim_location AS l ON h.location_id = l.location_id
    ORDER BY l.display_order, h.forecast_time
    """
)

daily = load_dataframe(
    """
    SELECT
        location_name,
        forecast_date,
        heating_hours,
        ventilation_hours,
        avg_price_eur_mwh,
        rule_based_cost_eur,
        avg_price_cost_eur,
        estimated_savings_eur,
        weather_risk_level
    FROM mart.latest_daily_weather_summary
    ORDER BY location_name, forecast_date
    """
)



latest_run = load_dataframe(
    """
    SELECT run_id::text AS run_id, fetched_at, forecast_days, status, message
    FROM mart.latest_pipeline_run
    """
)

quality = load_dataframe(
    """
    SELECT test_name, status, failed_rows, message
    FROM quality.test_results
    ORDER BY test_name
    """
)

# ------------------------------------------------------------------
# Tühja andmestiku kontroll
# ------------------------------------------------------------------
if hourly.empty:
    st.warning(
        "Andmeid ei ole veel laaditud. Käivita: "
        "`docker compose exec pipeline python scripts/run_pipeline.py run-all`"
    )
    st.stop()

# ------------------------------------------------------------------
# Tüübiteisendused
# ------------------------------------------------------------------
hourly["forecast_time"] = pd.to_datetime(hourly["forecast_time"])
hourly["forecast_date"] = pd.to_datetime(hourly["forecast_date"])
for col in ["temperature_c", "estimated_inside_temp_c", "price_eur_mwh",
            "combined_score", "display_order"]:
    hourly[col] = pd.to_numeric(hourly[col], errors="coerce")
hourly["forecast_date_label"] = hourly["forecast_time"].map(format_date_label)

if not daily.empty:
    daily["forecast_date"] = pd.to_datetime(daily["forecast_date"])
    for col in ["heating_hours", "ventilation_hours", "avg_price_eur_mwh",
                "rule_based_cost_eur", "avg_price_cost_eur", "estimated_savings_eur"]:
        daily[col] = pd.to_numeric(daily[col], errors="coerce")


# ------------------------------------------------------------------
# Küljeriba – asukoha valik
# ------------------------------------------------------------------
locations = (
    hourly[["location_name", "display_order"]]
    .drop_duplicates()
    .sort_values(["display_order", "location_name"])["location_name"]
    .tolist()
)
default_locations = [n for n in DEFAULT_LOCATION_NAMES if n in locations] or locations[:5]

selected_locations = st.sidebar.multiselect(
    "Asukohad", options=locations, default=default_locations, key="selected_locations"
)

if not selected_locations:
    st.info("Vali vähemalt üks asukoht.")
    st.stop()

if st.session_state.get("detail_location") not in selected_locations:
    st.session_state["detail_location"] = selected_locations[0]

detail_location = st.sidebar.selectbox(
    "Detailvaate asukoht", options=selected_locations, key="detail_location"
)

# ------------------------------------------------------------------
# Filtreerimine
# ------------------------------------------------------------------
filt_hourly = hourly[hourly["location_name"].isin(selected_locations)].copy()
filt_daily = daily[daily["location_name"].isin(selected_locations)].copy() if not daily.empty else pd.DataFrame()

action_price_daily = (
    filt_hourly[filt_hourly["action_needed"].isin(["heating", "ventilation"])]
    .groupby(["location_name", "forecast_date"], as_index=False)["price_eur_mwh"]
    .mean()
    .rename(columns={"price_eur_mwh": "avg_action_price_eur_mwh"})
)

filt_daily = filt_daily.merge(
    action_price_daily,
    on=["location_name", "forecast_date"],
    how="left",
)

filt_daily["avg_price_eur_kwh"] = filt_daily["avg_price_eur_mwh"] / 1000
filt_daily["avg_action_price_eur_kwh"] = filt_daily["avg_action_price_eur_mwh"] / 1000

available_dates = []
if not filt_daily.empty:
    available_dates = sorted(filt_daily["forecast_date"].dt.date.unique())

selected_date = None
if available_dates:
    selected_date = st.sidebar.selectbox(
        "KPI kuupäev",
        options=available_dates,
        format_func=lambda value: pd.Timestamp(value).strftime("%d.%m.%Y"),
    )

if selected_date is not None:
    filt_daily_for_kpi = filt_daily[
        (filt_daily["forecast_date"].dt.date == selected_date)
        & (filt_daily["location_name"] == detail_location)
    ].copy()
    filt_daily_for_charts = filt_daily[
        filt_daily["forecast_date"].dt.date == selected_date
    ].copy()
else:
    filt_daily_for_kpi = pd.DataFrame()
    filt_daily_for_charts = filt_daily.copy()

# ------------------------------------------------------------------
# Pealkiri ja viimane laadimine
# ------------------------------------------------------------------
st.title("Elektritarbimise optimeerimine kasvuhoones")
st.markdown(
    "Millistel tundidel on kasvuhoones vaja kasutada elektrit nõudvaid seadmeid (küte ja ventilatsioon), arvestades hinnangulist sisetemperatuuri, ning kui palju väiksem on hinnanguline elektrikulu võrreldes olukorraga, kus seade töötaks kogu päeva jooksul pidevalt?"
)

if not latest_run.empty:
    run = latest_run.iloc[0]
    st.caption(f"Viimane laadimine: {run['fetched_at']} | {run['message']}")

# ------------------------------------------------------------------
# KPI mõõdikud (valitud asukoht ja kuupäev)
# ------------------------------------------------------------------
if selected_date is not None:
    selected_date_label = pd.Timestamp(selected_date).strftime("%d.%m.%Y")
    st.info(f"Asukoht: {detail_location} | Kuupäev: {selected_date_label}")

if not filt_daily_for_kpi.empty:
    total_heating = int(filt_daily_for_kpi["heating_hours"].sum())
    total_ventilation = int(filt_daily_for_kpi["ventilation_hours"].sum())
    total_hours = total_heating + total_ventilation

    avg_action_price = filt_daily_for_kpi["avg_action_price_eur_kwh"].mean()
    avg_day_price = filt_daily_for_kpi["avg_price_eur_kwh"].mean()

    total_rule_cost = filt_daily_for_kpi["rule_based_cost_eur"].sum()
    total_continuous_cost = filt_daily_for_kpi["avg_price_cost_eur"].sum()
    total_savings = filt_daily_for_kpi["estimated_savings_eur"].sum()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Tegevustunnid",
        f"{total_hours} h",
        f"Küte {total_heating} h, ventilatsioon {total_ventilation} h",
    )

    col2.metric(
        "Reeglipõhine keskmine elektrihind",
        f"{avg_action_price:.4f} €/kWh" if pd.notna(avg_action_price) else "Vajadus puudub",
        f"Päeva keskmine {avg_day_price:.4f} €/kWh",
    )

    col3.metric(
        "Päevane kulu",
        f"{total_rule_cost:.2f} €",
        f"Pidev {total_continuous_cost:.2f} €, sääst {total_savings:.2f} €",
    )

# ------------------------------------------------------------------
# KPI 1: Kütte- ja ventilatsioonitundide arv päevas
# ------------------------------------------------------------------
st.subheader("KPI 1 – Tegevustunnid")

if not filt_daily_for_charts.empty:

    kpi1_data = filt_daily_for_charts.melt(
        id_vars=["location_name", "forecast_date"],
        value_vars=["heating_hours", "ventilation_hours"],
        var_name="tegevus",
        value_name="tunnid",
    )

    kpi1_data["tegevus"] = kpi1_data["tegevus"].map({
        "heating_hours": "Küte",
        "ventilation_hours": "Ventilatsioon",
    })

    kpi1_data["Kuupäev"] = kpi1_data["forecast_date"].dt.strftime("%d.%m")

    chart = (
        alt.Chart(kpi1_data)
        .mark_bar()
        .encode(
            y=alt.Y("location_name:N", title="Asukoht"),
            x=alt.X(
                "sum(tunnid):Q",
                title="Tunde",
                scale=alt.Scale(domain=[0, 24]),
                axis=alt.Axis(
                    format="d",
                    tickMinStep=1,
                    grid=False,
                ),
            ),
            color=alt.Color(
                "tegevus:N",
                title="Tegevus",
                scale=alt.Scale(
                    domain=["Küte", "Ventilatsioon"],
                    range=["#e07b39", "#2f9e44"],
                ),
            ),
            tooltip=[
                alt.Tooltip("location_name:N", title="Asukoht"),
                alt.Tooltip("Kuupäev:N", title="Kuupäev"),
                alt.Tooltip("tegevus:N", title="Tegevus"),
                alt.Tooltip("tunnid:Q", title="Tunde"),
            ],
        )
        .properties(height=350)
    )

    st.altair_chart(chart, use_container_width=True)

# ------------------------------------------------------------------
# KPI 2: Keskmine elektrihind reeglipõhise kasutuse tundidel võrreldes päeva keskmise hinnaga
# ------------------------------------------------------------------
st.subheader("KPI 2 – Reeglipõhine keskmine elektrihind")

detail_daily = filt_daily_for_kpi.copy()
avg_action_price = pd.NA
avg_day_price = pd.NA

if not detail_daily.empty:
    avg_action_price = detail_daily["avg_action_price_eur_kwh"].mean()
    avg_day_price = detail_daily["avg_price_eur_kwh"].mean()

if pd.notna(avg_action_price):

    col1, col2 = st.columns(2)

    col1.metric(
        "Reeglipõhine keskmine elektrihind",
        f"{avg_action_price:.4f} €/kWh"
    )

    col2.metric(
        "Päeva keskmine elektrihind",
        f"{avg_day_price:.4f} €/kWh"
    )

else:
    st.info(
        f"{detail_location}: valitud perioodil ei olnud kütte- ega ventilatsioonivajadust."
    )

    st.metric(
        "Päeva keskmine hind",
        f"{avg_day_price:.4f} €/kWh"
    )

# ------------------------------------------------------------------
# KPI 3: Hinnanguline päevane elektrikulu reeglipõhises kasutuses vs pidev kasutus
# ------------------------------------------------------------------
st.subheader("KPI 3 – Päevane kulu")

if not filt_daily_for_kpi.empty:
    cost_summary = filt_daily_for_kpi.copy()
    cost_summary["Kuupäev"] = cost_summary["forecast_date"].dt.strftime("%d.%m")

    cost_data = cost_summary.melt(
        id_vars=["location_name", "forecast_date", "Kuupäev"],
        value_vars=[
            "rule_based_cost_eur",
            "avg_price_cost_eur",
            "estimated_savings_eur",
        ],
        var_name="näitaja",
        value_name="euro",
    )

    cost_data["näitaja"] = cost_data["näitaja"].map({
        "rule_based_cost_eur": "Reeglipõhine kulu",
        "avg_price_cost_eur": "Pidev kasutus",
        "estimated_savings_eur": "Sääst",
    })

    cost_chart = (
        alt.Chart(cost_data)
        .mark_bar()
         .encode(
            y=alt.Y(
                "näitaja:N",
                title=None,
                sort=[
                    "Pidev kasutus",
                    "Reeglipõhine kulu",
                    "Sääst",
                ],
            ),
            x=alt.X(
                "euro:Q",
                title="Eurot (€)",
                scale=alt.Scale(zero=True),
                axis=alt.Axis(
                    format="d",
                    tickMinStep=1,
                    grid=False,
                ),
            ),
            color=alt.Color(
                "näitaja:N",
                title="Näitaja",
                scale=alt.Scale(
                    domain=[
                        "Pidev kasutus",
                        "Reeglipõhine kulu",
                        "Sääst",
                    ],
                    range=[
                        "#1f77b4",  # sinine - Pidev kasutus
                        "#e07b39",  # oranž - Reeglipõhine kulu
                        "#2ca02c",  # roheline - Sääst
                    ],
                ),
            ),
            tooltip=[
                alt.Tooltip("Kuupäev:N", title="Kuupäev"),
                alt.Tooltip("näitaja:N", title="Näitaja"),
                alt.Tooltip("euro:Q", title="€", format=".2f"),
            ],
        )
        .properties(
            height=300,
            title=f"Päevane kulu ja sääst – {detail_location}",
        )
    )

    st.altair_chart(cost_chart, use_container_width=True)

    # Päevakoond tabel
    filt_daily_display = filt_daily_for_charts.copy()
    filt_daily_display["forecast_date"] = (
        filt_daily_display["forecast_date"]
        .dt.strftime("%d.%m.%Y")
    )
    st.dataframe(
        filt_daily_display[[
            "location_name",
            "forecast_date",
            "heating_hours",
            "ventilation_hours",
            "rule_based_cost_eur",
            "avg_price_cost_eur",
            "estimated_savings_eur",
            "avg_price_eur_kwh",
        ]].rename(columns={
            "location_name": "Asukoht",
            "forecast_date": "Kuupäev",
            "heating_hours": "Küttetunde",
            "ventilation_hours": "Vent. tunde",
            "rule_based_cost_eur": "Reeglipõhine kulu €",
            "avg_price_cost_eur": "Pidev kasutus €",
            "estimated_savings_eur": "Sääst €",
            "avg_price_eur_kwh": "Päeva keskmine hind €/kWh",
        }),
        use_container_width=True,
        hide_index=True,
    )

# ------------------------------------------------------------------
# Temperatuuri detailvaade
# ------------------------------------------------------------------
detail_data = filt_hourly[filt_hourly["location_name"] == detail_location].copy()
st.subheader(f"Temperatuur – {detail_location}")

if not detail_data.empty:
    temp_base = alt.Chart(detail_data)

    outside = temp_base.mark_line(
        color="#1f77b4",
        strokeWidth=3,
    ).encode(
        x=alt.X(
            "forecast_time:T",
            title="Kellaaeg",
            axis=alt.Axis(
                format="%H",
                tickCount=24,
                labelAngle=0,
                grid=False,
            ),
        ),
        y=alt.Y(
            "temperature_c:Q",
            title="Temperatuur °C",
            axis=alt.Axis(grid=False),
        ),
        tooltip=[
            alt.Tooltip("forecast_time:T", title="Aeg", format="%d.%m %H:%M"),
            alt.Tooltip("temperature_c:Q", title="Välistemp °C", format=".1f"),
            alt.Tooltip("estimated_inside_temp_c:Q", title="Hinn. sisetemp °C", format=".1f"),
        ],
    )

    inside = temp_base.mark_line(
        color="#e07b39",
        strokeWidth=3,
    ).encode(
        x=alt.X(
            "forecast_time:T",
            title="Kellaaeg",
            axis=alt.Axis(
                format="%H",
                tickCount=24,
                labelAngle=0,
                grid=False,
            ),
        ),
        y=alt.Y(
            "estimated_inside_temp_c:Q",
            title="Temperatuur °C",
            axis=alt.Axis(grid=False),
        ),
        tooltip=[
            alt.Tooltip("forecast_time:T", title="Aeg", format="%d.%m %H:%M"),
            alt.Tooltip("estimated_inside_temp_c:Q", title="Hinn. sisetemp °C", format=".1f"),
        ],
    )

    rule_low = alt.Chart(pd.DataFrame({"y": [12]})).mark_rule(
        color="#999999",
        strokeWidth=1,
        opacity=0.6,
    ).encode(
        y="y:Q",
    )

    rule_high = alt.Chart(pd.DataFrame({"y": [28]})).mark_rule(
        color="#999999",
        strokeWidth=1,
        opacity=0.6,
    ).encode(
        y="y:Q",
    )

    st.altair_chart(
        (outside + inside + rule_low + rule_high).properties(height=220),
        use_container_width=True,
    )

    st.caption(
        "Sinine joon – välistemperatuur | "
        "Oranž joon – hinnanguline sisetemperatuur (välistemp + 5°C) | "
        "Hallid horisontaaljooned – küttepiir 12°C ja ventilatsioonipiir 28°C"
    )

# ------------------------------------------------------------------
# Andmekvaliteedi testid
# ------------------------------------------------------------------
st.subheader("Andmekvaliteedi kontrollid")
if not quality.empty:
    def highlight_status(row):
        if row["status"] == "failed":
            return ["background-color: #FCEBEB"] * len(row)
        return [""] * len(row)
    st.dataframe(
        quality.style.apply(highlight_status, axis=1),
        use_container_width=True,
        hide_index=True,
    )
