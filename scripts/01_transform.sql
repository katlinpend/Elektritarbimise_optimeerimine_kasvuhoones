TRUNCATE TABLE
    mart.outdoor_activity_windows,
    mart.hourly_weather_score,
    mart.daily_weather_summary,
    mart.fact_weather_forecast;

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

-- 3) 3h aknad
INSERT INTO mart.outdoor_activity_windows (
    run_id,
    location_id,
    location_name,
    window_start,
    window_end,
    duration_hours,
    avg_temperature_c,
    avg_price_eur_mwh,
    heating_hours,
    ventilation_hours,
    avg_combined_score,
    min_combined_score,
    recommendation_label,
    main_reason
)
WITH windows AS (
    SELECT
        h1.run_id,
        h1.location_id,
        h1.location_name,
        h1.forecast_time AS window_start,
        h1.forecast_time + INTERVAL '3 hours' AS window_end,
        COUNT(h2.forecast_time)::integer AS duration_hours,
        ROUND(AVG(h2.temperature_c), 2) AS avg_temperature_c,
        ROUND(AVG(h2.price_eur_mwh), 2) AS avg_price_eur_mwh,
        SUM(CASE WHEN h2.action_needed = 'heating' THEN 1 ELSE 0 END)::integer AS heating_hours,
        SUM(CASE WHEN h2.action_needed = 'ventilation' THEN 1 ELSE 0 END)::integer AS ventilation_hours,
        ROUND(AVG(h2.combined_score), 1) AS avg_combined_score,
        MIN(h2.combined_score)::integer AS min_combined_score
    FROM mart.hourly_weather_score h1
    JOIN mart.hourly_weather_score h2
      ON h1.run_id = h2.run_id
     AND h1.location_id = h2.location_id
     AND h2.forecast_time >= h1.forecast_time
     AND h2.forecast_time < h1.forecast_time + INTERVAL '3 hours'
    GROUP BY h1.run_id, h1.location_id, h1.location_name, h1.forecast_time
    HAVING COUNT(*) = 3
)
SELECT
    run_id,
    location_id,
    location_name,
    window_start,
    window_end,
    duration_hours,
    avg_temperature_c,
    avg_price_eur_mwh,
    heating_hours,
    ventilation_hours,
    avg_combined_score,
    min_combined_score,
    CASE
        WHEN heating_hours >= 2 THEN 'Kütmiseks sobiv aken'
        WHEN ventilation_hours >= 2 THEN 'Ventilatsiooniks sobiv aken'
        ELSE 'Temperatuur pigem stabiilne'
    END AS recommendation_label,
    CASE
        WHEN heating_hours >= 2 THEN 'Enamik aknast vajab kütet'
        WHEN ventilation_hours >= 2 THEN 'Enamik aknast vajab ventilatsiooni'
        ELSE 'Suurt sekkumist ei ole vaja'
    END AS main_reason
FROM windows;

-- 4) Päevakoond
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
    weather_risk_level
)
SELECT
    h.run_id,
    h.location_id,
    h.location_name,
    h.forecast_date,
    COUNT(*)::integer AS forecast_hours,
    ROUND(AVG(h.temperature_c), 2) AS avg_temp_c,
    MAX(h.temperature_c) AS max_temp_c,
    SUM(CASE WHEN h.action_needed = 'heating' THEN 1 ELSE 0 END)::integer AS heating_hours,
    SUM(CASE WHEN h.action_needed = 'ventilation' THEN 1 ELSE 0 END)::integer AS ventilation_hours,
    ROUND(AVG(h.price_eur_mwh), 2) AS avg_price_eur_mwh,
    CASE
        WHEN SUM(CASE WHEN h.action_needed IN ('heating', 'ventilation') THEN 1 ELSE 0 END) >= 12 THEN 'Kõrgem energiavajadus'
        WHEN SUM(CASE WHEN h.action_needed IN ('heating', 'ventilation') THEN 1 ELSE 0 END) >= 6 THEN 'Mõõdukas energiavajadus'
        ELSE 'Madal energiavajadus'
    END AS weather_risk_level
FROM mart.hourly_weather_score h
GROUP BY h.run_id, h.location_id, h.location_name, h.forecast_date;

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

CREATE OR REPLACE VIEW mart.latest_outdoor_activity_windows AS
SELECT w.*
FROM mart.outdoor_activity_windows w
JOIN mart.latest_pipeline_run r ON r.run_id = w.run_id;