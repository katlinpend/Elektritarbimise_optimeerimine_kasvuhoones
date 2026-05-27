TRUNCATE TABLE
    mart.hourly_weather_score,
    mart.daily_weather_summary,
    mart.fact_weather_forecast;

ALTER TABLE mart.hourly_weather_score
    ADD COLUMN IF NOT EXISTS price_eur_kwh numeric(10, 5);

ALTER TABLE mart.daily_weather_summary
    ADD COLUMN IF NOT EXISTS rule_based_cost_eur numeric(10, 2),
    ADD COLUMN IF NOT EXISTS avg_price_cost_eur numeric(10, 2),
    ADD COLUMN IF NOT EXISTS estimated_savings_eur numeric(10, 2);

-- 1) Fact: ainult temperatuur + hind
INSERT INTO mart.fact_weather_forecast (
    run_id,
    location_id,
    forecast_time,
    forecast_date,
    temperature_c,
    price_eur_mwh,
    fetched_at
)
SELECT
    run_id,
    location_id,
    forecast_time,
    forecast_time::date AS forecast_date,
    temperature_c,
    price_eur_mwh,
    fetched_at
FROM staging.weather_hourly_raw
WHERE price_eur_mwh IS NOT NULL;

-- 2) Tunnipõhine otsuseloogika
INSERT INTO mart.hourly_weather_score (
    run_id,
    location_id,
    location_name,
    forecast_time,
    forecast_date,
    forecast_hour,
    temperature_c,
    price_eur_mwh,
    price_eur_kwh,
    temperature_score,
    combined_score,
    suitability_label,
    main_reason,
    estimated_inside_temp_c,
    action_needed
)
WITH base AS (
    SELECT
        f.run_id,
        f.location_id,
        l.location_name,
        f.forecast_time,
        f.forecast_date,
        EXTRACT(HOUR FROM f.forecast_time)::integer AS forecast_hour,
        f.temperature_c,
        f.price_eur_mwh,
        ROUND((f.price_eur_mwh / 1000)::numeric, 5) AS price_eur_kwh,
        ROUND((f.temperature_c + 5)::numeric, 2) AS estimated_inside_temp_c
    FROM mart.fact_weather_forecast f
    JOIN mart.dim_location l ON l.location_id = f.location_id
),
scored AS (
    SELECT
        *,
        CASE
            WHEN estimated_inside_temp_c < 12 THEN 'heating'
            WHEN estimated_inside_temp_c > 28 THEN 'ventilation'
            ELSE 'none'
        END AS action_needed,
        CASE
            WHEN estimated_inside_temp_c < 12 THEN 40
            WHEN estimated_inside_temp_c > 28 THEN 40
            ELSE 100
        END AS temperature_score
    FROM base
)
SELECT
    run_id,
    location_id,
    location_name,
    forecast_time,
    forecast_date,
    forecast_hour,
    temperature_c,
    price_eur_mwh,
    price_eur_kwh,
    temperature_score,
    temperature_score AS combined_score,
    CASE
        WHEN action_needed = 'heating' THEN 'Küte vajalik'
        WHEN action_needed = 'ventilation' THEN 'Ventilatsioon vajalik'
        ELSE 'Temperatuur sobiv'
    END AS suitability_label,
    CASE
        WHEN action_needed = 'heating' THEN 'Hinnanguline sisetemperatuur alla 12°C'
        WHEN action_needed = 'ventilation' THEN 'Hinnanguline sisetemperatuur üle 28°C'
        ELSE 'Hinnanguline sisetemperatuur sobivas vahemikus'
    END AS main_reason,
    estimated_inside_temp_c,
    action_needed
FROM scored;


-- 4) Päevakoond
WITH hourly_costs AS (
    SELECT
        h.*,
        CASE
            WHEN h.action_needed IN ('heating', 'ventilation') THEN 5
            ELSE 0
        END AS rule_based_energy_kwh,
        5 AS continuous_energy_kwh
    FROM mart.hourly_weather_score h
),
daily_base AS (
    SELECT
        run_id,
        location_id,
        location_name,
        forecast_date,
        COUNT(*)::integer AS forecast_hours,
        ROUND(AVG(temperature_c), 2) AS avg_temp_c,
        MAX(temperature_c) AS max_temp_c,
        SUM(CASE WHEN action_needed = 'heating' THEN 1 ELSE 0 END)::integer AS heating_hours,
        SUM(CASE WHEN action_needed = 'ventilation' THEN 1 ELSE 0 END)::integer AS ventilation_hours,
        ROUND(AVG(price_eur_mwh), 2) AS avg_price_eur_mwh,
        ROUND(SUM(rule_based_energy_kwh * price_eur_kwh), 2) AS rule_based_cost_eur,
        ROUND(SUM(continuous_energy_kwh * price_eur_kwh), 2) AS avg_price_cost_eur,
        CASE
            WHEN SUM(CASE WHEN action_needed IN ('heating', 'ventilation') THEN 1 ELSE 0 END) >= 12
                THEN 'Kõrgem energiavajadus'
            WHEN SUM(CASE WHEN action_needed IN ('heating', 'ventilation') THEN 1 ELSE 0 END) >= 6
                THEN 'Mõõdukas energiavajadus'
            ELSE 'Madal energiavajadus'
        END AS weather_risk_level
    FROM hourly_costs
    GROUP BY
        run_id,
        location_id,
        location_name,
        forecast_date
)
INSERT INTO mart.daily_weather_summary (
    run_id,
    location_id,
    location_name,
    forecast_date,
    forecast_hours,
    avg_temp_c,
    max_temp_c,
    heating_hours,
    ventilation_hours,
    avg_price_eur_mwh,
    rule_based_cost_eur,
    avg_price_cost_eur,
    estimated_savings_eur,
    weather_risk_level
)
SELECT
    run_id,
    location_id,
    location_name,
    forecast_date,
    forecast_hours,
    avg_temp_c,
    max_temp_c,
    heating_hours,
    ventilation_hours,
    avg_price_eur_mwh,
    rule_based_cost_eur,
    avg_price_cost_eur,
    ROUND(avg_price_cost_eur - rule_based_cost_eur, 2) AS estimated_savings_eur,
    weather_risk_level
FROM daily_base;

-- latest views
CREATE OR REPLACE VIEW mart.latest_pipeline_run AS
SELECT
    run_id, fetched_at, source_name, forecast_days, status, message
FROM staging.pipeline_runs
WHERE status = 'success'
ORDER BY fetched_at DESC
LIMIT 1;

CREATE OR REPLACE VIEW mart.latest_weather_forecast AS
SELECT f.*
FROM mart.fact_weather_forecast f
JOIN mart.latest_pipeline_run r ON r.run_id = f.run_id;

CREATE OR REPLACE VIEW mart.latest_daily_weather_summary AS
SELECT d.*
FROM mart.daily_weather_summary d
JOIN mart.latest_pipeline_run r ON r.run_id = d.run_id;

CREATE OR REPLACE VIEW mart.latest_hourly_weather_score AS
SELECT h.*
FROM mart.hourly_weather_score h
JOIN mart.latest_pipeline_run r ON r.run_id = h.run_id;

