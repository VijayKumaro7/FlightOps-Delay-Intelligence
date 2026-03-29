-- ============================================================
--  FlightOps Delay Intelligence — Schema: Core Tables
--  Database: MySQL 8.0+
--  Author: github.com/VijayKumaro7
-- ============================================================

CREATE DATABASE IF NOT EXISTS flightops;
USE flightops;

-- ─────────────────────────────────────────────
-- 1. AIRLINES
-- ─────────────────────────────────────────────
CREATE TABLE airlines (
    carrier_code    CHAR(2)      NOT NULL,
    carrier_name    VARCHAR(100) NOT NULL,
    country         VARCHAR(50)  DEFAULT 'USA',
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (carrier_code)
);

-- ─────────────────────────────────────────────
-- 2. AIRPORTS
-- ─────────────────────────────────────────────
CREATE TABLE airports (
    airport_code    CHAR(3)      NOT NULL,
    airport_name    VARCHAR(150) NOT NULL,
    city            VARCHAR(100) NOT NULL,
    state           CHAR(2),
    latitude        DECIMAL(9,6),
    longitude       DECIMAL(9,6),
    timezone        VARCHAR(50)  DEFAULT 'America/New_York',
    PRIMARY KEY (airport_code)
);

-- ─────────────────────────────────────────────
-- 3. ROUTES  (carrier + origin + dest pair)
-- ─────────────────────────────────────────────
CREATE TABLE routes (
    route_id        INT          NOT NULL AUTO_INCREMENT,
    carrier_code    CHAR(2)      NOT NULL,
    origin          CHAR(3)      NOT NULL,
    destination     CHAR(3)      NOT NULL,
    scheduled_mins  SMALLINT     NOT NULL COMMENT 'Scheduled flight duration in minutes',
    PRIMARY KEY (route_id),
    UNIQUE KEY uq_route (carrier_code, origin, destination),
    FOREIGN KEY (carrier_code)  REFERENCES airlines(carrier_code),
    FOREIGN KEY (origin)        REFERENCES airports(airport_code),
    FOREIGN KEY (destination)   REFERENCES airports(airport_code)
);

-- ─────────────────────────────────────────────
-- 4. FLIGHTS  (one row = one flight leg)
-- ─────────────────────────────────────────────
CREATE TABLE flights (
    flight_id           BIGINT       NOT NULL AUTO_INCREMENT,
    route_id            INT          NOT NULL,
    flight_date         DATE         NOT NULL,
    flight_number       VARCHAR(8)   NOT NULL,
    scheduled_dep       SMALLINT     NOT NULL COMMENT 'HHMM format e.g. 1430',
    scheduled_arr       SMALLINT     NOT NULL,
    actual_dep          SMALLINT,
    actual_arr          SMALLINT,
    dep_delay_mins      SMALLINT     DEFAULT 0 COMMENT 'Negative = early',
    arr_delay_mins      SMALLINT     DEFAULT 0,
    cancelled           TINYINT(1)   DEFAULT 0,
    diverted            TINYINT(1)   DEFAULT 0,
    -- Delay breakdown buckets (minutes)
    carrier_delay       SMALLINT     DEFAULT 0,
    weather_delay       SMALLINT     DEFAULT 0,
    nas_delay           SMALLINT     DEFAULT 0  COMMENT 'National Air System delay',
    security_delay      SMALLINT     DEFAULT 0,
    late_aircraft_delay SMALLINT     DEFAULT 0,
    distance_miles      SMALLINT,
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (flight_id),
    FOREIGN KEY (route_id) REFERENCES routes(route_id)
);

-- ─────────────────────────────────────────────
-- 5. SLA RULES  (threshold config per carrier)
-- ─────────────────────────────────────────────
CREATE TABLE sla_rules (
    rule_id             INT          NOT NULL AUTO_INCREMENT,
    carrier_code        CHAR(2),      -- NULL = applies to all carriers
    max_delay_rate_pct  DECIMAL(5,2) NOT NULL DEFAULT 15.00 COMMENT 'Max % of flights allowed to be delayed',
    min_flights_window  INT          NOT NULL DEFAULT 100   COMMENT 'Minimum flights needed to trigger evaluation',
    window_days         INT          NOT NULL DEFAULT 30    COMMENT 'Rolling window in days',
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                                     COMMENT 'Tracks when an SLA threshold was last changed',
    updated_by          VARCHAR(100) DEFAULT NULL           COMMENT 'User who last modified this rule',
    PRIMARY KEY (rule_id),
    FOREIGN KEY (carrier_code) REFERENCES airlines(carrier_code)
);

-- ─────────────────────────────────────────────
-- 6. SLA BREACH LOG  (populated by stored proc)
-- ─────────────────────────────────────────────
CREATE TABLE sla_breach_log (
    breach_id       INT          NOT NULL AUTO_INCREMENT,
    route_id        INT          NOT NULL,
    breach_date     DATE         NOT NULL,
    delay_rate_pct  DECIMAL(5,2) NOT NULL,
    total_flights   INT          NOT NULL,
    delayed_flights INT          NOT NULL,
    rule_id         INT          NOT NULL,
    resolved        TINYINT(1)   DEFAULT 0,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (breach_id),
    UNIQUE KEY uq_breach_route_date_rule (route_id, breach_date, rule_id)
                                         COMMENT 'Prevents duplicate breach records from concurrent procedure runs',
    FOREIGN KEY (route_id) REFERENCES routes(route_id),
    FOREIGN KEY (rule_id)  REFERENCES sla_rules(rule_id)
);

-- ─────────────────────────────────────────────
-- 7. AUDIT LOG  (populated by triggers)
-- ─────────────────────────────────────────────
CREATE TABLE audit_log (
    audit_id        BIGINT       NOT NULL AUTO_INCREMENT,
    table_name      VARCHAR(50)  NOT NULL,
    operation       ENUM('INSERT','UPDATE','DELETE') NOT NULL,
    record_id       BIGINT       NOT NULL,
    changed_by      VARCHAR(100) DEFAULT USER(),
    changed_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    old_values      JSON,
    new_values      JSON,
    PRIMARY KEY (audit_id)
);
