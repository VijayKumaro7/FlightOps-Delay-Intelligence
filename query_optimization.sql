-- ============================================================
--  FlightOps Delay Intelligence
--  File: optimization/query_optimization.sql
--  Goal: Demonstrate EXPLAIN-proven query optimizations.
--        Run each BEFORE block, capture EXPLAIN output,
--        then run the AFTER block and compare.
-- ============================================================

USE flightops;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- OPTIMIZATION 1: Missing Index on flight_date
-- Problem: Full table scan on 3M rows for date range filter
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- ── BEFORE: Force full scan (drop index to demonstrate) ──
-- ALTER TABLE flights DROP INDEX idx_flight_date;
EXPLAIN SELECT COUNT(*), AVG(arr_delay_mins)
FROM   flights
WHERE  flight_date BETWEEN '2023-01-01' AND '2023-03-31';
-- Expected: type=ALL, rows≈3,000,000

-- ── AFTER: Index-assisted range scan ──
-- ALTER TABLE flights ADD INDEX idx_flight_date (flight_date);
EXPLAIN SELECT COUNT(*), AVG(arr_delay_mins)
FROM   flights
WHERE  flight_date BETWEEN '2023-01-01' AND '2023-03-31';
-- Expected: type=range, rows≈750,000 (75% reduction in rows examined)


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- OPTIMIZATION 2: Rewrite Correlated Subquery → JOIN
-- Problem: Correlated subquery executes once per row
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- ── BEFORE: Correlated subquery (slow) ──
EXPLAIN
SELECT f.flight_id, f.arr_delay_mins
FROM   flights f
WHERE  f.arr_delay_mins > (
           SELECT AVG(f2.arr_delay_mins)
           FROM   flights f2
           WHERE  f2.route_id = f.route_id   -- re-evaluated per row!
       )
  AND  f.flight_date >= '2023-01-01';

-- ── AFTER: Pre-aggregate with CTE, then JOIN ──
EXPLAIN
WITH route_avg AS (
    SELECT route_id, AVG(arr_delay_mins) AS avg_delay
    FROM   flights
    GROUP  BY route_id
)
SELECT f.flight_id, f.arr_delay_mins
FROM   flights    f
JOIN   route_avg  ra ON f.route_id = ra.route_id
WHERE  f.arr_delay_mins > ra.avg_delay
  AND  f.flight_date >= '2023-01-01';
-- Expected: CTE evaluated once; JOIN replaces per-row subquery.


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- OPTIMIZATION 3: EXISTS vs IN for semi-join
-- Problem: IN with large subquery builds full list in memory
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- ── BEFORE: IN subquery ──
EXPLAIN
SELECT carrier_code, carrier_name
FROM   airlines
WHERE  carrier_code IN (
           SELECT DISTINCT r.carrier_code
           FROM   routes  r
           JOIN   flights f ON r.route_id = f.route_id
           WHERE  f.arr_delay_mins >= 60
       );

-- ── AFTER: EXISTS (stops at first match) ──
EXPLAIN
SELECT a.carrier_code, a.carrier_name
FROM   airlines a
WHERE  EXISTS (
           SELECT 1
           FROM   routes  r
           JOIN   flights f ON r.route_id = f.route_id
           WHERE  r.carrier_code   = a.carrier_code   -- correlated, but stops early
             AND  f.arr_delay_mins >= 60
       );


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- OPTIMIZATION 4: Covering Index for scorecard query
-- Problem: Query hits main table data pages for every row
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- ── BEFORE: No covering index ──
EXPLAIN
SELECT route_id, flight_date, arr_delay_mins
FROM   flights
WHERE  route_id    = 42
  AND  flight_date >= '2023-01-01';

-- ── AFTER: Covering index (all needed columns in one index) ──
-- The index idx_route_date_delay(route_id, flight_date, arr_delay_mins)
-- already created in 02_indexes.sql covers this query completely.
EXPLAIN
SELECT route_id, flight_date, arr_delay_mins
FROM   flights
WHERE  route_id    = 42
  AND  flight_date >= '2023-01-01';
-- Expected: Extra = "Using index" → zero data page reads


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- OPTIMIZATION RESULTS SUMMARY  (record your actual numbers)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/*
| #  | Optimization          | Rows Examined Before | Rows Examined After | Speedup |
|----|-----------------------|----------------------|---------------------|---------|
| 1  | Add flight_date index | 3,000,000            | ~750,000            | ~75%    |
| 2  | CTE replaces subquery | 3,000,000 × N        | 3,000,000 + N       | ~90%    |
| 3  | EXISTS vs IN          | Full list in memory  | Early-exit          | ~40%    |
| 4  | Covering index        | Data+index pages     | Index only          | ~60%    |
*/
