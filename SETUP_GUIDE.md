# 🛠️ FlightOps Delay Intelligence — Step-by-Step Build Guide

This guide walks you through building the project from zero — even if you've never
set up a MySQL project before. Follow each step in order.

---

## PHASE 1: Environment Setup

### Step 1 — Install MySQL 8.0

**Windows:**
```
Download MySQL Installer from: https://dev.mysql.com/downloads/installer/
Select: MySQL Server 8.0 + MySQL Workbench
```

**Mac (Homebrew):**
```bash
brew install mysql
brew services start mysql
mysql_secure_installation
```

**Linux (Ubuntu):**
```bash
sudo apt update
sudo apt install mysql-server
sudo mysql_secure_installation
sudo systemctl start mysql
```

### Step 2 — Install a SQL Client

Recommended: **DBeaver** (free, works on all OS)
- Download: https://dbeaver.io/download/
- Connect to: localhost:3306, user=root

### Step 3 — Install Python dependencies

```bash
pip install faker mysql-connector-python
```

---

## PHASE 2: Database Setup

### Step 4 — Clone the repo

```bash
git clone https://github.com/VijayKumaro7/flightops-sql.git
cd flightops-sql
```

### Step 5 — Create database and tables

```bash
mysql -u root -p < schema/01_tables.sql
```

You should see the `flightops` database created with 7 tables:
- airlines, airports, routes, flights
- sla_rules, sla_breach_log, audit_log

### Step 6 — Add indexes

```bash
mysql -u root -p flightops < schema/02_indexes.sql
```

### Step 7 — Create views

```bash
mysql -u root -p flightops < schema/03_views.sql
```

Verify: `SHOW FULL TABLES IN flightops WHERE TABLE_TYPE = 'VIEW';`
→ Should show 3 views: vw_flight_details, vw_carrier_monthly_scorecard, vw_route_performance

---

## PHASE 3: Stored Procedures & Triggers

### Step 8 — Load stored procedures

```bash
mysql -u root -p flightops < procedures/sp_flag_delayed_routes.sql
```

Verify: `SHOW PROCEDURE STATUS WHERE Db = 'flightops';`
→ Should show 3 procedures

### Step 9 — Load triggers

```bash
mysql -u root -p flightops < triggers/trg_audit_log.sql
```

Verify: `SHOW TRIGGERS IN flightops;`
→ Should show 4 triggers

---

## PHASE 4: Seed Data

### Step 10 — Generate 500K flight records

```bash
# Basic (default 500K rows):
python seed/seed_data.py --user root --password yourpassword

# Custom row count:
python seed/seed_data.py --rows 1000000 --user root --password yourpassword

# Custom host:
python seed/seed_data.py --host 192.168.1.100 --user myuser --password mypass
```

This takes ~3–5 minutes for 500K rows. You'll see progress printed.

### Step 11 — Verify data loaded

```sql
USE flightops;
SELECT COUNT(*) FROM flights;          -- Should be ~500,000
SELECT COUNT(*) FROM routes;           -- Should be ~80–100
SELECT COUNT(*) FROM airlines;         -- Should be 8
SELECT COUNT(*) FROM airports;         -- Should be 12
```

---

## PHASE 5: Run the Analytics

### Step 12 — Detect SLA breaches

```sql
USE flightops;

-- Insert a default SLA rule if not already seeded
INSERT IGNORE INTO sla_rules (carrier_code, max_delay_rate_pct, min_flights_window, window_days)
VALUES (NULL, 15.00, 100, 30);

-- Run the breach detector
SET @breaches = 0;
CALL sp_flag_delayed_routes(CURDATE(), @breaches);
SELECT CONCAT(@breaches, ' new SLA breaches detected') AS result;

-- View the breaches
SELECT * FROM sla_breach_log LIMIT 10;
```

### Step 13 — Generate a carrier scorecard

```sql
-- Scorecard for all carriers in a specific month
CALL sp_monthly_scorecard(NULL, 2023, 6);

-- Scorecard for a single carrier
CALL sp_monthly_scorecard('DL', 2023, 6);
```

### Step 14 — Run analytical queries

Open these files in DBeaver and run them one-by-one:

```bash
# Carrier rankings + MoM trend + delay root cause
queries/carrier_performance.sql

# Airport bottlenecks + propagation analysis
queries/airport_bottlenecks.sql

# SLA breach report + chronic offenders + compliance
queries/sla_breach_report.sql
```

### Step 15 — Test query optimizations

```sql
-- Open this file and run each BEFORE/AFTER block
-- Compare the "rows" column in EXPLAIN output
optimization/query_optimization.sql
```

For each pair, you should see a significant drop in `rows examined`.

---

## PHASE 6: Verify Triggers Work

### Step 16 — Test the audit log trigger

```sql
-- Insert a test flight (this will fire trg_flights_after_insert)
INSERT INTO flights (route_id, flight_date, flight_number, scheduled_dep,
                     scheduled_arr, dep_delay_mins, arr_delay_mins)
VALUES (1, CURDATE(), 'AA999', 800, 1000, 25, 30);

-- Check audit log
SELECT * FROM audit_log WHERE table_name = 'flights' ORDER BY audit_id DESC LIMIT 5;
```

### Step 17 — Test validation trigger

```sql
-- This should FAIL with our trg_validate_delay_values trigger:
INSERT INTO flights (route_id, flight_date, flight_number, scheduled_dep,
                     scheduled_arr, actual_dep, cancelled, dep_delay_mins, arr_delay_mins)
VALUES (1, CURDATE(), 'TEST001', 800, 1000, 830, 1, 30, 30);
-- Error: "Cancelled flights cannot have actual departure times."
```

---

## PHASE 7: GitHub Setup

### Step 18 — Push to GitHub

```bash
cd flightops-sql
git init
git add .
git commit -m "feat: initial FlightOps Delay Intelligence project"
git branch -M main
git remote add origin https://github.com/VijayKumaro7/flightops-sql.git
git push -u origin main
```

### Step 19 — Add topics to your GitHub repo

Go to your repo → Settings (gear icon near description) → Add topics:
```
sql mysql data-engineering analytics stored-procedures triggers window-functions portfolio
```

### Step 20 — Pin to your GitHub profile

Go to your GitHub profile → Customize profile → Pin this repository.

---

## 📸 Screenshot Checklist (for README)

Take screenshots of:
- [ ] ERD diagram from DBeaver (Database → Generate ER Diagram)
- [ ] EXPLAIN output showing index usage
- [ ] Sample output of sp_monthly_scorecard
- [ ] sla_breach_log with populated data
- [ ] audit_log showing trigger entries

Add these to `docs/` folder and reference in README.md.

---

## ✅ Done! What to say in interviews

> "I designed the schema to reflect real airline operations — flights, routes, carrier SLA contracts.
> The stored procedure scans a rolling 30-day window and automatically flags any route whose
> delay rate exceeds the SLA threshold, with an idempotency guard so it's safe to run daily.
> I also documented four query optimizations with EXPLAIN ANALYZE proof — the biggest win was
> rewriting a correlated subquery as a CTE pre-aggregation, which reduced rows examined by ~90%."
