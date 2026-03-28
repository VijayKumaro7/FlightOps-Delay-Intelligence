"""
Carrier Performance page — rankings, MoM trend, root cause breakdown.
Mirrors the queries in carrier_performance.sql.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import run_query


# ── SQL (mirrors carrier_performance.sql) ─────────────────────────────────────

_RANKINGS_SQL = """
WITH base AS (
    SELECT
        a.carrier_code,
        a.carrier_name,
        COUNT(*)                                                          AS total_flights,
        SUM(f.cancelled)                                                  AS cancelled,
        SUM(CASE WHEN f.arr_delay_mins >= 15 THEN 1 ELSE 0 END)          AS delayed,
        ROUND(AVG(f.arr_delay_mins), 2)                                   AS avg_delay,
        ROUND(AVG(CASE WHEN f.arr_delay_mins >= 15
                  THEN f.arr_delay_mins END), 2)                          AS avg_delay_when_late,
        SUM(CASE WHEN f.arr_delay_mins >= 60 THEN 1 ELSE 0 END)          AS severe_delays
    FROM  flights  f
    JOIN  routes   r ON f.route_id    = r.route_id
    JOIN  airlines a ON r.carrier_code = a.carrier_code
    WHERE f.flight_date BETWEEN :start_date AND :end_date
      AND f.cancelled = 0
      {carrier_filter}
    GROUP BY a.carrier_code, a.carrier_name
),
ranked AS (
    SELECT *,
        ROUND(100.0 * delayed / total_flights, 2)        AS delay_rate_pct,
        ROUND(100.0 * cancelled / total_flights, 2)      AS cancel_rate_pct,
        RANK() OVER (ORDER BY (delayed / total_flights) ASC) AS on_time_rank
    FROM base
)
SELECT on_time_rank, carrier_code, carrier_name, total_flights,
       delayed, severe_delays, avg_delay AS avg_arr_delay_mins,
       avg_delay_when_late, delay_rate_pct, cancel_rate_pct
FROM ranked
ORDER BY on_time_rank
"""

_MOM_SQL = """
WITH monthly AS (
    SELECT
        a.carrier_code,
        a.carrier_name,
        DATE_FORMAT(f.flight_date, '%Y-%m')                               AS month_label,
        ROUND(100.0 * SUM(CASE WHEN f.arr_delay_mins >= 15
                          THEN 1 ELSE 0 END) / COUNT(*), 2)              AS delay_rate_pct
    FROM  flights  f
    JOIN  routes   r ON f.route_id    = r.route_id
    JOIN  airlines a ON r.carrier_code = a.carrier_code
    WHERE f.cancelled = 0
      AND f.flight_date BETWEEN :start_date AND :end_date
      {carrier_filter}
    GROUP BY a.carrier_code, a.carrier_name, month_label
)
SELECT carrier_code, carrier_name, month_label, delay_rate_pct,
    LAG(delay_rate_pct) OVER (PARTITION BY carrier_code ORDER BY month_label) AS prev_month_rate,
    ROUND(delay_rate_pct -
          LAG(delay_rate_pct) OVER (PARTITION BY carrier_code ORDER BY month_label), 2) AS mom_change_pct
FROM monthly
ORDER BY carrier_code, month_label
"""

_ROOT_CAUSE_SQL = """
SELECT
    a.carrier_code,
    a.carrier_name,
    ROUND(100.0 * SUM(f.carrier_delay) /
          NULLIF(SUM(f.carrier_delay + f.weather_delay + f.nas_delay
               + f.security_delay + f.late_aircraft_delay), 0), 1) AS pct_carrier,
    ROUND(100.0 * SUM(f.weather_delay) /
          NULLIF(SUM(f.carrier_delay + f.weather_delay + f.nas_delay
               + f.security_delay + f.late_aircraft_delay), 0), 1) AS pct_weather,
    ROUND(100.0 * SUM(f.nas_delay) /
          NULLIF(SUM(f.carrier_delay + f.weather_delay + f.nas_delay
               + f.security_delay + f.late_aircraft_delay), 0), 1) AS pct_nas,
    ROUND(100.0 * SUM(f.security_delay) /
          NULLIF(SUM(f.carrier_delay + f.weather_delay + f.nas_delay
               + f.security_delay + f.late_aircraft_delay), 0), 1) AS pct_security,
    ROUND(100.0 * SUM(f.late_aircraft_delay) /
          NULLIF(SUM(f.carrier_delay + f.weather_delay + f.nas_delay
               + f.security_delay + f.late_aircraft_delay), 0), 1) AS pct_late_aircraft,
    SUM(f.carrier_delay + f.weather_delay + f.nas_delay
      + f.security_delay + f.late_aircraft_delay)                   AS grand_total_delay_mins
FROM  flights  f
JOIN  routes   r ON f.route_id    = r.route_id
JOIN  airlines a ON r.carrier_code = a.carrier_code
WHERE f.cancelled = 0
  AND f.flight_date BETWEEN :start_date AND :end_date
  {carrier_filter}
GROUP BY a.carrier_code, a.carrier_name
ORDER BY grand_total_delay_mins DESC
"""


def _carrier_filter_clause(carrier: str) -> str:
    if carrier == "All":
        return ""
    return "AND a.carrier_code = :carrier_code"


def render(selected_carrier: str, start_date, end_date):
    cf = _carrier_filter_clause(selected_carrier)
    params = {"start_date": str(start_date), "end_date": str(end_date)}
    if selected_carrier != "All":
        params["carrier_code"] = selected_carrier

    # ── Carrier Rankings ──────────────────────────────────────────────────────
    st.subheader("Carrier On-Time Rankings")
    try:
        df_rank = run_query(_RANKINGS_SQL.format(carrier_filter=cf), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if df_rank.empty:
        st.info("No data for selected filters.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Flights", f"{int(df_rank['total_flights'].sum()):,}")
    col2.metric("Avg Delay Rate", f"{df_rank['delay_rate_pct'].mean():.1f}%")
    col3.metric("Severe Delays", f"{int(df_rank['severe_delays'].sum()):,}")

    # Horizontal bar chart — delay rate per carrier
    fig_rank = px.bar(
        df_rank.sort_values("delay_rate_pct", ascending=True),
        x="delay_rate_pct",
        y="carrier_name",
        orientation="h",
        color="delay_rate_pct",
        color_continuous_scale="RdYlGn_r",
        labels={"delay_rate_pct": "Delay Rate (%)", "carrier_name": "Carrier"},
        title="Delay Rate by Carrier (lower is better)",
        text="delay_rate_pct",
    )
    fig_rank.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_rank.update_layout(coloraxis_showscale=False, height=400)
    st.plotly_chart(fig_rank, use_container_width=True)

    with st.expander("Full rankings table"):
        st.dataframe(
            df_rank[["on_time_rank", "carrier_name", "total_flights",
                     "delay_rate_pct", "avg_arr_delay_mins", "avg_delay_when_late",
                     "severe_delays", "cancel_rate_pct"]],
            use_container_width=True,
        )

    st.divider()

    # ── Month-over-Month Trend ────────────────────────────────────────────────
    st.subheader("Month-over-Month Delay Trend")
    try:
        df_mom = run_query(_MOM_SQL.format(carrier_filter=cf), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if not df_mom.empty:
        fig_mom = px.line(
            df_mom,
            x="month_label",
            y="delay_rate_pct",
            color="carrier_name",
            markers=True,
            labels={"month_label": "Month", "delay_rate_pct": "Delay Rate (%)", "carrier_name": "Carrier"},
            title="Monthly Delay Rate per Carrier",
        )
        fig_mom.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig_mom, use_container_width=True)

    st.divider()

    # ── Root Cause Breakdown ──────────────────────────────────────────────────
    st.subheader("Delay Root Cause Breakdown")
    try:
        df_cause = run_query(_ROOT_CAUSE_SQL.format(carrier_filter=cf), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if not df_cause.empty:
        cause_cols = ["pct_carrier", "pct_weather", "pct_nas", "pct_security", "pct_late_aircraft"]
        cause_labels = ["Carrier", "Weather", "NAS", "Security", "Late Aircraft"]

        # Stacked bar per carrier
        df_melt = df_cause.melt(
            id_vars=["carrier_name"],
            value_vars=cause_cols,
            var_name="cause",
            value_name="percentage",
        )
        df_melt["cause"] = df_melt["cause"].map(dict(zip(cause_cols, cause_labels)))

        fig_cause = px.bar(
            df_melt,
            x="carrier_name",
            y="percentage",
            color="cause",
            barmode="stack",
            labels={"percentage": "% of Delay Minutes", "carrier_name": "Carrier", "cause": "Cause"},
            title="Delay Cause Breakdown by Carrier (%)",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_cause.update_layout(height=400)
        st.plotly_chart(fig_cause, use_container_width=True)

        # Summary donut for selected/all carriers
        totals = df_cause[cause_cols].sum()
        fig_donut = go.Figure(go.Pie(
            labels=cause_labels,
            values=totals.values,
            hole=0.45,
            textinfo="label+percent",
        ))
        fig_donut.update_layout(title="Overall Delay Cause Distribution", height=380)
        st.plotly_chart(fig_donut, use_container_width=True)
