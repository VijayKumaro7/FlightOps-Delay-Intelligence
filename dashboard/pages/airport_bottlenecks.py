"""
Airport Bottlenecks page — top delay-prone airports, propagation, route heatmap,
time-of-day pattern.
Mirrors the queries in airport_bottlenecks.sql.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import run_query


# ── SQL (mirrors airport_bottlenecks.sql) ─────────────────────────────────────

_TOP_AIRPORTS_SQL = """
WITH dep_stats AS (
    SELECT
        r.origin                                                         AS airport_code,
        ap.airport_name,
        ap.city,
        ap.state,
        ap.latitude,
        ap.longitude,
        COUNT(*)                                                         AS total_departures,
        ROUND(AVG(f.dep_delay_mins), 2)                                  AS avg_dep_delay,
        ROUND(100.0 * SUM(CASE WHEN f.dep_delay_mins >= 15
                          THEN 1 ELSE 0 END) / COUNT(*), 2)             AS dep_delay_rate_pct,
        MAX(f.dep_delay_mins)                                            AS worst_dep_delay,
        SUM(CASE WHEN f.dep_delay_mins >= 60 THEN 1 ELSE 0 END)         AS extreme_delays
    FROM  flights  f
    JOIN  routes   r  ON f.route_id    = r.route_id
    JOIN  airports ap ON r.origin      = ap.airport_code
    WHERE f.cancelled = 0
      AND f.flight_date BETWEEN :start_date AND :end_date
      {carrier_filter}
    GROUP BY r.origin, ap.airport_name, ap.city, ap.state, ap.latitude, ap.longitude
    HAVING total_departures >= 50
)
SELECT
    DENSE_RANK() OVER (ORDER BY avg_dep_delay DESC) AS delay_rank,
    airport_code, airport_name, city, state,
    latitude, longitude,
    total_departures, avg_dep_delay, dep_delay_rate_pct,
    worst_dep_delay, extreme_delays
FROM dep_stats
ORDER BY avg_dep_delay DESC
LIMIT 20
"""

_PROPAGATION_SQL = """
SELECT
    r.origin                                                             AS airport_code,
    ap.city,
    COUNT(*)                                                             AS flights_affected,
    ROUND(AVG(f.late_aircraft_delay), 2)                                 AS avg_late_aircraft_delay,
    ROUND(AVG(f.carrier_delay), 2)                                       AS avg_carrier_delay,
    ROUND(AVG(f.nas_delay), 2)                                           AS avg_nas_delay,
    ROUND(AVG(f.late_aircraft_delay) /
          NULLIF(AVG(f.arr_delay_mins), 0) * 100, 1)                    AS propagation_ratio_pct
FROM  flights  f
JOIN  routes   r  ON f.route_id = r.route_id
JOIN  airports ap ON r.origin   = ap.airport_code
WHERE f.late_aircraft_delay > 0
  AND f.cancelled = 0
  AND f.flight_date BETWEEN :start_date AND :end_date
  {carrier_filter}
GROUP BY r.origin, ap.city
HAVING flights_affected >= 30
ORDER BY propagation_ratio_pct DESC
LIMIT 15
"""

_ROUTE_HEATMAP_SQL = """
SELECT
    r.origin,
    ap_o.city                                                            AS origin_city,
    r.destination,
    ap_d.city                                                            AS dest_city,
    COUNT(*)                                                             AS flights,
    ROUND(AVG(f.arr_delay_mins), 1)                                      AS avg_arr_delay,
    ROUND(100.0 * SUM(CASE WHEN f.arr_delay_mins >= 15
                      THEN 1 ELSE 0 END) / COUNT(*), 1)                 AS delay_rate_pct
FROM  flights  f
JOIN  routes   r    ON f.route_id    = r.route_id
JOIN  airports ap_o ON r.origin      = ap_o.airport_code
JOIN  airports ap_d ON r.destination = ap_d.airport_code
WHERE f.cancelled = 0
  AND f.flight_date BETWEEN :start_date AND :end_date
  {carrier_filter}
GROUP BY r.origin, ap_o.city, r.destination, ap_d.city
HAVING flights >= 20
ORDER BY avg_arr_delay DESC
LIMIT 25
"""

_TIME_OF_DAY_SQL = """
SELECT
    r.origin                                                             AS airport_code,
    CASE
        WHEN f.scheduled_dep BETWEEN 0    AND 559  THEN '12AM-6AM'
        WHEN f.scheduled_dep BETWEEN 600  AND 959  THEN '6AM-10AM'
        WHEN f.scheduled_dep BETWEEN 1000 AND 1359 THEN '10AM-2PM'
        WHEN f.scheduled_dep BETWEEN 1400 AND 1759 THEN '2PM-6PM'
        ELSE                                             '6PM-12AM'
    END                                                                  AS time_slot,
    COUNT(*)                                                             AS flights,
    ROUND(AVG(f.dep_delay_mins), 2)                                      AS avg_dep_delay,
    ROUND(100.0 * SUM(CASE WHEN f.dep_delay_mins >= 15
                      THEN 1 ELSE 0 END) / COUNT(*), 2)                 AS delay_rate_pct
FROM  flights  f
JOIN  routes   r ON f.route_id = r.route_id
WHERE f.cancelled = 0
  AND f.flight_date BETWEEN :start_date AND :end_date
  {carrier_filter}
GROUP BY r.origin, time_slot
ORDER BY r.origin, avg_dep_delay DESC
"""


def _carrier_filter_clause(carrier: str) -> str:
    if carrier == "All":
        return ""
    return "AND r.carrier_code = :carrier_code"


def render(selected_carrier: str, start_date, end_date):
    cf = _carrier_filter_clause(selected_carrier)
    params = {"start_date": str(start_date), "end_date": str(end_date)}
    if selected_carrier != "All":
        params["carrier_code"] = selected_carrier

    # ── Top delay-prone airports bubble map ───────────────────────────────────
    st.subheader("Top Delay-Prone Airports")
    try:
        df_top = run_query(_TOP_AIRPORTS_SQL.format(carrier_filter=cf), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if df_top.empty:
        st.info("No data for selected filters.")
        return

    fig_map = px.scatter_geo(
        df_top,
        lat="latitude",
        lon="longitude",
        size="avg_dep_delay",
        color="avg_dep_delay",
        hover_name="airport_name",
        hover_data={"city": True, "state": True, "avg_dep_delay": ":.1f",
                    "dep_delay_rate_pct": ":.1f", "latitude": False, "longitude": False},
        color_continuous_scale="Reds",
        scope="usa",
        title="Average Departure Delay by Airport (bubble size = delay magnitude)",
        labels={"avg_dep_delay": "Avg Dep Delay (min)"},
    )
    fig_map.update_layout(height=450)
    st.plotly_chart(fig_map, use_container_width=True)

    # Bar chart — top 10 airports by delay rate
    fig_bar = px.bar(
        df_top.head(10).sort_values("dep_delay_rate_pct", ascending=True),
        x="dep_delay_rate_pct",
        y="airport_code",
        orientation="h",
        color="dep_delay_rate_pct",
        color_continuous_scale="Oranges",
        labels={"dep_delay_rate_pct": "Departure Delay Rate (%)", "airport_code": "Airport"},
        title="Top 10 Airports by Departure Delay Rate",
        text="dep_delay_rate_pct",
    )
    fig_bar.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_bar.update_layout(coloraxis_showscale=False, height=380)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # ── Delay Propagation ─────────────────────────────────────────────────────
    st.subheader("Delay Propagation (Late Aircraft Effect)")
    try:
        df_prop = run_query(_PROPAGATION_SQL.format(carrier_filter=cf), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if not df_prop.empty:
        fig_prop = px.bar(
            df_prop.sort_values("propagation_ratio_pct", ascending=True),
            x="propagation_ratio_pct",
            y="airport_code",
            orientation="h",
            color="propagation_ratio_pct",
            color_continuous_scale="Blues",
            labels={"propagation_ratio_pct": "Propagation Ratio (%)", "airport_code": "Airport"},
            title="Cascade Delay Ratio by Airport (% of arrival delay from upstream late aircraft)",
            text="propagation_ratio_pct",
            hover_data={"city": True, "avg_late_aircraft_delay": ":.1f"},
        )
        fig_prop.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
        fig_prop.update_layout(coloraxis_showscale=False, height=400)
        st.plotly_chart(fig_prop, use_container_width=True)

    st.divider()

    # ── Route Pair Heatmap ────────────────────────────────────────────────────
    st.subheader("Origin → Destination Delay Heatmap")
    try:
        df_routes = run_query(_ROUTE_HEATMAP_SQL.format(carrier_filter=cf), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if not df_routes.empty:
        pivot = df_routes.pivot_table(
            index="origin", columns="destination", values="delay_rate_pct", aggfunc="mean"
        )
        fig_heat = px.imshow(
            pivot,
            color_continuous_scale="RdYlGn_r",
            labels={"color": "Delay Rate (%)"},
            title="Route Delay Rate Heatmap (origin rows × destination columns)",
            aspect="auto",
        )
        fig_heat.update_layout(height=450)
        st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()

    # ── Time-of-Day Pattern ───────────────────────────────────────────────────
    st.subheader("Time-of-Day Delay Pattern")
    try:
        df_tod = run_query(_TIME_OF_DAY_SQL.format(carrier_filter=cf), params)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if not df_tod.empty:
        time_order = ["12AM-6AM", "6AM-10AM", "10AM-2PM", "2PM-6PM", "6PM-12AM"]
        pivot_tod = df_tod.pivot_table(
            index="airport_code", columns="time_slot", values="avg_dep_delay", aggfunc="mean"
        ).reindex(columns=[t for t in time_order if t in df_tod["time_slot"].unique()])

        fig_tod = px.imshow(
            pivot_tod,
            color_continuous_scale="RdYlGn_r",
            labels={"color": "Avg Dep Delay (min)", "x": "Time Slot", "y": "Airport"},
            title="Average Departure Delay by Airport × Time of Day",
            aspect="auto",
        )
        fig_tod.update_layout(height=420)
        st.plotly_chart(fig_tod, use_container_width=True)
