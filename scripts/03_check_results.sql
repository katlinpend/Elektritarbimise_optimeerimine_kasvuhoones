SELECT
    run_id,
    fetched_at,
    source_name,
    forecast_days,
    status
FROM staging.pipeline_runs
ORDER BY fetched_at DESC
LIMIT 5;

SELECT
    location_id,
    location_name,
    county,
    latitude,
    longitude
FROM mart.dim_location
WHERE is_active
ORDER BY display_order, location_name;



SELECT
    test_name,
    status,
    failed_rows,
    message
FROM quality.test_results
ORDER BY test_name;