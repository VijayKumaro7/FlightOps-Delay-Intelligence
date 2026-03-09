"""
FlightOps Delay Intelligence — Seed Data Generator
Generates realistic synthetic flight data using Faker + random distributions
that match real BTS (Bureau of Transportation Statistics) patterns.

Usage:
    pip install faker mysql-connector-python
    python seed/seed_data.py --rows 500000 --host localhost --db flightops
"""

import argparse
import random
import datetime
import mysql.connector
from faker import Faker

fake = Faker()

# ── Real-world US carriers ────────────────────────────────
AIRLINES = [
    ("AA", "American Airlines"),
    ("DL", "Delta Air Lines"),
    ("UA", "United Airlines"),
    ("WN", "Southwest Airlines"),
    ("B6", "JetBlue Airways"),
    ("AS", "Alaska Airlines"),
    ("NK", "Spirit Airlines"),
    ("F9", "Frontier Airlines"),
]

# ── Major US airports ─────────────────────────────────────
AIRPORTS = [
    ("ATL", "Hartsfield-Jackson Atlanta International", "Atlanta",    "GA",  33.6407, -84.4277),
    ("LAX", "Los Angeles International",                "Los Angeles","CA",  33.9425, -118.4081),
    ("ORD", "O'Hare International",                     "Chicago",    "IL",  41.9742, -87.9073),
    ("DFW", "Dallas/Fort Worth International",          "Dallas",     "TX",  32.8998, -97.0403),
    ("DEN", "Denver International",                     "Denver",     "CO",  39.8561, -104.6737),
    ("JFK", "John F. Kennedy International",            "New York",   "NY",  40.6413, -73.7781),
    ("SFO", "San Francisco International",              "San Francisco","CA",37.6213, -122.3790),
    ("SEA", "Seattle-Tacoma International",             "Seattle",    "WA",  47.4502, -122.3088),
    ("MIA", "Miami International",                      "Miami",      "FL",  25.7959, -80.2870),
    ("BOS", "Logan International",                      "Boston",     "MA",  42.3656, -71.0096),
    ("LAS", "Harry Reid International",                 "Las Vegas",  "NV",  36.0840, -115.1537),
    ("PHX", "Phoenix Sky Harbor International",         "Phoenix",    "AZ",  33.4373, -112.0078),
]


def random_delay():
    """
    Realistic delay distribution:
    ~72% on-time / early, ~18% slightly late, ~7% moderately late, ~3% severely late
    """
    roll = random.random()
    if roll < 0.30:
        return random.randint(-20, -1)     # Early
    elif roll < 0.72:
        return random.randint(0, 14)       # On time (< 15 min)
    elif roll < 0.87:
        return random.randint(15, 45)      # Minor delay
    elif roll < 0.95:
        return random.randint(46, 120)     # Moderate delay
    else:
        return random.randint(121, 480)    # Severe delay


def split_delay_into_causes(total_delay):
    """Split a total delay into BTS cause categories."""
    if total_delay <= 0:
        return 0, 0, 0, 0, 0

    causes = ["carrier", "weather", "nas", "security", "late_aircraft"]
    weights = [0.35, 0.20, 0.20, 0.02, 0.23]
    result = {c: 0 for c in causes}

    remaining = total_delay
    for i, cause in enumerate(causes[:-1]):
        portion = int(remaining * weights[i] * random.uniform(0.6, 1.4))
        portion = min(portion, remaining)
        result[cause] = max(0, portion)
        remaining -= result[cause]

    result["late_aircraft"] = max(0, remaining)
    return (result["carrier"], result["weather"], result["nas"],
            result["security"], result["late_aircraft"])


def seed(rows: int, conn_params: dict):
    conn   = mysql.connector.connect(**conn_params)
    cursor = conn.cursor()

    print("→ Seeding airlines...")
    for code, name in AIRLINES:
        cursor.execute(
            "INSERT IGNORE INTO airlines (carrier_code, carrier_name) VALUES (%s, %s)",
            (code, name)
        )

    print("→ Seeding airports...")
    for row in AIRPORTS:
        cursor.execute(
            """INSERT IGNORE INTO airports
               (airport_code, airport_name, city, state, latitude, longitude)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            row
        )

    print("→ Seeding SLA rules...")
    cursor.execute("""
        INSERT IGNORE INTO sla_rules (carrier_code, max_delay_rate_pct, min_flights_window, window_days)
        VALUES (NULL, 15.00, 100, 30)
    """)

    print("→ Building routes...")
    route_map = {}   # (carrier, origin, dest) -> route_id
    airport_codes = [a[0] for a in AIRPORTS]
    for carrier_code, _ in AIRLINES:
        # Each carrier operates ~8–12 routes
        num_routes = random.randint(8, 12)
        pairs_used = set()
        for _ in range(num_routes):
            origin = random.choice(airport_codes)
            dest   = random.choice([a for a in airport_codes if a != origin])
            if (origin, dest) in pairs_used:
                continue
            pairs_used.add((origin, dest))
            dist   = random.randint(300, 2800)
            sched  = int(dist / 6) + random.randint(-10, 10)   # ~6 miles/min
            cursor.execute(
                """INSERT IGNORE INTO routes (carrier_code, origin, destination, scheduled_mins)
                   VALUES (%s, %s, %s, %s)""",
                (carrier_code, origin, dest, sched)
            )
            cursor.execute("SELECT LAST_INSERT_ID()")
            route_id = cursor.fetchone()[0]
            if route_id:
                route_map[(carrier_code, origin, dest)] = route_id

    conn.commit()
    all_route_ids = list(route_map.values())
    if not all_route_ids:
        # Fallback: pull all route IDs from DB
        cursor.execute("SELECT route_id FROM routes")
        all_route_ids = [r[0] for r in cursor.fetchall()]

    print(f"→ Seeding {rows:,} flight records...")
    start_date = datetime.date(2023, 1, 1)
    batch      = []
    BATCH_SIZE = 5000

    for i in range(rows):
        route_id   = random.choice(all_route_ids)
        flight_date = start_date + datetime.timedelta(days=random.randint(0, 364))
        sched_dep  = random.choice([600, 700, 800, 900, 1000, 1100, 1200,
                                    1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000])
        arr_delay  = random_delay()
        dep_delay  = max(arr_delay - random.randint(0, 10), arr_delay)
        cancelled  = 1 if random.random() < 0.02 else 0

        if cancelled:
            actual_dep = None
            actual_arr = None
            arr_delay  = 0
            dep_delay  = 0
            car, wth, nas, sec, late = 0, 0, 0, 0, 0
        else:
            actual_dep = sched_dep + dep_delay
            actual_arr = sched_dep + 120 + arr_delay   # simplified
            car, wth, nas, sec, late = split_delay_into_causes(
                arr_delay if arr_delay > 0 else 0
            )

        batch.append((
            route_id, flight_date,
            f"{random.choice([c[0] for c in AIRLINES])}{random.randint(100,999)}",
            sched_dep, sched_dep + 120,
            actual_dep, actual_arr,
            dep_delay, arr_delay,
            cancelled, 0,
            car, wth, nas, sec, late,
            random.randint(300, 2800)
        ))

        if len(batch) >= BATCH_SIZE:
            cursor.executemany("""
                INSERT INTO flights
                    (route_id, flight_date, flight_number,
                     scheduled_dep, scheduled_arr, actual_dep, actual_arr,
                     dep_delay_mins, arr_delay_mins, cancelled, diverted,
                     carrier_delay, weather_delay, nas_delay, security_delay,
                     late_aircraft_delay, distance_miles)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, batch)
            conn.commit()
            batch = []
            print(f"   {i+1:,} / {rows:,} rows inserted...", end="\r")

    if batch:
        cursor.executemany("""
            INSERT INTO flights
                (route_id, flight_date, flight_number,
                 scheduled_dep, scheduled_arr, actual_dep, actual_arr,
                 dep_delay_mins, arr_delay_mins, cancelled, diverted,
                 carrier_delay, weather_delay, nas_delay, security_delay,
                 late_aircraft_delay, distance_miles)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, batch)
        conn.commit()

    cursor.close()
    conn.close()
    print(f"\n✅ Done! {rows:,} flights seeded successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FlightOps seed data generator")
    parser.add_argument("--rows",     type=int, default=500_000, help="Number of flight rows")
    parser.add_argument("--host",     default="localhost")
    parser.add_argument("--port",     type=int, default=3306)
    parser.add_argument("--user",     default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--db",       default="flightops")
    args = parser.parse_args()

    seed(
        rows=args.rows,
        conn_params={
            "host":     args.host,
            "port":     args.port,
            "user":     args.user,
            "password": args.password,
            "database": args.db,
        }
    )
