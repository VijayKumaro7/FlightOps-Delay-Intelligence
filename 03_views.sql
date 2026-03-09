-- ============================================================
--  FlightOps Delay Intelligence — Schema: Views
-- ============================================================

USE flightops;

-- ─────────────────────────────────────────────────────────
-- VIEW 1: vw_flight_details
--   Denormalized flight + route + carrier + airports
--   Used as base for most analytical queries
-- ─────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_flight_details AS
SELECT
    f.flight_id,
    f.flight_date,
    f.flight_number,
    a.carrier_code,
    a.carrier_name,
    r.origin,
    ap_orig.city        AS origin_city,
    ap_orig.state       AS origin_state,
    r.destination,
    ap_dest.city        AS dest_city,
    ap_dest.state       AS dest_state,
    f.dep_delay_mins,
    f.arr_delay_mins,
    f.cancelled,
    f.diverted,
    f.carrier_delay,
    f.weather_delay,
    f.nas_delay,
    f.security_delay,
    f.late_aircraft_delay,
    f.distance_miles,
    -- Derived flags
    CASE WHEN f.arr_delay_mins >= 15 THEN 1 ELSE 0 END   AS is_delayed,
    CASE WHEN f.arr_delay_mins >= 60 THEN 1 ELSE 0 END   AS is_severely_delayed,
    CASE WHEN f.arr_delay_mins < 0   THEN 1 ELSE 0 END   AS is_early
FROM flights        f
JOIN routes         r       ON f.route_id        = r.route_id
JOIN airlines       a       ON r.carrier_code    = a.carrier_code
JOIN airports       ap_orig ON r.origin          = ap_orig.airport_code
JOIN airports       ap_dest ON r.destination     = ap_dest.airport_code;


-- ─────────────────────────────────────────────────────────
-- VIEW 2: vw_carrier_monthly_scorecard
--   Monthly on-time performance per carrier
-- ─────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_carrier_monthly_scorecard AS
SELECT
    carrier_code,
    carrier_name,
    YEAR(flight_date)                                        AS yr,
    MONTH(flight_date)                                       AS mo,
    COUNT(*)                                                 AS total_flights,
    SUM(cancelled)                                           AS cancelled_flights,
    SUM(is_delayed)                                          AS delayed_flights,
    SUM(is_severely_delayed)                                 AS severe_delays,
    ROUND(AVG(arr_delay_mins), 2)                            AS avg_arr_delay,
    ROUND(AVG(CASE WHEN is_delayed = 1
              THEN arr_delay_mins END), 2)                   AS avg_delay_when_late,
    ROUND(100.0 * SUM(is_delayed)  / COUNT(*), 2)            AS delay_rate_pct,
    ROUND(100.0 * SUM(cancelled)   / COUNT(*), 2)            AS cancel_rate_pct,
    ROUND(100.0 * SUM(is_early)    / COUNT(*), 2)            AS early_rate_pct
FROM  vw_flight_details
GROUP BY carrier_code, carrier_name, yr, mo;


-- ─────────────────────────────────────────────────────────
-- VIEW 3: vw_route_performance
--   Aggregated KPIs per route (all-time)
-- ─────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_route_performance AS
SELECT
    r.route_id,
    r.carrier_code,
    r.origin,
    r.destination,
    CONCAT(r.origin, ' → ', r.destination)                  AS route_label,
    COUNT(*)                                                 AS total_flights,
    ROUND(AVG(f.arr_delay_mins), 2)                          AS avg_arr_delay,
    ROUND(100.0 * SUM(CASE WHEN f.arr_delay_mins >= 15
                       THEN 1 ELSE 0 END) / COUNT(*), 2)    AS delay_rate_pct,
    ROUND(100.0 * SUM(f.cancelled) / COUNT(*), 2)            AS cancel_rate_pct,
    MAX(f.arr_delay_mins)                                    AS worst_delay,
    MIN(f.arr_delay_mins)                                    AS best_time
FROM flights  f
JOIN routes   r ON f.route_id = r.route_id
GROUP BY r.route_id, r.carrier_code, r.origin, r.destination;
