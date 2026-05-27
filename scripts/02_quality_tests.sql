TRUNCATE TABLE quality.test_results;

WITH latest_run AS (
    SELECT run_id
    FROM staging.pipeline_runs
    WHERE status = 'success'
    ORDER BY fetched_at DESC
    LIMIT 1
),
test_cases AS (
    SELECT
        'dim_location_has_active_rows' AS test_name,
        CASE WHEN EXISTS (
            SELECT 1 FROM mart.dim_location WHERE is_active
        ) THEN 0 ELSE 1 END AS failed_rows,
        'Asukohtade dimensioonis peab olema vähemalt üks aktiivne rida.' AS message

    UNION ALL

    SELECT
        'active_locations_have_coordinates' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Aktiivsetel asukohtadel peavad olema koordinaadid.' AS message
    FROM mart.dim_location
    WHERE is_active
      AND (
          latitude IS NULL
          OR longitude IS NULL
          OR latitude < 57
          OR latitude > 60
          OR longitude < 21
          OR longitude > 29
      )

    UNION ALL

    SELECT
        'weather_raw_has_rows' AS test_name,
        CASE WHEN EXISTS (
            SELECT 1
            FROM staging.weather_hourly_raw w
            JOIN latest_run r ON r.run_id = w.run_id
        ) THEN 0 ELSE 1 END AS failed_rows,
        'Viimasel edukal laadimisel peab olema vähemalt üks toorida.' AS message

    UNION ALL

    SELECT
        'latest_run_has_active_locations' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Viimasel edukal laadimisel peavad olema kõik aktiivsed asukohad.' AS message
    FROM mart.dim_location l
    LEFT JOIN latest_run r ON TRUE
    LEFT JOIN staging.weather_hourly_raw w
      ON w.run_id = r.run_id
     AND w.location_id = l.location_id
    WHERE l.is_active
      AND w.location_id IS NULL

    UNION ALL

    SELECT
        'forecast_time_not_null' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Prognoosi aeg ei tohi puududa.' AS message
    FROM staging.weather_hourly_raw w
    JOIN latest_run r ON r.run_id = w.run_id
    WHERE w.forecast_time IS NULL

    UNION ALL

    SELECT
        'unique_location_time_per_run' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Sama käivituse, asukoha ja tunni kohta tohib olla üks rida.' AS message
    FROM (
        SELECT w.run_id, w.location_id, w.forecast_time, COUNT(*) AS c
        FROM staging.weather_hourly_raw w
        JOIN latest_run r ON r.run_id = w.run_id
        GROUP BY w.run_id, w.location_id, w.forecast_time
        HAVING COUNT(*) > 1
    ) d

    UNION ALL

    SELECT
        'temperature_reasonable' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Temperatuur peab jääma vahemikku -50 kuni 50 kraadi.' AS message
    FROM staging.weather_hourly_raw w
    JOIN latest_run r ON r.run_id = w.run_id
    WHERE w.temperature_c IS NULL
       OR w.temperature_c < -50
       OR w.temperature_c > 50

    UNION ALL

    SELECT
    'price_not_null' AS test_name,
    COUNT(*)::integer AS failed_rows,
    'Mart tabelis ei tohi elektrihind olla NULL.' AS message
    FROM mart.fact_weather_forecast f
    JOIN latest_run r ON r.run_id = f.run_id
    WHERE f.price_eur_mwh IS NULL

    UNION ALL

    SELECT
        'action_label_valid' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'action_needed peab olema heating, ventilation või none.' AS message
    FROM mart.hourly_weather_score h
    JOIN latest_run r ON r.run_id = h.run_id
    WHERE h.action_needed NOT IN ('heating', 'ventilation', 'none')

    UNION ALL

    SELECT
        'mart_daily_summary_has_rows' AS test_name,
        CASE WHEN EXISTS (SELECT 1 FROM mart.latest_daily_weather_summary)
             THEN 0 ELSE 1 END AS failed_rows,
        'Päevane koondtabel peab sisaldama ridu.' AS message

    
)
INSERT INTO quality.test_results (test_name, status, failed_rows, message)
SELECT
    test_name,
    CASE WHEN failed_rows = 0 THEN 'passed' ELSE 'failed' END,
    failed_rows,
    message
FROM test_cases
ORDER BY test_name;