"""
FlightOps Delay Intelligence — Centralised configuration constants.
Change values here to affect the entire dashboard without touching
individual page files.
"""

# ── SLA thresholds ────────────────────────────────────────────────────────────
SLA_DEFAULT_THRESHOLD_PCT: float = 15.0   # Default delay-rate SLA (%)
SLA_AT_RISK_PCT:           float = 75.0   # Compliance % below which a carrier is "at risk"
SLA_TARGET_PCT:            float = 90.0   # Compliance % target

# ── Delay severity thresholds ─────────────────────────────────────────────────
DELAY_CRITICAL_PCT:  float = 30.0   # Breach severity: CRITICAL
DELAY_HIGH_PCT:      float = 20.0   # Breach severity: HIGH
DELAY_MINOR_MINS:    int   = 15     # Definition of "delayed" (minutes)
DELAY_SEVERE_MINS:   int   = 60     # Definition of "severely delayed"

# ── Query / data windows ──────────────────────────────────────────────────────
SLA_WINDOW_DAYS:      int = 30    # Rolling window for SLA compliance check
CHRONIC_WINDOW_DAYS:  int = 90    # Window for chronic offender detection
CHRONIC_MIN_BREACHES: int = 3     # Min breaches to be considered chronic

# ── Seed data ─────────────────────────────────────────────────────────────────
SEED_BATCH_SIZE:         int = 5000
SEED_CANCELLATION_RATE:  float = 0.02    # 2% cancellation probability

# ── Dashboard cache ───────────────────────────────────────────────────────────
CACHE_TTL_SECONDS: int = 300   # 5-minute query result cache
