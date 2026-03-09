-- ============================================================
--  FlightOps Delay Intelligence — Triggers
--  Database: MySQL 8.0+
-- ============================================================

USE flightops;
DELIMITER $$

-- ─────────────────────────────────────────────────────────
-- TRIGGER 1: trg_flights_after_insert
--   Writes to audit_log whenever a new flight is recorded.
-- ─────────────────────────────────────────────────────────
CREATE TRIGGER trg_flights_after_insert
AFTER INSERT ON flights
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, operation, record_id, new_values)
    VALUES (
        'flights',
        'INSERT',
        NEW.flight_id,
        JSON_OBJECT(
            'flight_date',   NEW.flight_date,
            'flight_number', NEW.flight_number,
            'route_id',      NEW.route_id,
            'dep_delay',     NEW.dep_delay_mins,
            'arr_delay',     NEW.arr_delay_mins,
            'cancelled',     NEW.cancelled
        )
    );
END$$


-- ─────────────────────────────────────────────────────────
-- TRIGGER 2: trg_flights_after_update
--   Captures before/after snapshot on flight updates.
--   Only fires when delay-relevant columns change.
-- ─────────────────────────────────────────────────────────
CREATE TRIGGER trg_flights_after_update
AFTER UPDATE ON flights
FOR EACH ROW
BEGIN
    -- Only audit if delay-sensitive fields changed
    IF OLD.arr_delay_mins  <> NEW.arr_delay_mins
    OR OLD.dep_delay_mins  <> NEW.dep_delay_mins
    OR OLD.cancelled       <> NEW.cancelled
    OR OLD.diverted        <> NEW.diverted
    THEN
        INSERT INTO audit_log
               (table_name, operation, record_id, old_values, new_values)
        VALUES (
            'flights',
            'UPDATE',
            NEW.flight_id,
            JSON_OBJECT(
                'arr_delay', OLD.arr_delay_mins,
                'dep_delay', OLD.dep_delay_mins,
                'cancelled', OLD.cancelled,
                'diverted',  OLD.diverted
            ),
            JSON_OBJECT(
                'arr_delay', NEW.arr_delay_mins,
                'dep_delay', NEW.dep_delay_mins,
                'cancelled', NEW.cancelled,
                'diverted',  NEW.diverted
            )
        );
    END IF;
END$$


-- ─────────────────────────────────────────────────────────
-- TRIGGER 3: trg_sla_breach_after_insert
--   Auto-sends a structured alert payload into audit_log
--   whenever a new SLA breach is logged.
--   (In production, an event-driven system would consume this)
-- ─────────────────────────────────────────────────────────
CREATE TRIGGER trg_sla_breach_after_insert
AFTER INSERT ON sla_breach_log
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, operation, record_id, new_values)
    VALUES (
        'sla_breach_log',
        'INSERT',
        NEW.breach_id,
        JSON_OBJECT(
            'event',          'SLA_BREACH_DETECTED',
            'route_id',       NEW.route_id,
            'breach_date',    NEW.breach_date,
            'delay_rate_pct', NEW.delay_rate_pct,
            'total_flights',  NEW.total_flights,
            'delayed_flights', NEW.delayed_flights,
            'severity',       CASE
                                  WHEN NEW.delay_rate_pct >= 30 THEN 'CRITICAL'
                                  WHEN NEW.delay_rate_pct >= 20 THEN 'HIGH'
                                  ELSE 'MEDIUM'
                              END
        )
    );
END$$


-- ─────────────────────────────────────────────────────────
-- TRIGGER 4: trg_validate_delay_values
--   Prevents invalid delay data at database layer.
--   Fires BEFORE INSERT on flights.
-- ─────────────────────────────────────────────────────────
CREATE TRIGGER trg_validate_delay_values
BEFORE INSERT ON flights
FOR EACH ROW
BEGIN
    -- Delay components must not exceed total arrival delay
    IF (IFNULL(NEW.carrier_delay, 0)
      + IFNULL(NEW.weather_delay, 0)
      + IFNULL(NEW.nas_delay, 0)
      + IFNULL(NEW.security_delay, 0)
      + IFNULL(NEW.late_aircraft_delay, 0)) > (NEW.arr_delay_mins + 10)
    THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT =
                'Delay component sum exceeds total arrival delay. Check data quality.';
    END IF;

    -- A cancelled flight cannot have actual departure/arrival times
    IF NEW.cancelled = 1 AND NEW.actual_dep IS NOT NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT =
                'Cancelled flights cannot have actual departure times.';
    END IF;
END$$

DELIMITER ;
