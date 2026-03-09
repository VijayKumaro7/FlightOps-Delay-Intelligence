-- ============================================================
--  FlightOps Delay Intelligence
--  Query: carrier_performance.sql
--  Goal: Rank all carriers by on-time performance with
--        month-over-month trend and delay cause analysis.
-- ============================================================

USE flightops;

-- ─────────────────────────────────────────────────────────
-- Q1: Carrier Rankings — last 12 months
--     Uses RANK() window function and CTE chaining
-- ─────────────────────────────────────────────────────────
WITH base AS (
    SELECT
        a.carrier_code,
        a.carrier_name,
        COUNT(*)                                                          AS total_flights,
        SUM(f.cancelled)                                                  AS cancelled,
        SUM(CASE WHEN f.arr_delay_mins >= 15 THEN 1 ELSE 0 END)          AS delayed,
        ROUND(AVG(f.arr_delay_mins), 2)                                   AS avg_delay,
        ROUND(AVG(CASE WHEN f.arr_delay_mins >= 15
                  THEN f.arr_delay_mins END), 2)                          AS avg_delay_when_late,
        SUM(CASE WHEN f.arr_delay_mins >= 60 THEN 1 ELSE 0 END)          AS severe_delays
    FROM  flights  f
    JOIN  routes   r ON f.route_id    = r.route_id
    JOIN  airlines a ON r.carrier_code = a.carrier_code
    WHERE f.flight_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
      AND f.cancelled   = 0
    GROUP BY a.carrier_code, a.carrier_name
),
ranked AS (
    SELECT
        *,
        ROUND(100.0 * delayed / total_flights, 2)        AS delay_rate_pct,
        ROUND(100.0 * cancelled / total_flights, 2)      AS cancel_rate_pct,
        RANK() OVER (ORDER BY (delayed / total_flights) ASC) AS on_time_rank,
        PERCENT_RANK() OVER (ORDER BY (delayed / total_flights) ASC) AS percentile
    FROM base
)
SELECT
    on_time_rank,
    carrier_code,
    carrier_name,
    total_flights,
    delayed,
    severe_delays,
    avg_delay       AS avg_arr_delay_mins,
    avg_delay_when_late,
    delay_rate_pct,
    cancel_rate_pct,
    ROUND(percentile * 100, 1)  AS percentile_rank
FROM ranked
ORDER BY on_time_rank;


-- ─────────────────────────────────────────────────────────
-- Q2: Month-over-Month Delay Trend per Carrier
--     Uses LAG() to compute MoM change
-- ─────────────────────────────────────────────────────────
WITH monthly AS (
    SELECT
        a.carrier_code,
        a.carrier_name,
        DATE_FORMAT(f.flight_date, '%Y-%m')                               AS month_label,
        ROUND(100.0 * SUM(CASE WHEN f.arr_delay_mins >= 15
                          THEN 1 ELSE 0 END) / COUNT(*), 2)              AS delay_rate_pct
    FROM  flights  f
    JOIN  routes   r ON f.route_id    = r.route_id
    JOIN  airlines a ON r.carrier_code = a.carrier_code
    WHERE f.cancelled = 0
    GROUP BY a.carrier_code, a.carrier_name, month_label
)
SELECT
    carrier_code,
    carrier_name,
    month_label,
    delay_rate_pct,
    LAG(delay_rate_pct) OVER (PARTITION BY carrier_code ORDER BY month_label) AS prev_month_rate,
    ROUND(delay_rate_pct -
          LAG(delay_rate_pct) OVER (PARTITION BY carrier_code ORDER BY month_label), 2)
                                                                               AS mom_change_pct,
    CASE
        WHEN delay_rate_pct >
             LAG(delay_rate_pct) OVER (PARTITION BY carrier_code ORDER BY month_label)
        THEN '📈 Worsening'
        WHEN delay_rate_pct <
             LAG(delay_rate_pct) OVER (PARTITION BY carrier_code ORDER BY month_label)
        THEN '📉 Improving'
        ELSE '➡ Flat'
    END AS trend
FROM monthly
ORDER BY carrier_code, month_label;


-- ─────────────────────────────────────────────────────────
-- Q3: Delay Root Cause Breakdown
--     What % of total delay minutes comes from each cause?
-- ─────────────────────────────────────────────────────────
SELECT
    a.carrier_code,
    a.carrier_name,
    SUM(f.carrier_delay)                                            AS total_carrier_mins,
    SUM(f.weather_delay)                                            AS total_weather_mins,
    SUM(f.nas_delay)                                                AS total_nas_mins,
    SUM(f.security_delay)                                           AS total_security_mins,
    SUM(f.late_aircraft_delay)                                      AS total_late_aircraft_mins,
    SUM(f.carrier_delay + f.weather_delay + f.nas_delay
      + f.security_delay + f.late_aircraft_delay)                   AS grand_total_delay_mins,
    -- % breakdown
    ROUND(100.0 * SUM(f.carrier_delay)       /
          NULLIF(SUM(f.carrier_delay + f.weather_delay + f.nas_delay
               + f.security_delay + f.late_aircraft_delay), 0), 1) AS pct_carrier,
    ROUND(100.0 * SUM(f.weather_delay)       /
          NULLIF(SUM(f.carrier_delay + f.weather_delay + f.nas_delay
               + f.security_delay + f.late_aircraft_delay), 0), 1) AS pct_weather,
    ROUND(100.0 * SUM(f.nas_delay)           /
          NULLIF(SUM(f.carrier_delay + f.weather_delay + f.nas_delay
               + f.security_delay + f.late_aircraft_delay), 0), 1) AS pct_nas,
    ROUND(100.0 * SUM(f.late_aircraft_delay) /
          NULLIF(SUM(f.carrier_delay + f.weather_delay + f.nas_delay
               + f.security_delay + f.late_aircraft_delay), 0), 1) AS pct_late_aircraft
FROM  flights  f
JOIN  routes   r ON f.route_id    = r.route_id
JOIN  airlines a ON r.carrier_code = a.carrier_code
WHERE f.cancelled = 0
GROUP BY a.carrier_code, a.carrier_name
ORDER BY grand_total_delay_mins DESC;
