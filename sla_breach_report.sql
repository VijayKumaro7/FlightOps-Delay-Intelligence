-- ============================================================
--  FlightOps Delay Intelligence
--  Query: sla_breach_report.sql
--  Goal: Dashboard-style SLA compliance report —
--        Which routes are chronically breaching SLA?
-- ============================================================

USE flightops;

-- ─────────────────────────────────────────────────────────
-- Q1: All Active (Unresolved) SLA Breaches
-- ─────────────────────────────────────────────────────────
SELECT
    bl.breach_id,
    bl.breach_date,
    CONCAT(r.origin, ' → ', r.destination)                              AS route,
    a.carrier_name,
    bl.total_flights,
    bl.delayed_flights,
    bl.delay_rate_pct,
    sr.max_delay_rate_pct                                               AS sla_threshold_pct,
    ROUND(bl.delay_rate_pct - sr.max_delay_rate_pct, 2)                 AS overage_pct,
    CASE
        WHEN bl.delay_rate_pct >= 30 THEN '🔴 CRITICAL'
        WHEN bl.delay_rate_pct >= 20 THEN '🟠 HIGH'
        ELSE                              '🟡 MEDIUM'
    END                                                                  AS severity,
    DATEDIFF(CURDATE(), bl.breach_date)                                  AS days_open
FROM  sla_breach_log bl
JOIN  routes         r  ON bl.route_id   = r.route_id
JOIN  airlines       a  ON r.carrier_code = a.carrier_code
JOIN  sla_rules      sr ON bl.rule_id    = sr.rule_id
WHERE bl.resolved = 0
ORDER BY bl.delay_rate_pct DESC;


-- ─────────────────────────────────────────────────────────
-- Q2: Chronic Offenders — Routes with Repeated Breaches
--     (3+ breaches in last 90 days = systemic problem)
-- ─────────────────────────────────────────────────────────
WITH breach_counts AS (
    SELECT
        route_id,
        COUNT(*)                                                         AS breach_count,
        MAX(delay_rate_pct)                                              AS peak_delay_rate,
        MIN(breach_date)                                                 AS first_breach,
        MAX(breach_date)                                                 AS latest_breach,
        ROUND(AVG(delay_rate_pct), 2)                                    AS avg_delay_rate
    FROM  sla_breach_log
    WHERE breach_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
    GROUP BY route_id
    HAVING breach_count >= 3
)
SELECT
    bc.breach_count,
    CONCAT(r.origin, ' → ', r.destination)                              AS route,
    a.carrier_name,
    bc.avg_delay_rate,
    bc.peak_delay_rate,
    bc.first_breach,
    bc.latest_breach,
    DATEDIFF(bc.latest_breach, bc.first_breach)                          AS breach_span_days,
    -- Classify chronic vs intermittent
    CASE
        WHEN bc.breach_count >= 6 THEN 'CHRONIC — Structural Issue'
        WHEN bc.breach_count >= 3 THEN 'RECURRING — Needs Monitoring'
        ELSE                           'INTERMITTENT'
    END                                                                  AS pattern
FROM  breach_counts bc
JOIN  routes        r  ON bc.route_id    = r.route_id
JOIN  airlines      a  ON r.carrier_code = a.carrier_code
ORDER BY bc.breach_count DESC, bc.avg_delay_rate DESC;


-- ─────────────────────────────────────────────────────────
-- Q3: SLA Compliance Rate by Carrier (Executive Summary)
-- ─────────────────────────────────────────────────────────
WITH carrier_routes AS (
    SELECT DISTINCT
        r.carrier_code,
        r.route_id
    FROM routes r
),
breached_routes AS (
    SELECT DISTINCT
        r.carrier_code,
        bl.route_id
    FROM  sla_breach_log bl
    JOIN  routes         r ON bl.route_id = r.route_id
    WHERE bl.breach_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
)
SELECT
    a.carrier_name,
    COUNT(cr.route_id)                                                   AS total_routes,
    COUNT(br.route_id)                                                   AS breached_routes,
    COUNT(cr.route_id) - COUNT(br.route_id)                             AS compliant_routes,
    ROUND(100.0 * (COUNT(cr.route_id) - COUNT(br.route_id))
                 / COUNT(cr.route_id), 1)                                AS sla_compliance_pct,
    CASE
        WHEN ROUND(100.0 * (COUNT(cr.route_id) - COUNT(br.route_id))
                          / COUNT(cr.route_id), 1) >= 90 THEN '✅ Meets SLA'
        WHEN ROUND(100.0 * (COUNT(cr.route_id) - COUNT(br.route_id))
                          / COUNT(cr.route_id), 1) >= 75 THEN '⚠️  At Risk'
        ELSE                                                   '❌ SLA Breach'
    END                                                                  AS sla_status
FROM  carrier_routes cr
JOIN  airlines       a  ON cr.carrier_code = a.carrier_code
LEFT  JOIN breached_routes br
      ON cr.carrier_code = br.carrier_code AND cr.route_id = br.route_id
GROUP BY a.carrier_name
ORDER BY sla_compliance_pct DESC;
