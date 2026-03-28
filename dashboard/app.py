"""
FlightOps Delay Intelligence — Streamlit Dashboard
Run with:  streamlit run dashboard/app.py
"""

import streamlit as st

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
    import datetime
    default_start = datetime.date(2023, 1, 1)
    default_end = datetime.date(2023, 12, 31)
    start_date = st.date_input("From", value=default_start, min_value=default_start, max_value=default_end)
    end_date = st.date_input("To", value=default_end, min_value=default_start, max_value=default_end)

    st.divider()
    st.caption("Data: Synthetic BTS-pattern data · MySQL backend")

# Store filters in session state so pages can access them
st.session_state["selected_carrier"] = selected_carrier
st.session_state["start_date"] = start_date
st.session_state["end_date"] = end_date

# ── Main content area ─────────────────────────────────────────────────────────
st.title("FlightOps Delay Intelligence")

tab1, tab2, tab3 = st.tabs([
    "📊 Carrier Performance",
    "🗺️ Airport Bottlenecks",
    "🚨 SLA Dashboard",
])

with tab1:
    from pages.carrier_performance import render
    render(selected_carrier, start_date, end_date)

with tab2:
    from pages.airport_bottlenecks import render
    render(selected_carrier, start_date, end_date)

with tab3:
    from pages.sla_dashboard import render
    render(selected_carrier, start_date, end_date)
