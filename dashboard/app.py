"""
FlightOps Delay Intelligence — Streamlit Dashboard
Run with:  streamlit run dashboard/app.py
"""

import datetime
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from config import SLA_DEFAULT_THRESHOLD_PCT

st.set_page_config(
    page_title="FlightOps Delay Intelligence",
    page_icon="✈️",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("✈️ FlightOps")
    st.caption("Delay Intelligence Dashboard")
    st.divider()

    st.subheader("Filters")

    # Carrier filter
    carrier_options = ["All", "AA", "DL", "UA", "WN", "B6", "AS", "NK", "F9"]
    selected_carrier = st.selectbox("Carrier", carrier_options)

    # Date range filter
    default_start = datetime.date(2023, 1, 1)
    default_end   = datetime.date(2023, 12, 31)
    start_date = st.date_input("From", value=default_start,
                                min_value=default_start, max_value=default_end)
    end_date   = st.date_input("To",   value=default_end,
                                min_value=default_start, max_value=default_end)

    # Date validation — swap silently if user picks end before start
    if start_date > end_date:
        st.warning("'From' date is after 'To' date — dates have been swapped.")
        start_date, end_date = end_date, start_date

    st.divider()

    # SLA threshold slider
    st.subheader("SLA Settings")
    sla_threshold = st.slider(
        "Delay-rate SLA threshold (%)",
        min_value=5, max_value=30,
        value=int(SLA_DEFAULT_THRESHOLD_PCT),
        step=5,
        help="Routes with a delay rate above this % are considered SLA breaches.",
    )

    st.divider()
    st.caption("Data: Synthetic BTS-pattern data · MySQL backend")
    st.caption(f"Query cache: 5 min · Threshold: {sla_threshold}%")

# ── SLA breach alert banner ───────────────────────────────────────────────────
_RECENT_BREACH_SQL = """
SELECT COUNT(*) AS cnt
FROM sla_breach_log
WHERE resolved = 0
  AND created_at >= NOW() - INTERVAL 24 HOUR
"""

try:
    from db import run_query
    df_alert = run_query(_RECENT_BREACH_SQL)
    if not df_alert.empty and int(df_alert["cnt"].iloc[0]) > 0:
        breach_count = int(df_alert["cnt"].iloc[0])
        st.error(
            f"🚨 **{breach_count} new SLA breach{'es' if breach_count > 1 else ''} "
            f"detected in the last 24 hours.** Check the SLA Dashboard tab for details."
        )
except Exception:
    pass  # Silently skip banner if DB is unavailable

# ── Main content area ─────────────────────────────────────────────────────────
st.title("FlightOps Delay Intelligence")

tab1, tab2, tab3 = st.tabs([
    "📊 Carrier Performance",
    "🗺️ Airport Bottlenecks",
    "🚨 SLA Dashboard",
])

with tab1:
    from pages.carrier_performance import render
    render(selected_carrier, start_date, end_date, sla_threshold)

with tab2:
    from pages.airport_bottlenecks import render
    render(selected_carrier, start_date, end_date)

with tab3:
    from pages.sla_dashboard import render
    render(selected_carrier, start_date, end_date, sla_threshold)
