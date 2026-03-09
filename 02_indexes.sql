-- ============================================================
--  FlightOps Delay Intelligence — Schema: Indexes
--  Purpose: Optimise analytical query patterns
-- ============================================================

USE flightops;

-- ─── flights: most queries filter by date range ───────────
ALTER TABLE flights ADD INDEX idx_flight_date         (flight_date);
ALTER TABLE flights ADD INDEX idx_route_date          (route_id, flight_date);
ALTER TABLE flights ADD INDEX idx_dep_delay           (dep_delay_mins);
ALTER TABLE flights ADD INDEX idx_arr_delay           (arr_delay_mins);
ALTER TABLE flights ADD INDEX idx_cancelled           (cancelled);
-- Composite: route performance queries
ALTER TABLE flights ADD INDEX idx_route_date_delay    (route_id, flight_date, arr_delay_mins);

-- ─── routes: joins to airlines/airports ───────────────────
ALTER TABLE routes  ADD INDEX idx_routes_carrier      (carrier_code);
ALTER TABLE routes  ADD INDEX idx_routes_origin       (origin);
ALTER TABLE routes  ADD INDEX idx_routes_dest         (destination);

-- ─── breach log: lookup by date / route ───────────────────
ALTER TABLE sla_breach_log ADD INDEX idx_breach_date  (breach_date);
ALTER TABLE sla_breach_log ADD INDEX idx_breach_route (route_id);
