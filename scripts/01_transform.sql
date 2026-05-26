TRUNCATE TABLE
    mart.outdoor_activity_windows,
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

-- 3) 3h aknad
INSERT INTO mart.outdoor_activity_windows (
    run_id,
    location_id,
    location_name,
    window_start,
    window_end,
    duratio