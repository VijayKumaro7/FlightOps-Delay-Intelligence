-- ============================================================
--  FlightOps Delay Intelligence — Stored Procedures
--  Database: MySQL 8.0+
-- ============================================================

USE flightops;
DELIMITER $$

-- ─────────────────────────────────────────────────────────
-- PROCEDURE 1: sp_flag_delayed_routes
--   Scans all routes over the last N days.
--   Inserts a breach record whenever a route's delay rate
--   exceeds the SLA threshold defined in sla_rules.
--   Idempotent: skips route/date combos already logged.
-- ─────────────────────────────────────────────────────────
CREATE PROCEDURE sp_flag_delayed_routes(
    IN  p_as_of_date   DATE,       -- Evaluation date (NULL = today)
    OUT p_breaches_found INT        -- How many new breaches inserted
)
BEGIN
    DECLARE v_eval_date DATE;
    DECLARE v_window    INT;
    DECLARE v_threshold DECIMAL(5,2);
    DECLARE v_min_flights INT;
    DECLARE v_rule_id   INT;

    -- Default to today if no date supplied
    SET v_eval_date = IFNULL(p_as_of_date, CURDATE());

    -- Pull default SLA rule (carrier_code IS NULL = global)
    SELECT rule_id, window_days, max_delay_rate_pct, min_flights_window
    INTO   v_rule_id, v_window, v_threshold, v_min_flights
    FROM   sla_rules
    WHERE  carrier_code IS NULL
    ORDER BY rule_id ASC
    LIMIT  1;

    -- ── Compute rolling delay rates and insert breaches ──
    INSERT INTO sla_breach_log
           (route_id, breach_date, delay_rate_pct,
            total_flights, delayed_flights, rule_id)
    SELECT
        r.route_id,
        v_eval_date                                                     AS breach_date,
        ROUND(100.0 * SUM(CASE WHEN f.arr_delay_mins >= 15
                          THEN 1 ELSE 0 END) / COUNT(*), 2)             AS delay_rate_pct,
        COUNT(*)                                                         AS total_flights,
        SUM(CASE WHEN f.arr_delay_mins >= 15 THEN 1 ELSE 0 END)         AS delayed_flights,
        v_rule_id
    FROM  flights f
    JOIN  routes  r ON f.route_id = r.route_id
    WHERE f.flight_date BETWEEN DATE_SUB(v_eval_date, INTERVAL v_window DAY)
                             AND v_eval_date
      AND f.cancelled = 0
    GROUP BY r.route_id
    HAVING
        COUNT(*) >= v_min_flights
        AND ROUND(100.0 * SUM(CASE WHEN f.arr_delay_mins >= 15
                              THEN 1 ELSE 0 END) / COUNT(*), 2) > v_threshold
        -- Idempotency guard
        AND NOT EXISTS (
            SELECT 1 FROM sla_breach_log bl
            WHERE  bl.route_id    = r.route_id
              AND  bl.breach_date = v_eval_date
        );

    SET p_breaches_found = ROW_COUNT();
END$$


-- ─────────────────────────────────────────────────────────
-- PROCEDURE 2: sp_monthly_scorecard
--   Returns a full performance scorecard for a given carrier
--   and month, including rank among all carriers that month.
-- ─────────────────────────────────────────────────────────
CREATE PROCEDURE sp_monthly_scorecard(
    IN p_carrier_code CHAR(2),
    IN p_year         INT,
    IN p_month        INT
)
BEGIN
    -- Validate inputs
    IF p_year  IS NULL OR p_month IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'p_year and p_month cannot be NULL';
    END IF;

    -- ── Carrier's scorecard for the month ──
    SELECT
        s.carrier_code,
        s.carrier_name,
        s.yr,
        s.mo,
        s.total_flights,
        s.cancelled_flights,
        s.delayed_flights,
        s.avg_arr_delay,
        s.delay_rate_pct,
        s.cancel_rate_pct,
        s.early_rate_pct,
        -- Rank among all carriers this month (lower delay_rate = better rank)
        RANK() OVER (
            PARTITION BY s.yr, s.mo
            ORDER BY s.delay_rate_pct ASC
        )  AS on_time_rank,
        -- Total carriers evaluated this month
        COUNT(*) OVER (PARTITION BY s.yr, s.mo) AS total_carriers_evaluated
    FROM  vw_carrier_monthly_scorecard s
    WHERE s.yr = p_year
      AND s.mo = p_month
      AND (p_carrier_code IS NULL OR s.carrier_code = p_carrier_code);

    -- ── Delay cause breakdown for the month ──
    SELECT
        a.carrier_code,
        a.carrier_name,
        ROUND(AVG(f.carrier_delay),       2) AS avg_carrier_delay,
        ROUND(AVG(f.weather_delay),       2) AS avg_weather_delay,
        ROUND(AVG(f.nas_delay),           2) AS avg_nas_delay,
        ROUND(AVG(f.security_delay),      2) AS avg_security_delay,
        ROUND(AVG(f.late_aircraft_delay), 2) AS avg_late_aircraft_delay,
        -- Dominant cause
        CASE
            WHEN AVG(f.carrier_delay)       = GREATEST(AVG(f.carrier_delay), AVG(f.weather_delay),
                                              AVG(f.nas_delay), AVG(f.late_aircraft_delay))
                THEN 'Carrier Operations'
            WHEN AVG(f.weather_delay)       = GREATEST(AVG(f.carrier_delay), AVG(f.weather_delay),
                                              AVG(f.nas_delay), AVG(f.late_aircraft_delay))
                THEN 'Weather'
            WHEN AVG(f.nas_delay)           = GREATEST(AVG(f.carrier_delay), AVG(f.weather_delay),
                                              AVG(f.nas_delay), AVG(f.late_aircraft_delay))
                THEN 'National Air System'
            ELSE 'Late Aircraft'
        END AS dominant_delay_cause
    FROM  flights  f
    JOIN  routes   r ON f.route_id    = r.route_id
    JOIN  airlines a ON r.carrier_code = a.carrier_code
    WHERE YEAR(f.flight_date)  = p_year
      AND MONTH(f.flight_date) = p_month
      AND (p_carrier_code IS NULL OR a.carrier_code = p_carrier_code)
      AND f.cancelled = 0
    GROUP BY a.carrier_code, a.carrier_name;
END$$


-- ─────────────────────────────────────────────────────────
-- PROCEDURE 3: sp_resolve_breach
--   Marks a breach record as resolved (used after airline
--   takes corrective action).
-- ─────────────────────────────────────────────────────────
CREATE PROCEDURE sp_resolve_breach(
    IN p_breach_id INT
)
BEGIN
    IF NOT EXISTS (SELECT 1 FROM sla_breach_log WHERE breach_id = p_breach_id) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Breach ID not found';
    END IF;

    UPDATE sla_breach_log
    SET    resolved = 1
    WHERE  breach_id = p_breach_id;

    SELECT CONCAT('Breach #', p_breach_id, ' marked as resolved.') AS status;
END$$

DELIMITER ;
