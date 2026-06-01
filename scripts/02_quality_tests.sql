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
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM mart.dim_location
                WHERE is_active
            )
                THEN 0
            ELSE 1
        END AS failed_rows,
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
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM staging.weather_hourly_raw AS w
                INNER JOIN latest_run AS r ON w.run_id = r.run_id
            )
                THEN 0
            ELSE 1
        END AS failed_rows,
        'Viimasel edukal laadimisel peab olema vähemalt üks ilmarida.' AS message

    UNION ALL

    SELECT
        'latest_run_has_active_locations' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Viimasel edukal laadimisel peavad olema kõik aktiivsed asukohad dimensioonitabelist.' AS message
    FROM mart.dim_location AS l
    LEFT JOIN latest_run AS r
        ON TRUE
    LEFT JOIN staging.weather_hourly_raw AS w
        ON r.run_id = w.run_id
       AND l.location_id = w.location_id
    WHERE l.is_active
      AND w.location_id IS NULL

    UNION ALL

    SELECT
        'forecast_time_not_null' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Prognoosi aeg ei tohi puududa.' AS message
    FROM staging.weather_hourly_raw AS w
    INNER JOIN latest_run AS r ON w.run_id = r.run_id
    WHERE w.forecast_time IS NULL

    UNION ALL

    SELECT
        'forecast_time_not_stale' AS test_name,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM staging.weather_hourly_raw AS w
                INNER JOIN latest_run AS r ON w.run_id = r.run_id
                WHERE w.forecast_time > NOW()
            ) THEN 0 ELSE 1
        END AS failed_rows,
        'Vähemalt mõni prognoositund peab olema tulevikus.' AS message

    UNION ALL

    SELECT
        'unique_location_time_per_run' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Sama käivituse, asukoha ja tunni kohta tohib olla üks rida.' AS message
    FROM (
        SELECT
            w.run_id,
            w.location_id,
            w.forecast_time,
            COUNT(*) AS row_count
        FROM staging.weather_hourly_raw AS w
        INNER JOIN latest_run AS r ON w.run_id = r.run_id
        GROUP BY
            w.run_id,
            w.location_id,
            w.forecast_time
        HAVING COUNT(*) > 1
    ) AS duplicates

    UNION ALL

    -- temperature_c on Open-Meteo vastuses alati olemas, NULL on päris viga
    SELECT
        'temperature_reasonable' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Temperatuur peab jääma vahemikku -50 kuni 50 kraadi.' AS message
    FROM staging.weather_hourly_raw AS w
    INNER JOIN latest_run AS r ON w.run_id = r.run_id
    WHERE w.temperature_c IS NULL
       OR w.temperature_c < -50
       OR w.temperature_c > 50

    UNION ALL

    -- Kontrollime ainult et vähemalt mõni tund on kaetud (API töötab).
    SELECT
        'price_coverage_exists' AS test_name,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM staging.weather_hourly_raw AS w
                INNER JOIN latest_run AS r ON w.run_id = r.run_id
                WHERE w.price_eur_mwh IS NOT NULL
            )
                THEN 0
            ELSE 1
        END AS failed_rows,
        'Vähemalt mõne tunni elektrihind peab olema olemas (Elering API).' AS message

    UNION ALL

    -- combined_score arvutatakse 01_transform.sql-is: max 30+35+25+10=100, min=0
    SELECT
        'combined_score_range' AS test_name,
        COUNT(*)::integer AS failed_rows,
        'Kombineeritud sobivuse skoor peab jääma vahemikku 0 kuni 100.' AS message
    FROM mart.hourly_weather_score AS h
    INNER JOIN latest_run AS r ON h.run_id = r.run_id
    WHERE h.combined_score < 0
       OR h.combined_score > 100

    UNION ALL
    
      SELECT
        'price_missing_share_under_20_pct' AS test_name,
        CASE
            WHEN (
                SELECT COUNT(*) FILTER (WHERE w.price_eur_mwh IS NULL)::float
                     / NULLIF(COUNT(*), 0)
                FROM staging.weather_hourly_raw AS w
                INNER JOIN latest_run AS r ON w.run_id = r.run_id
            ) > 0.20
                THEN 1
            ELSE 0
        END AS failed_rows,
        'Puuduva elektrihinnaga staging-ridu tohib viimases laadimises olla kuni 20%.' AS message
    UNION ALL
    
    SELECT
        'action_and_label_consistent' AS test_name,
        COUNT(*)::integer AS failed_rows,
    'action_needed ja suitability_label peavad omavahel vastama.' AS message
    FROM mart.hourly_weather_score AS h
    INNER JOIN latest_run AS r ON h.run_id = r.run_id
    WHERE NOT (
        (h.action_needed = 'heating'      AND h.suitability_label = 'Küte vajalik')
    OR (h.action_needed = 'ventilation'  AND h.suitability_label = 'Ventilatsioon vajalik')
    OR (h.action_needed = 'none'         AND h.suitability_label = 'Temperatuur sobiv')
    )

    UNION ALL

    SELECT
        'mart_daily_summary_has_rows' AS test_name,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM mart.latest_daily_weather_summary
            )
                THEN 0
            ELSE 1
        END AS failed_rows,
        'Päevane koondtabel peab sisaldama näidikulaua ridu.' AS message

    UNION ALL

SELECT
    'mart_hourly_score_has_rows' AS test_name,
    CASE WHEN EXISTS (
        SELECT 1
        FROM mart.hourly_weather_score AS h
        INNER JOIN latest_run AS r ON h.run_id = r.run_id
    ) THEN 0 ELSE 1 END AS failed_rows,
    'Tunnipõhine skooride tabel peab sisaldama ridu.' AS message
)
INSERT INTO quality.test_results (
    test_name,
    status,
    failed_rows,
    message
)
SELECT
    test_name,
    CASE WHEN failed_rows = 0 THEN 'passed' ELSE 'failed' END AS status,
    failed_rows,
    message
FROM test_cases
ORDER BY test_name;
