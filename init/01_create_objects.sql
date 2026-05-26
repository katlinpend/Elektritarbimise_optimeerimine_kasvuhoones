CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS quality;

CREATE TABLE IF NOT EXISTS staging.pipeline_runs (
    run_id uuid PRIMARY KEY,
    fetched_at timestamptz NOT NULL,
    source_name text NOT NULL,
    forecast_days integer NOT NULL,
    status text NOT NULL,
    message text
);

CREATE TABLE IF NOT EXISTS staging.weather_hourly_raw (
    run_id uuid NOT NULL REFERENCES staging.pipeline_runs (run_id),
    location_id text NOT NULL,
    location_name text NOT NULL,
    latitude numeric(9, 4) NOT NULL,
    longitude numeric(9, 4) NOT NULL,
    forecast_time timestamp NOT NULL,
    temperature_c numeric(6, 2),
    price_eur_mwh numeric(10, 2),
    fetched_at timestamptz NOT NULL,
    source_url text NOT NULL,
    PRIMARY KEY (run_id, location_id, forecast_time)
);

CREATE TABLE IF NOT EXISTS mart.dim_location (
    location_id text PRIMARY KEY,
    location_name text NOT NULL,
    country text NOT NULL,
    county text NOT NULL,
    location_type text NOT NULL,
    latitude numeric(9, 4) NOT NULL,
    longitude numeric(9, 4) NOT NULL,
    display_order integer NOT NULL,
    is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS mart.fact_weather_forecast (
    run_id uuid NOT NULL,
    location_id text NOT NULL REFERENCES mart.dim_location (location_id),
    forecast_time timestamp NOT NULL,
    forecast_date date NOT NULL,
    temperature_c numeric(6, 2),
    price_eur_mwh numeric(10, 2),
    fetched_at timestamptz NOT NULL,
    PRIMARY KEY (run_id, location_id, forecast_time)
);

CREATE TABLE IF NOT EXISTS mart.hourly_weather_score (
    run_id uuid NOT NULL,
    location_id text NOT NULL REFERENCES mart.dim_location (location_id),
    location_name text NOT NULL,
    forecast_time timestamp NOT NULL,
    forecast_date date NOT NULL,
    forecast_hour integer NOT NULL,
    temperature_c numeric(6, 2),
    price_eur_mwh numeric(10, 2),
    price_eur_kwh numeric(10, 5),
    temperature_score integer NOT NULL,
    combined_score integer NOT NULL,
    suitability_label text NOT NULL,
    main_reason text NOT NULL,
    estimated_inside_temp_c numeric(6, 2) NOT NULL,
    action_needed text NOT NULL,
    PRIMARY KEY (run_id, location_id, forecast_time)
);

CREATE TABLE IF NOT EXISTS mart.outdoor_activity_windows (
    run_id uuid NOT NULL,
    location_id text NOT NULL REFERENCES mart.dim_location (location_id),
    location_name text NOT NULL,
    window_start timestamp NOT NULL,
    window_end timestamp NOT NULL,
    duration_hours integer NOT NULL,
    avg_temperature_c numeric(6, 2),
    avg_price_eur_mwh numeric(10, 2),
    heating_hours integer NOT NULL,
    ventilation_hours integer NOT NULL,
    avg_combined_score numeric(5, 1) NOT NULL,
    min_combined_score integer NOT NULL,
    recommendation_label text NOT NULL,
    main_reason text NOT NULL,
    PRIMARY KEY (run_id, location_id, window_start)
);

CREATE TABLE IF NOT EXISTS mart.daily_weather_summary (
    run_id uuid NOT NULL,
    location_id text NOT NULL REFERENCES mart.dim_location (location_id),
    location_name text NOT NULL,
    forecast_date date NOT NULL,
    forecast_hours integer NOT NULL,
    avg_temp_c numeric(6, 2),
    max_temp_c numeric(6, 2),
    heating_hours integer NOT NULL,
    ventilation_hours integer NOT NULL,
    avg_price_eur_mwh numeric(10, 2),

    rule_based_cost_eur numeric(10, 2),
    avg_price_cost_eur numeric(10, 2),
    estimated_savings_eur numeric(10, 2),

    weather_risk_level text NOT NULL,
    PRIMARY KEY (run_id, location_id, forecast_date)
);

CREATE TABLE IF NOT EXISTS quality.test_results (
    test_run_at timestamptz NOT NULL DEFAULT now(),
    test_name text NOT NULL,
    status text NOT NULL,
    failed_rows integer NOT NULL,
    message text NOT NULL
);

CREATE OR REPLACE VIEW mart.latest_pipeline_run AS
SELECT
    run_id,
    fetched_at,
    source_name,
    forecast_days,
    status,
    message
FROM staging.pipeline_runs
WHERE status = 'success'
ORDER BY fetched_at DESC
LIMIT 1;

CREATE OR REPLACE VIEW mart.latest_weather_forecast AS
SELECT f.*
FROM mart.fact_weather_forecast AS f
INNER JOIN mart.latest_pipeline_run AS r
    ON f.run_id = r.run_id;

CREATE OR REPLACE VIEW mart.latest_daily_weather_summary AS
SELECT d.*
FROM mart.daily_weather_summary AS d
INNER JOIN mart.latest_pipeline_run AS r
    ON d.run_id = r.run_id;

CREATE OR REPLACE VIEW mart.latest_hourly_weather_score AS
SELECT h.*
FROM mart.hourly_weather_score AS h
INNER JOIN mart.latest_pipeline_run AS r
    ON h.run_id = r.run_id;

CREATE OR REPLACE VIEW mart.latest_outdoor_activity_windows AS
SELECT w.*
FROM mart.outdoor_activity_windows AS w
INNER JOIN mart.latest_pipeline_run AS r
    ON w.run_id = r.run_id;