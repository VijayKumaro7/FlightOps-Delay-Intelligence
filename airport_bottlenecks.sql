-- ============================================================
--  FlightOps Delay Intelligence
--  Query: airport_bottlenecks.sql
--  Goal: Find which airports generate the most outbound
--        and inbound delays — useful for ops teams and
--        investors evaluating airport capacity.
-- ============================================================

USE flightops;

-- ─────────────────────────────────────────────────────────
-- Q1: Top 20 Most Delay-Prone Airports (Departure side)
--     Ranked by average departure delay
-- ─────────────────────────────────────────────────────────
WITH dep_stats AS (
    SELECT
        r.origin                                                         AS airport_code,
        ap.airport_name,
        ap.city,
        ap.state,
        COUNT(*)                                                         AS total_departures,
        ROUND(AVG(f.dep_delay_mins), 2)                                  AS avg_dep_delay,
        ROUND(100.0 * SUM(CASE WHEN f.dep_delay_mins >= 15
                          THEN 1 ELSE 0 END) / COUNT(*), 2)             AS dep_delay_rate_pct,
        MAX(f.dep_delay_mins)                                            AS worst_dep_delay,
        SUM(CASE WHEN f.dep_delay_mins >= 60 THEN 1 ELSE 0 END)         AS extreme_delays
    FROM  flights  f
    JOIN  routes   r  ON f.route_id    = r.route_id
    JOIN  airports ap ON r.origin      = ap.airport_code
    WHERE f.cancelled = 0
    GROUP BY r.origin, ap.airport_name, ap.city, ap.state
    HAVING total_departures >= 50   -- Filter out tiny airports
)
SELECT
    DENSE_RANK() OVER (ORDER BY avg_dep_delay DESC) AS delay_rank,
    airport_code,
    airport_name,
    city,
    state,
    total_departures,
    avg_dep_delay,
    dep_delay_rate_pct,
    worst_dep_delay,
    extreme_delays
FROM dep_stats
ORDER BY avg_dep_delay DESC
LIMIT 20;


-- ─────────────────────────────────────────────────────────
-- Q2: Airports Where Delays PROPAGATE (Late Aircraft Effect)
--     High late_aircraft_delay = delays cascading from upstream
-- ─────────────────────────────────────────────────────────
SELECT
    r.origin                                                             AS airport_code,
    ap.city,
    COUNT(*)                                                             AS flights_affected,
    ROUND(AVG(f.late_aircraft_delay), 2)                                 AS avg_late_aircraft_delay,
    ROUND(AVG(f.carrier_delay), 2)                                       AS avg_carrier_delay,
    ROUND(AVG(f.nas_delay), 2)                                           AS avg_nas_delay,
    -- Propagation ratio: how much of the delay is due to incoming aircraft
    ROUND(AVG(f.late_aircraft_delay) /
          NULLIF(AVG(f.arr_delay_mins), 0) * 100, 1)                    AS propagation_ratio_pct
FROM  flights  f
JOIN  routes   r  ON f.route_id = r.route_id
JOIN  airports ap ON r.origin   = ap.airport_code
WHERE f.late_aircraft_delay > 0
  AND f.cancelled = 0
GROUP BY r.origin, ap.city
HAVING flights_affected >= 30
ORDER BY propagation_ratio_pct DESC
LIMIT 15;


-- ─────────────────────────────────────────────────────────
-- Q3: Airport Pair Heat Map — Worst Origin→Dest Routes
--     Full route-level delay matrix
-- ─────────────────────────────────────────────────────────
SELECT
    r.origin,
    ap_o.city                                                            AS origin_city,
    r.destination,
    ap_d.city                                                            AS dest_city,
    COUNT(*)                                                             AS flights,
    ROUND(AVG(f.arr_delay_mins), 1)                                      AS avg_arr_delay,
    ROUND(100.0 * SUM(CASE WHEN f.arr_delay_mins >= 15
                      THEN 1 ELSE 0 END) / COUNT(*), 1)                 AS delay_rate_pct,
    -- Delay "budget" vs actual
    ROUND(AVG(f.arr_delay_mins) - AVG(r.scheduled_mins) * 0.05, 1)      AS delay_beyond_buffer
FROM  flights  f
JOIN  routes   r   ON f.route_id    = r.route_id
JOIN  airports ap_o ON r.origin      = ap_o.airport_code
JOIN  airports ap_d ON r.destination = ap_d.airport_code
WHERE f.cancelled = 0
GROUP BY r.origin, ap_o.city, r.destination, ap_d.city
HAVING flights >= 20
ORDER BY avg_arr_delay DESC
LIMIT 25;


-- ─────────────────────────────────────────────────────────
-- Q4: Time-of-Day Delay Pattern per Airport
--     Are morning flights more on-time than evening?
-- ─────────────────────────────────────────────────────────
SELECT
    r.origin                                                             AS airport_code,
    CASE
        WHEN f.scheduled_dep BETWEEN 0    AND 559  THEN '12AM–6AM (Red-eye)'
        WHEN f.scheduled_dep BETWEEN 600  AND 959  THEN '6AM–10AM (Morning)'
        WHEN f.scheduled_dep BETWEEN 1000 AND 1359 THEN '10AM–2PM (Midday)'
        WHEN f.scheduled_dep BETWEEN 1400 AND 1759 THEN '2PM–6PM (Afternoon)'
        ELSE                                             '6PM–12AM (Evening)'
    END                                                                  AS time_slot,
    COUNT(*)                                                             AS flights,
    ROUND(AVG(f.dep_delay_mins), 2)                                      AS avg_dep_delay,
    ROUND(100.0 * SUM(CASE WHEN f.dep_delay_mins >= 15
                      THEN 1 ELSE 0 END) / COUNT(*), 2)                 AS delay_rate_pct
FROM  flights  f
JOIN  routes   r ON f.route_id = r.route_id
WHERE f.cancelled = 0
GROUP BY r.origin, time_slot
ORDER BY r.origin, avg_dep_delay DESC;
