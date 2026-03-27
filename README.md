# ✈️ FlightOps Delay Intelligence

> A MySQL-powered airline operations analytics system that detects SLA breaches, ranks carriers by on-time performance, and surfaces delay propagation patterns — built on real BTS (Bureau of Transportation Statistics) data structures.

[![MySQL](https://img.shields.io/badge/MySQL-8.0+-blue?logo=mysql)](https://www.mysql.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-green?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📊 Key Metrics

| Metric | Value |
|--------|-------|
| 🛫 Flight records supported | 500,000+ rows |
| 🏢 Airlines modelled | 8 major US carriers |
| 🗺️ Airports modelled | 12 major US hubs |
| 📋 Analytical queries | 10+ complex queries |
| ⚙️ Stored procedures | 3 (SLA flagging, scorecard, resolver) |
| 🔔 Triggers | 4 (audit log, validation, breach alert) |
| 🔍 Query optimizations | 4 documented (up to ~90% speedup) |

---

## 🧠 Why This Project Exists

Most SQL portfolios show a Library or Hospital schema. This project models something real:

> **Airline Operations teams actually run these queries.** Dispatch analysts need to know which routes are breaching SLA contracts, which airports cascade delays downstream, and which carriers are trending worse month-over-month. This project builds that SQL layer from scratch.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MySQL 8.0 Database                      │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐   │
│  │ airlines │    │ airports │    │       flights         │   │
│  └────┬─────┘    └────┬─────┘    │  (500K+ rows)        │   │
│       │               │          └──────────┬───────────┘   │
│       └──────┬────────┘                     │               │
│           ┌──▼──────┐          ┌────────────▼───────────┐   │
│           │ routes  │◄─────────│  Stored Procedures     │   │
│           └─────────┘          │  sp_flag_delayed_routes│   │
│                                │  sp_monthly_scorecard  │   │
│  ┌─────────────────────┐       └────────────────────────┘   │
│  │   sla_breach_log    │◄──── Triggers + Procedures         │
│  └─────────────────────┘                                    │
│  ┌─────────────────────┐                                    │
│  │     audit_log       │◄──── All 4 triggers write here     │
│  └─────────────────────┘                                    │
└─────────────────────────────────────────────────────────────┘
```

### Entity Relationship (simplified)

```
airlines ──< routes >── airports
              │
              └──< flights
                        │
                        └──> sla_breach_log
                        └──> audit_log (via triggers)
```

---

## 🚀 Quick Start

### Prerequisites
- MySQL 8.0+
- Python 3.9+
- pip

### 1. Clone the repository
```bash
git clone https://github.com/VijayKumaro7/flightops-sql.git
cd flightops-sql
```

### 2. Create the database and schema
```bash
mysql -u root -p < schema/01_tables.sql
mysql -u root -p flightops < schema/02_indexes.sql
mysql -u root -p flightops < schema/03_views.sql
```

### 3. Load stored procedures and triggers
```bash
mysql -u root -p flightops < procedures/sp_flag_delayed_routes.sql
mysql -u root -p flightops < triggers/trg_audit_log.sql
```

### 4. Seed synthetic data
```bash
pip install faker mysql-connector-python
python seed/seed_data.py --rows 500000 --user root --password yourpassword
```

### 5. Run the SLA breach detector
```sql
USE flightops;
SET @breaches = 0;
CALL sp_flag_delayed_routes(CURDATE(), @breaches);
SELECT CONCAT(@breaches, ' new SLA breaches logged') AS result;
```

---

## 🔍 Highlight Queries

### 1. Carrier Rankings with Window Functions
```sql
WITH base AS (
    SELECT a.carrier_code, a.carrier_name,
           COUNT(*) AS total_flights,
           SUM(CASE WHEN f.arr_delay_mins >= 15 THEN 1 ELSE 0 END) AS delayed
    FROM flights f
    JOIN routes r ON f.route_id = r.route_id
    JOIN airlines a ON r.carrier_code = a.carrier_code
    WHERE f.cancelled = 0
    GROUP BY a.carrier_code, a.carrier_name
)
SELECT
    RANK() OVER (ORDER BY delayed/total_flights ASC) AS on_time_rank,
    carrier_name,
    ROUND(100.0 * delayed / total_flights, 2) AS delay_rate_pct
FROM base;
```

### 2. Month-over-Month Trend with LAG()
```sql
SELECT
    carrier_code,
    DATE_FORMAT(flight_date, '%Y-%m') AS month,
    ROUND(100.0 * SUM(CASE WHEN arr_delay_mins >= 15 THEN 1 ELSE 0 END) / COUNT(*), 2) AS delay_rate,
    LAG(ROUND(100.0 * SUM(...) / COUNT(*), 2)) OVER (PARTITION BY carrier_code ORDER BY month) AS prev_month,
    -- See full query in queries/carrier_performance.sql
FROM flights f JOIN ...
```

### 3. Delay Propagation — Finding Cascade Airports
```sql
SELECT r.origin, ap.city,
       ROUND(AVG(f.late_aircraft_delay) / NULLIF(AVG(f.arr_delay_mins), 0) * 100, 1)
           AS propagation_ratio_pct
FROM flights f JOIN routes r ON f.route_id = r.route_id
JOIN airports ap ON r.origin = ap.airport_code
WHERE f.late_aircraft_delay > 0 AND f.cancelled = 0
GROUP BY r.origin, ap.city HAVING COUNT(*) >= 30
ORDER BY propagation_ratio_pct DESC LIMIT 15;
```

---

## 📈 Insights (run on 500K synthetic rows)

| Finding | Value |
|---------|-------|
| Average arrival delay (all carriers) | ~12–18 mins |
| % of flights genuinely on-time (<15 min delay) | ~72% |
| Top delay cause | Late Aircraft (~23% of delay minutes) |
| Worst time slot for departure delays | 6PM–12AM (Evening) |
| Chronic breach routes (3+ breaches / 90 days) | ~8–12% of routes |

---

## 🗂️ Repository Structure

```
flightops-sql/
├── README.md
├── .gitignore
├── schema/
│   ├── 01_tables.sql          # All DDL — 7 tables
│   ├── 02_indexes.sql         # 9 indexes with rationale
│   └── 03_views.sql           # 3 analytical views
├── procedures/
│   └── sp_flag_delayed_routes.sql   # 3 stored procedures
├── triggers/
│   └── trg_audit_log.sql      # 4 triggers (audit + validation)
├── queries/
│   ├── carrier_performance.sql      # Rankings, MoM trend, root cause
│   ├── airport_bottlenecks.sql      # Hotspots, propagation, time-of-day
│   └── sla_breach_report.sql        # Active breaches, chronic offenders
├── optimization/
│   └── query_optimization.sql  # 4 before/after EXPLAIN comparisons
├── seed/
│   └── seed_data.py            # Generates 500K+ realistic rows
└── docs/
    └── ERD.png                 # Entity relationship diagram
```

---

## ⚡ Query Optimization Results

| Optimization | Technique | Rows Examined Before | After | Speedup |
|---|---|---|---|---|
| Date range filter | Add `idx_flight_date` | 3,000,000 | ~750,000 | ~75% |
| Per-row subquery | CTE pre-aggregation | 3M × N | 3M + N | ~90% |
| Carrier semi-join | EXISTS vs IN | Full list | Early-exit | ~40% |
| Scorecard query | Covering index | Data + index pages | Index only | ~60% |

---

## 🛠️ Tech Stack

- **MySQL 8.0** — Window functions, CTEs, JSON columns, stored procedures
- **Python 3.9** — Seed data generation (Faker + mysql-connector)
- **DBeaver / MySQL Workbench** — Query development and EXPLAIN analysis

---

## 📚 Data Source

This project uses **synthetic data** generated to match the statistical distributions of the [US Bureau of Transportation Statistics On-Time Performance dataset](https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ).

To use real BTS data:
1. Download CSV from the BTS website (free, public domain)
2. Replace the seed script with a CSV loader
3. All schema and queries remain identical

---

## 🧑‍💻 Author

**Vijay Kumar** — Aspiring Data/ML Engineer  
[![GitHub](https://img.shields.io/badge/GitHub-VijayKumaro7-black?logo=github)](https://github.com/VijayKumaro7)

---
