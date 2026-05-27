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
    "heating": "Küte vajalik",
    "ventilation": "Ventilatsioon vajalik",
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

windows = load_dataframe(
    """
    SELECT
        w.location_id,
        w.location_name,
        l.county,
        l.display_order,
        w.window_start,
        w.window_end,
        w.avg_temperature_c,
        w.avg_price_eur_mwh,
        w.heating_hours,
        w.ventilation_hours,
        w.recommendation_label,
        w.main_reason
    FROM mart.latest_outdoor_activity_windows AS w
    INNER JOIN mart.dim_location AS l ON w.location_id = l.location_id
    ORDER BY w.avg_price_eur_mwh ASC NULLS LAST, w.window_start
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

if not windows.empty:
    windows["window_start"] = pd.to_datetime(windows["window_start"])
    windows["window_end"] = pd.to_datetime(windows["window_end"])
    for col in ["avg_temperature_c", "avg_price_eur_mwh",
                "heating_hours", "ventilation_hours", "display_order"]:
        windows[col] = pd.to_numeric(windows[col], errors="coerce")

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
filt_windows = windows[windows["location_name"].isin(selected_locations)].copy() if not windows.empty else pd.DataFrame()

# ------------------------------------------------------------------
# Pealkiri ja viimane laadimine
# ------------------------------------------------------------------
st.title("Kasvuhoone elektritarbimise optimeerija")

if not latest_run.empty:
    run = latest_run.iloc[0]
    st.caption(f"Viimane laadimine: {run['fetched_at']} | {run['message']}")

# ------------------------------------------------------------------
# KPI mõõdikud (päevakoond, kõik valitud asukohad kokku)
# ------------------------------------------------------------------
if not filt_daily.empty:
    total_heating = int(filt_daily["heating_hours"].sum())
    total_ventilation = int(filt_daily["ventilation_hours"].sum())
    total_rule_cost = filt_daily["rule_based_cost_eur"].sum()
    total_savings = filt_daily["estimated_savings_eur"].sum()
    avg_price = filt_daily["avg_price_eur_mwh"].mean()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Kütetunde kokku", f"{total_heating} h")
    col2.metric("Ventilatsioonitunde kokku", f"{total_ventilation} h")
    col3.metric("Reeglipõhine kulu", f"{total_rule_cost:.3f} €")
    col4.metric("Hinnanguline sääst", f"{total_savings:.3f} €")
    col5.metric("Keskmine börsihind", f"{avg_price:.1f} €/MWh")

# ------------------------------------------------------------------
# KPI 1: Tunnipõhine otsus – kalender (action_needed)
# ------------------------------------------------------------------
st.subheader("KPI 1 – Kütte- ja ventilatsioonitunnid")

for loc in selected_locations:
    loc_data = filt_hourly[filt_hourly["location_name"] == loc].copy()
    if loc_data.empty:
        continue
    day_count = loc_data["forecast_date_label"].nunique()
    chart = (
        alt.Chart(loc_data)
        .mark_rect(stroke="white", strokeWidth=0.5)
        .encode(
            x=alt.X("forecast_hour:O", title="Tund",
                    axis=alt.Axis(labelAngle=0, values=[0, 3, 6, 9, 12, 15, 18, 21])),
            y=alt.Y("forecast_date_label:N", title="Päev",
                    sort=alt.SortField("forecast_time", order="ascending")),
            color=action_color(),
            tooltip=[
                alt.Tooltip("forecast_time:T", title="Aeg"),
                alt.Tooltip("temperature_c:Q", title="Välistemp °C", format=".1f"),
                alt.Tooltip("estimated_inside_temp_c:Q", title="Hinn. sisetemp °C", format=".1f"),
                alt.Tooltip("action_needed:N", title="Olek"),
                alt.Tooltip("price_eur_mwh:Q", title="Börsihind €/MWh", format=".2f"),
                alt.Tooltip("main_reason:N", title="Põhjus"),
            ],
        )
        .properties(title=loc, height=max(120, 30 * day_count))
    )
    st.altair_chart(chart, use_container_width=True)

# ------------------------------------------------------------------
# KPI 2: Börsihind tundide kaupa + action värviga
# ------------------------------------------------------------------
st.subheader("KPI 2 – Börsihind kütte- ja ventilatsioonitundidel")

detail_data = filt_hourly[filt_hourly["location_name"] == detail_location].copy()
if not detail_data.empty:
    price_chart = (
        alt.Chart(detail_data)
        .mark_bar()
        .encode(
            x=alt.X("forecast_time:T", title=None),
            y=alt.Y("price_eur_mwh:Q", title="Börsihind €/MWh"),
            color=action_color(),
            tooltip=[
                alt.Tooltip("forecast_time:T", title="Aeg"),
                alt.Tooltip("price_eur_mwh:Q", title="Börsihind €/MWh", format=".2f"),
                alt.Tooltip("action_needed:N", title="Olek"),
                alt.Tooltip("estimated_inside_temp_c:Q", title="Hinn. sisetemp °C", format=".1f"),
            ],
        )
        .properties(height=220, title=f"Börsihind tunni kaupa – {detail_location}")
    )
    st.altair_chart(price_chart, use_container_width=True)

# ------------------------------------------------------------------
# KPI 3: Päevane kulu – reeglipõhine vs pidev tarbimine
# ------------------------------------------------------------------
st.subheader("KPI 3 – Päevane kulu: reeglipõhine vs pidev tarbimine")

if not filt_daily.empty:
    filt_daily["Kuupäev"] = filt_daily["forecast_date"].dt.strftime("%d.%m")
    cost_data = filt_daily.melt(
        id_vars=["location_name", "forecast_date", "Kuupäev"],
        value_vars=["rule_based_cost_eur", "avg_price_cost_eur"],
        var_name="kulu_tüüp",
        value_name="kulu_eur",
    )
    cost_data["kulu_tüüp"] = cost_data["kulu_tüüp"].map({
        "rule_based_cost_eur": "Reeglipõhine kulu",
        "avg_price_cost_eur": "Pidev tarbimine",
    })
    cost_data["kulu_eur"] = pd.to_numeric(cost_data["kulu_eur"], errors="coerce")

    cost_chart = (
        alt.Chart(cost_data[cost_data["location_name"] == detail_location])
        .mark_bar()
        .encode(
            x=alt.X("Kuupäev:N", title="Kuupäev"),
            y=alt.Y("kulu_eur:Q", title="Kulu (€)", scale=alt.Scale(zero=True)),
            color=alt.Color("kulu_tüüp:N", title="Tarbimisviis",
                            scale=alt.Scale(
                                domain=["Reeglipõhine kulu", "Pidev tarbimine"],
                                range=["#2f9e44", "#adb5bd"]
                            )),
            xOffset="kulu_tüüp:N",
            tooltip=[
                alt.Tooltip("Kuupäev:N", title="Kuupäev"),
                alt.Tooltip("kulu_tüüp:N", title="Tarbimisviis"),
                alt.Tooltip("kulu_eur:Q", title="Kulu €", format=".4f"),
            ],
        )
        .properties(height=220, title=f"Päevane energiakulu – {detail_location}")
    )
    st.altair_chart(cost_chart, use_container_width=True)

    # Päevakoond tabel
    st.dataframe(
        filt_daily[[
            "location_name", "forecast_date", "heating_hours", "ventilation_hours",
            "avg_price_eur_mwh", "rule_based_cost_eur", "avg_price_cost_eur",
            "estimated_savings_eur", "weather_risk_level",
        ]].rename(columns={
            "location_name": "Asukoht",
            "forecast_date": "Kuupäev",
            "heating_hours": "Kütetunde",
            "ventilation_hours": "Vent. tunde",
            "avg_price_eur_mwh": "Kesk. hind €/MWh",
            "rule_based_cost_eur": "Reeglipõhine kulu €",
            "avg_price_cost_eur": "Pidev tarbimine €",
            "estimated_savings_eur": "Sääst €",
            "weather_risk_level": "Energiavajadus",
        }),
        use_container_width=True,
        hide_index=True,
    )

# ------------------------------------------------------------------
# Odavaimad 3h ajaaknad kütteks/ventilatsiooniks
# ------------------------------------------------------------------
st.subheader("Odavaimad 3h ajaaknad seadme käitamiseks")

if not filt_windows.empty:
    filt_windows["Aken"] = (
        filt_windows["window_start"].dt.strftime("%d.%m %H:%M")
        + "–"
        + filt_windows["window_end"].dt.strftime("%H:%M")
    )
    st.dataframe(
        filt_windows.head(15)[[
            "location_name", "county", "Aken",
            "avg_temperature_c", "avg_price_eur_mwh",
            "heating_hours", "ventilation_hours",
            "recommendation_label", "main_reason",
        ]].rename(columns={
            "location_name": "Asukoht",
            "county": "Maakond",
            "avg_temperature_c": "Kesk. temp °C",
            "avg_price_eur_mwh": "Kesk. hind €/MWh",
            "heating_hours": "Kütetunde",
            "ventilation_hours": "Vent. tunde",
            "recommendation_label": "Soovitus",
            "main_reason": "Põhjus",
        }),
        use_container_width=True,
        hide_index=True,
    )

# ------------------------------------------------------------------
# Temperatuuri detailvaade
# ------------------------------------------------------------------
st.subheader(f"Temperatuur – {detail_location}")

if not detail_data.empty:
    temp_base = alt.Chart(detail_data)
    outside = temp_base.mark_line(color="#1f77b4", strokeWidth=2).encode(
        x=alt.X("forecast_time:T", title=None),
        y=alt.Y("temperature_c:Q", title="Temperatuur °C"),
        tooltip=[
            alt.Tooltip("forecast_time:T", title="Aeg"),
            alt.Tooltip("temperature_c:Q", title="Välistemp °C", format=".1f"),
            alt.Tooltip("estimated_inside_temp_c:Q", title="Hinn. sisetemp °C", format=".1f"),
        ],
    )
    inside = temp_base.mark_line(color="#e07b39", strokeWidth=2, strokeDash=[4, 2]).encode(
        x="forecast_time:T",
        y="estimated_inside_temp_c:Q",
    )
    rule_low = alt.Chart(pd.DataFrame({"y": [12]})).mark_rule(
        color="red", strokeDash=[3, 3], opacity=0.5
    ).encode(y="y:Q")
    rule_high = alt.Chart(pd.DataFrame({"y": [28]})).mark_rule(
        color="orange", strokeDash=[3, 3], opacity=0.5
    ).encode(y="y:Q")

    st.altair_chart(
        (outside + inside + rule_low + rule_high).properties(height=220),
        use_container_width=True,
    )
    st.caption("Sinine joon – välistemp | Oranž joon – hinnanguline sisetemp (välistemp + 5°C) | Punane piir – 12°C | Oranž piir – 28°C")

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
