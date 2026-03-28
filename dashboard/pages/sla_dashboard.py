"""
SLA Dashboard page — active breaches, chronic offenders, carrier compliance.
Mirrors the queries in sla_breach_report.sql.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import run_query


# ── SQL (mirrors sla_breach_report.sql) ──────────────────────────────────────

_ACTIVE_BREACHES_SQL = """
SELECT
    bl.breach_id,
    bl.breach_date,
    CONCAT(r.origin, ' → ', r.destination)                              AS route,
    a.carrier_name,
    a.carrier_code,
    bl.total_flights,
    bl.delayed_flights,
    bl.delay_rate_pct,
    sr.max_delay_rate_pct                                               AS sla_threshold_pct,
    ROUND(bl.delay_rate_pct - sr.max_delay_rate_pct, 2)                 AS overage_pct,
    CASE
        WHEN bl.delay_rate_pct >= 30 THEN 'CRITICAL'
        WHEN bl.delay_rate_pct >= 20 THEN 'HIGH'
        ELSE                              'MEDIUM'
    END                                                                  AS severity,
    DATEDIFF(CURDATE(), bl.breach_date)                                  AS days_open
FROM  sla_breach_log bl
JOIN  routes         r  ON bl.route_id   = r.route_id
JOIN  airlines       a  ON r.carrier_code = a.carrier_code
JOIN  sla_rules      sr ON bl.rule_id    = sr.rule_id
WHERE bl.resolved = 0
  {carrier_filter}
ORDER BY bl.delay_rate_pct DESC
"""

_CHRONIC_SQL = """
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
    a.carrier_code,
    bc.avg_delay_rate,
    bc.peak_delay_rate,
    bc.first_breach,
    bc.latest_breach,
    DATEDIFF(bc.latest_breach, bc.first_breach)                          AS breach_span_days,
    CASE
        WHEN bc.breach_count >= 6 THEN 'CHRONIC'
        WHEN bc.breach_count >= 3 THEN 'RECURRING'
        ELSE                           'INTERMITTENT'
    END                                                                  AS pattern
FROM  breach_counts bc
JOIN  routes        r  ON bc.route_id    = r.route_id
JOIN  airlines      a  ON r.carrier_code = a.carrier_code
  {carrier_filter}
ORDER BY bc.breach_count DESC, bc.avg_delay_rate DESC
"""

_COMPLIANCE_SQL = """
WITH carrier_routes AS (
    SELECT DISTINCT r.carrier_code, r.route_id
    FROM routes r
),
breached_routes AS (
    SELECT DISTINCT r.carrier_code, bl.route_id
    FROM  sla_breach_log bl
    JOIN  routes         r ON bl.route_id = r.route_id
    WHERE bl.breach_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
)
SELECT
    a.carrier_name,
    a.carrier_code,
    COUNT(cr.route_id)                                                   AS total_routes,
    COUNT(br.route_id)                                                   AS breached_routes,
    COUNT(cr.route_id) - COUNT(br.route_id)                             AS compliant_routes,
    ROUND(100.0 * (COUNT(cr.route_id) - COUNT(br.route_id))
                 / COUNT(cr.route_id), 1)                                AS sla_compliance_pct
FROM  carrier_routes cr
JOIN  airlines       a  ON cr.carrier_code = a.carrier_code
LEFT  JOIN breached_routes br
      ON cr.carrier_code = br.carrier_code AND cr.route_id = br.route_id
  {carrier_filter}
GROUP BY a.carrier_name, a.carrier_code
ORDER BY sla_compliance_pct DESC
"""


def _carrier_filter_clause_breach(carrier: str) -> str:
    if carrier == "All":
        return ""
    return "AND a.carrier_code = :carrier_code"


def _carrier_filter_clause_chronic(carrier: str) -> str:
    if carrier == "All":
        return ""
    return "AND a.carrier_code = :carrier_code"


def _carrier_filter_clause_compliance(carrier: str) -> str:
    if carrier == "All":
        return ""
    return "AND a.carrier_code = :carrier_code"


_SEVERITY_COLORS = {"CRITICAL": "#e74c3c", "HIGH": "#e67e22", "MEDIUM": "#f1c40f"}
_PATTERN_COLORS = {"CHRONIC": "#c0392b", "RECURRING": "#e67e22", "INTERMITTENT": "#3498db"}


def render(selected_carrier: str, start_date, end_date):
    params = {}
    if selected_carrier != "All":
        params["carrier_code"] = selected_carrier

    # ── Active SLA Breaches ───────────────────────────────────────────────────
    st.subheader("Active (Unresolved) SLA Breaches")
    try:
        cf = _carrier_filter_clause_breach(selected_carrier)
        df_breach = run_query(_ACTIVE_BREACHES_SQL.format(carrier_filter=cf), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if df_breach.empty:
        st.success("No active SLA breaches for the selected filters.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Active Breaches", len(df_breach))
        col2.metric("Critical", int((df_breach["severity"] == "CRITICAL").sum()))
        col3.metric("Avg Overage", f"{df_breach['overage_pct'].mean():.1f}%")

        # Severity distribution donut
        sev_counts = df_breach["severity"].value_counts().reset_index()
        sev_counts.columns = ["severity", "count"]
        fig_sev = px.pie(
            sev_counts,
            names="severity",
            values="count",
            color="severity",
            color_discrete_map=_SEVERITY_COLORS,
            hole=0.45,
            title="Breach Severity Distribution",
        )
        st.plotly_chart(fig_sev, use_container_width=True)

        # Color-coded breach table
        def color_severity(val):
            colors = {"CRITICAL": "background-color:#fde8e8", "HIGH": "background-color:#fef3e2", "MEDIUM": "background-color:#fefce8"}
            return colors.get(val, "")

        display_cols = ["breach_date", "route", "carrier_name", "delay_rate_pct",
                        "sla_threshold_pct", "overage_pct", "severity", "days_open"]
        styled = df_breach[display_cols].style.applymap(color_severity, subset=["severity"])
        st.dataframe(styled, use_container_width=True)

    st.divider()

    # ── Chronic Offenders ─────────────────────────────────────────────────────
    st.subheader("Chronic Offenders (Last 90 Days)")
    try:
        cf_chronic = _carrier_filter_clause_chronic(selected_carrier)
        df_chronic = run_query(_CHRONIC_SQL.format(carrier_filter=cf_chronic), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if df_chronic.empty:
        st.info("No chronic offenders found (no routes with 3+ breaches in last 90 days).")
    else:
        fig_chronic = px.bar(
            df_chronic.sort_values("breach_count", ascending=True),
            x="breach_count",
            y="route",
            color="pattern",
            color_discrete_map=_PATTERN_COLORS,
            orientation="h",
            labels={"breach_count": "Breach Count (last 90 days)", "route": "Route"},
            title="Chronic Offender Routes",
            hover_data={"carrier_name": True, "avg_delay_rate": ":.1f", "peak_delay_rate": ":.1f"},
            text="breach_count",
        )
        fig_chronic.update_traces(textposition="outside")
        fig_chronic.update_layout(height=max(350, len(df_chronic) * 32))
        st.plotly_chart(fig_chronic, use_container_width=True)

    st.divider()

    # ── Carrier SLA Compliance ────────────────────────────────────────────────
    st.subheader("Carrier SLA Compliance (Last 30 Days)")
    try:
        cf_comp = _carrier_filter_clause_compliance(selected_carrier)
        df_comp = run_query(_COMPLIANCE_SQL.format(carrier_filter=cf_comp), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if df_comp.empty:
        st.info("No compliance data available.")
        return

    # Gauge charts for each carrier
    cols = st.columns(min(4, len(df_comp)))
    for i, row in enumerate(df_comp.itertuples()):
        col = cols[i % len(cols)]
        pct = float(row.sla_compliance_pct)
        color = "#27ae60" if pct >= 90 else "#e67e22" if pct >= 75 else "#e74c3c"
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=pct,
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 75], "color": "#fde8e8"},
                    {"range": [75, 90], "color": "#fef3e2"},
                    {"range": [90, 100], "color": "#eafaf1"},
                ],
                "threshold": {"line": {"color": "black", "width": 2}, "thickness": 0.75, "value": 90},
            },
            title={"text": row.carrier_name, "font": {"size": 13}},
        ))
        fig_gauge.update_layout(height=220, margin=dict(t=40, b=10, l=20, r=20))
        col.plotly_chart(fig_gauge, use_container_width=True)

    # Summary bar chart
    fig_comp = px.bar(
        df_comp.sort_values("sla_compliance_pct"),
        x="sla_compliance_pct",
        y="carrier_name",
        orientation="h",
        color="sla_compliance_pct",
        color_continuous_scale="RdYlGn",
        range_color=[50, 100],
        labels={"sla_compliance_pct": "SLA Compliance (%)", "carrier_name": "Carrier"},
        title="SLA Compliance Rate by Carrier",
        text="sla_compliance_pct",
    )
    fig_comp.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_comp.add_vline(x=90, line_dash="dash", line_color="green", annotation_text="90% target")
    fig_comp.add_vline(x=75, line_dash="dash", line_color="orange", annotation_text="75% at-risk")
    fig_comp.update_layout(coloraxis_showscale=False, height=400)
    st.plotly_chart(fig_comp, use_container_width=True)
