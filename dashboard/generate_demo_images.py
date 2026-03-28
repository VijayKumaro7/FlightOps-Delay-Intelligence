"""
FlightOps Delay Intelligence — Demo Image Generator
Generates PNG screenshots of every dashboard chart using synthetic data.
No database connection required.

Run:  python dashboard/generate_demo_images.py
Output: dashboard/demo_images/*.png
"""

import os
import random
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.cm import ScalarMappable
import seaborn as sns

random.seed(42)
np.random.seed(42)

OUT = os.path.join(os.path.dirname(__file__), "demo_images")
os.makedirs(OUT, exist_ok=True)

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
plt.rcParams.update({"figure.dpi": 150, "savefig.bbox": "tight",
                     "savefig.facecolor": "white"})

CARRIERS = [
    ("AA", "American Airlines"),
    ("DL", "Delta Air Lines"),
    ("UA", "United Airlines"),
    ("WN", "Southwest Airlines"),
    ("B6", "JetBlue Airways"),
    ("AS", "Alaska Airlines"),
    ("NK", "Spirit Airlines"),
    ("F9", "Frontier Airlines"),
]
CARRIER_NAMES = {c[0]: c[1] for c in CARRIERS}
CARRIER_CODES = [c[0] for c in CARRIERS]

AIRPORTS = ["ATL", "LAX", "ORD", "DFW", "DEN", "JFK", "SFO", "SEA", "MIA", "BOS", "LAS", "PHX"]

AIRPORT_COORDS = {
    "ATL": (33.6407, -84.4277,  "Atlanta",       "GA"),
    "LAX": (33.9425, -118.4081, "Los Angeles",   "CA"),
    "ORD": (41.9742, -87.9073,  "Chicago",       "IL"),
    "DFW": (32.8998, -97.0403,  "Dallas",        "TX"),
    "DEN": (39.8561, -104.6737, "Denver",        "CO"),
    "JFK": (40.6413, -73.7781,  "New York",      "NY"),
    "SFO": (37.6213, -122.379,  "San Francisco", "CA"),
    "SEA": (47.4502, -122.3088, "Seattle",       "WA"),
    "MIA": (25.7959, -80.287,   "Miami",         "FL"),
    "BOS": (42.3656, -71.0096,  "Boston",        "MA"),
    "LAS": (36.084,  -115.1537, "Las Vegas",     "NV"),
    "PHX": (33.4373, -112.0078, "Phoenix",       "AZ"),
}

# Colour helpers
def rate_color(val, vmin=10, vmax=35, cmap="RdYlGn_r"):
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    return plt.cm.get_cmap(cmap)(norm(val))

def save(fig, name):
    path = os.path.join(OUT, f"{name}.png")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✓  {name}.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CARRIER RANKINGS — horizontal bar
# ═══════════════════════════════════════════════════════════════════════════════
def gen_carrier_rankings():
    delay_rates = {"AS": 11.2, "DL": 13.8, "WN": 15.4, "AA": 17.9,
                   "UA": 19.1, "B6": 22.3, "F9": 26.7, "NK": 29.4}
    names  = [CARRIER_NAMES[c] for c in CARRIER_CODES]
    rates  = [delay_rates[c] for c in CARRIER_CODES]
    df = pd.DataFrame({"carrier": names, "delay_rate_pct": rates})
    df = df.sort_values("delay_rate_pct")

    fig, ax = plt.subplots(figsize=(11, 6))
    colors = [rate_color(v) for v in df["delay_rate_pct"]]
    bars = ax.barh(df["carrier"], df["delay_rate_pct"], color=colors, edgecolor="white", height=0.65)
    for bar, val in zip(bars, df["delay_rate_pct"]):
        ax.text(val + 0.4, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=11)
    ax.set_xlabel("Delay Rate (%)")
    ax.set_title("Carrier On-Time Rankings  —  Delay Rate by Carrier (lower is better)",
                 fontsize=13, fontweight="bold", pad=14)
    ax.set_xlim(0, 36)
    ax.axvline(15, color="steelblue", linestyle="--", linewidth=1.2, alpha=0.6, label="15% SLA threshold")
    ax.legend(fontsize=10)
    fig.tight_layout()
    save(fig, "01_carrier_rankings")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MONTH-OVER-MONTH TREND — multi-line
# ═══════════════════════════════════════════════════════════════════════════════
def gen_mom_trend():
    months = [f"{m:02d}" for m in range(1, 13)]
    base   = {"AS": 11, "DL": 14, "WN": 15, "AA": 18, "UA": 19, "B6": 22, "F9": 27, "NK": 29}
    palette = sns.color_palette("tab10", n_colors=len(CARRIERS))

    fig, ax = plt.subplots(figsize=(13, 6))
    for idx, (code, name) in enumerate(CARRIERS):
        vals = []
        v = base[code]
        for _ in months:
            v += random.uniform(-2.5, 2.5)
            v = max(5, min(40, v))
            vals.append(round(v, 2))
        ax.plot(months, vals, marker="o", label=name, color=palette[idx], linewidth=2)

    ax.set_xlabel("Month (2023)")
    ax.set_ylabel("Delay Rate (%)")
    ax.set_title("Month-over-Month Delay Trend  —  Monthly Delay Rate per Carrier",
                 fontsize=13, fontweight="bold", pad=14)
    ax.legend(fontsize=9, ncol=2, loc="upper left")
    ax.axhline(15, color="steelblue", linestyle="--", linewidth=1, alpha=0.5, label="15% SLA")
    fig.tight_layout()
    save(fig, "02_mom_trend")


# ═══════════════════════════════════════════════════════════════════════════════
# 3a. ROOT CAUSE — stacked bar
# ═══════════════════════════════════════════════════════════════════════════════
def gen_root_cause_stacked():
    causes     = ["Carrier", "Weather", "NAS", "Security", "Late Aircraft"]
    clr        = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2"]
    rows = []
    for code, name in CARRIERS:
        c  = round(random.uniform(30, 40), 1)
        w  = round(random.uniform(15, 25), 1)
        n  = round(random.uniform(15, 25), 1)
        s  = round(random.uniform(1, 4), 1)
        la = round(100 - c - w - n - s, 1)
        rows.append([name, c, w, n, s, la])
    df = pd.DataFrame(rows, columns=["carrier"] + causes)

    fig, ax = plt.subplots(figsize=(12, 6))
    bottom = np.zeros(len(df))
    for cause, color in zip(causes, clr):
        ax.bar(df["carrier"], df[cause], bottom=bottom, label=cause,
               color=color, edgecolor="white", width=0.6)
        bottom += df[cause].values

    ax.set_ylabel("% of Delay Minutes")
    ax.set_title("Delay Root Cause Breakdown  —  % of Total Delay Minutes by Carrier",
                 fontsize=13, fontweight="bold", pad=14)
    ax.legend(fontsize=10, loc="upper right")
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    save(fig, "03a_root_cause_stacked")


# ═══════════════════════════════════════════════════════════════════════════════
# 3b. ROOT CAUSE — donut
# ═══════════════════════════════════════════════════════════════════════════════
def gen_root_cause_donut():
    labels = ["Carrier", "Weather", "NAS", "Security", "Late Aircraft"]
    values = [35.0, 20.0, 20.0, 2.0, 23.0]
    clrs   = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2"]

    fig, ax = plt.subplots(figsize=(8, 7))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct="%1.1f%%",
        colors=clrs, startangle=140,
        wedgeprops={"width": 0.55, "edgecolor": "white"},
        textprops={"fontsize": 12},
    )
    ax.set_title("Overall Delay Cause Distribution  —  All Carriers Combined",
                 fontsize=13, fontweight="bold", pad=18)
    fig.tight_layout()
    save(fig, "03b_root_cause_donut")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. AIRPORT SCATTER MAP (US outline approximation)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_airport_bubble_map():
    rows = []
    for code, (lat, lon, city, state) in AIRPORT_COORDS.items():
        avg_delay = round(random.uniform(10, 28), 1)
        rows.append({"code": code, "lat": lat, "lon": lon,
                     "city": city, "avg_delay": avg_delay})
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_facecolor("#d9eaf7")
    # rough US bounding box
    ax.set_xlim(-128, -65)
    ax.set_ylim(24, 50)

    norm   = plt.Normalize(df["avg_delay"].min(), df["avg_delay"].max())
    cmap   = plt.cm.Reds
    sizes  = (df["avg_delay"] ** 2) * 3

    sc = ax.scatter(df["lon"], df["lat"], c=df["avg_delay"], cmap=cmap,
                    norm=norm, s=sizes, edgecolors="white", linewidths=1.2, zorder=3)
    for _, row in df.iterrows():
        ax.text(row["lon"] + 0.6, row["lat"] + 0.4, row["code"],
                fontsize=9, fontweight="bold", zorder=4)

    cb = fig.colorbar(sc, ax=ax, shrink=0.6, pad=0.02)
    cb.set_label("Avg Dep Delay (min)", fontsize=10)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Airport Bottlenecks  —  Avg Departure Delay by US Hub (bubble size = delay magnitude)",
                 fontsize=13, fontweight="bold", pad=14)
    fig.tight_layout()
    save(fig, "04_airport_bubble_map")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. AIRPORT DELAY RATE — bar
# ═══════════════════════════════════════════════════════════════════════════════
def gen_airport_delay_bar():
    rates = {ap: round(random.uniform(14, 34), 1) for ap in AIRPORTS}
    df = pd.DataFrame(rates.items(), columns=["airport", "rate"]).sort_values("rate")

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [rate_color(v, vmin=14, vmax=34) for v in df["rate"]]
    bars = ax.barh(df["airport"], df["rate"], color=colors, edgecolor="white", height=0.65)
    for bar, val in zip(bars, df["rate"]):
        ax.text(val + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=10)
    ax.set_xlabel("Departure Delay Rate (%)")
    ax.set_title("Top Airports by Departure Delay Rate",
                 fontsize=13, fontweight="bold", pad=14)
    ax.set_xlim(0, 40)
    fig.tight_layout()
    save(fig, "05_airport_delay_bar")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PROPAGATION RATIO — bar
# ═══════════════════════════════════════════════════════════════════════════════
def gen_propagation_bar():
    sample = random.sample(AIRPORTS, 10)
    ratios = {ap: round(random.uniform(25, 70), 1) for ap in sample}
    df = pd.DataFrame(ratios.items(), columns=["airport", "ratio"]).sort_values("ratio")

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [plt.cm.Blues(v / 100) for v in df["ratio"]]
    bars = ax.barh(df["airport"], df["ratio"], color=colors, edgecolor="white", height=0.65)
    for bar, val in zip(bars, df["ratio"]):
        ax.text(val + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}%", va="center", fontsize=10)
    ax.set_xlabel("Propagation Ratio (%)")
    ax.set_title("Delay Propagation  —  Cascade Delay Ratio by Airport\n"
                 "(% of arrival delay from upstream late aircraft)",
                 fontsize=13, fontweight="bold", pad=14)
    ax.set_xlim(0, 85)
    fig.tight_layout()
    save(fig, "06_propagation_bar")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. ROUTE HEATMAP
# ═══════════════════════════════════════════════════════════════════════════════
def gen_route_heatmap():
    ap   = AIRPORTS[:8]
    arr = np.random.uniform(10, 35, (len(ap), len(ap)))
    np.fill_diagonal(arr, np.nan)
    data = pd.DataFrame(arr, index=ap, columns=ap)

    fig, ax = plt.subplots(figsize=(10, 8))
    mask = np.isnan(data.values)
    sns.heatmap(data, annot=True, fmt=".0f", cmap="RdYlGn_r",
                linewidths=0.5, ax=ax, mask=mask,
                cbar_kws={"label": "Delay Rate (%)"})
    ax.set_xlabel("Destination")
    ax.set_ylabel("Origin")
    ax.set_title("Route Delay Rate Heatmap  —  Origin × Destination",
                 fontsize=13, fontweight="bold", pad=14)
    fig.tight_layout()
    save(fig, "07_route_heatmap")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. TIME-OF-DAY HEATMAP
# ═══════════════════════════════════════════════════════════════════════════════
def gen_time_of_day_heatmap():
    slots = ["12AM-6AM", "6AM-10AM", "10AM-2PM", "2PM-6PM", "6PM-12AM"]
    ap    = AIRPORTS[:8]
    base  = np.array([5, 8, 12, 18, 24])
    data  = pd.DataFrame(
        np.clip(np.random.normal(base, 2.5, (len(ap), len(slots))), 2, 38),
        index=ap, columns=slots,
    )

    fig, ax = plt.subplots(figsize=(11, 6))
    sns.heatmap(data, annot=True, fmt=".1f", cmap="RdYlGn_r",
                linewidths=0.5, ax=ax,
                cbar_kws={"label": "Avg Dep Delay (min)"})
    ax.set_xlabel("Time Slot")
    ax.set_ylabel("Airport")
    ax.set_title("Time-of-Day Delay Pattern  —  Avg Departure Delay by Airport × Time of Day",
                 fontsize=13, fontweight="bold", pad=14)
    fig.tight_layout()
    save(fig, "08_time_of_day_heatmap")


# ═══════════════════════════════════════════════════════════════════════════════
# 9. SLA BREACH SEVERITY — donut
# ═══════════════════════════════════════════════════════════════════════════════
def gen_sla_severity_donut():
    labels = ["CRITICAL", "HIGH", "MEDIUM"]
    values = [8, 14, 21]
    clrs   = ["#e74c3c", "#e67e22", "#f1c40f"]

    fig, ax = plt.subplots(figsize=(7, 6))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct="%1.0f%%",
        colors=clrs, startangle=90,
        wedgeprops={"width": 0.52, "edgecolor": "white"},
        textprops={"fontsize": 13},
    )
    ax.set_title("Active SLA Breach Severity Distribution",
                 fontsize=13, fontweight="bold", pad=18)
    # centre count
    ax.text(0, 0, f"{sum(values)}\nBreaches", ha="center", va="center",
            fontsize=14, fontweight="bold", color="#333")
    fig.tight_layout()
    save(fig, "09_sla_severity_donut")


# ═══════════════════════════════════════════════════════════════════════════════
# 10. CHRONIC OFFENDERS — bar
# ═══════════════════════════════════════════════════════════════════════════════
def gen_chronic_offenders():
    routes_data = [
        ("JFK → LAX", "CHRONIC",      9),
        ("ORD → DFW", "CHRONIC",      8),
        ("MIA → JFK", "CHRONIC",      7),
        ("DEN → ORD", "RECURRING",    5),
        ("LAX → SFO", "RECURRING",    4),
        ("ATL → BOS", "RECURRING",    4),
        ("PHX → LAS", "RECURRING",    3),
        ("SEA → DEN", "INTERMITTENT", 3),
    ]
    df = pd.DataFrame(routes_data, columns=["route", "pattern", "count"])
    df = df.sort_values("count")
    pcolors = {"CHRONIC": "#c0392b", "RECURRING": "#e67e22", "INTERMITTENT": "#3498db"}
    colors  = [pcolors[p] for p in df["pattern"]]

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(df["route"], df["count"], color=colors, edgecolor="white", height=0.65)
    for bar, val in zip(bars, df["count"]):
        ax.text(val + 0.1, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=11, fontweight="bold")
    ax.set_xlabel("Breach Count (last 90 days)")
    ax.set_title("Chronic Offenders  —  Routes with Repeated SLA Breaches",
                 fontsize=13, fontweight="bold", pad=14)
    legend_patches = [mpatches.Patch(color=c, label=p) for p, c in pcolors.items()]
    ax.legend(handles=legend_patches, fontsize=10, loc="lower right")
    ax.set_xlim(0, 12)
    fig.tight_layout()
    save(fig, "10_chronic_offenders")


# ═══════════════════════════════════════════════════════════════════════════════
# 11. CARRIER SLA COMPLIANCE GAUGES (as a grouped bar + colour fill)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_sla_gauges():
    compliance = {"DL": 95.2, "AS": 93.8, "WN": 91.0, "AA": 88.5,
                  "UA": 84.3, "B6": 79.6, "F9": 72.1, "NK": 65.4}
    codes  = list(compliance.keys())
    names  = [CARRIER_NAMES[c] for c in codes]
    values = [compliance[c] for c in codes]
    colors = ["#27ae60" if v >= 90 else "#e67e22" if v >= 75 else "#e74c3c" for v in values]

    fig, axes = plt.subplots(2, 4, figsize=(14, 7), subplot_kw=dict(aspect="equal"))
    for ax, code, val, color in zip(axes.flat, codes, values, colors):
        theta = np.linspace(0, np.pi, 200)
        ax.plot(np.cos(theta), np.sin(theta), color="#ddd", linewidth=14, solid_capstyle="round")
        fill_theta = np.linspace(0, np.pi * val / 100, 200)
        ax.plot(np.cos(fill_theta), np.sin(fill_theta), color=color,
                linewidth=14, solid_capstyle="round")
        ax.text(0, -0.05, f"{val:.1f}%", ha="center", va="center",
                fontsize=16, fontweight="bold", color=color)
        ax.text(0, -0.35, CARRIER_NAMES[code], ha="center", va="center",
                fontsize=9, color="#444")
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-0.5, 1.2)
        ax.axis("off")

    fig.suptitle("Carrier SLA Compliance Gauges  —  % of Routes Meeting SLA (last 30 days)",
                 fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    save(fig, "11_sla_compliance_gauges")


# ═══════════════════════════════════════════════════════════════════════════════
# 12. CARRIER SLA COMPLIANCE BAR
# ═══════════════════════════════════════════════════════════════════════════════
def gen_sla_compliance_bar():
    data = [
        ("Delta Air Lines",    95.2),
        ("Alaska Airlines",    93.8),
        ("Southwest Airlines", 91.0),
        ("American Airlines",  88.5),
        ("United Airlines",    84.3),
        ("JetBlue Airways",    79.6),
        ("Frontier Airlines",  72.1),
        ("Spirit Airlines",    65.4),
    ]
    df = pd.DataFrame(data, columns=["carrier", "compliance"])
    df = df.sort_values("compliance")

    norm   = plt.Normalize(50, 100)
    colors = [plt.cm.RdYlGn(norm(v)) for v in df["compliance"]]

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(df["carrier"], df["compliance"], color=colors,
                   edgecolor="white", height=0.65)
    for bar, val in zip(bars, df["compliance"]):
        ax.text(val + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=11)
    ax.axvline(90, color="green",  linestyle="--", linewidth=1.4, label="90% target")
    ax.axvline(75, color="orange", linestyle="--", linewidth=1.4, label="75% at-risk")
    ax.set_xlabel("SLA Compliance (%)")
    ax.set_xlim(50, 105)
    ax.set_title("Carrier SLA Compliance Rate  —  % of Routes Meeting SLA Threshold (last 30 days)",
                 fontsize=13, fontweight="bold", pad=14)
    ax.legend(fontsize=10, loc="lower right")
    fig.tight_layout()
    save(fig, "12_sla_compliance_bar")


# ═══════════════════════════════════════════════════════════════════════════════
# Run all
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating FlightOps dashboard demo images...\n")
    gen_carrier_rankings()
    gen_mom_trend()
    gen_root_cause_stacked()
    gen_root_cause_donut()
    gen_airport_bubble_map()
    gen_airport_delay_bar()
    gen_propagation_bar()
    gen_route_heatmap()
    gen_time_of_day_heatmap()
    gen_sla_severity_donut()
    gen_chronic_offenders()
    gen_sla_gauges()
    gen_sla_compliance_bar()
    print(f"\nDone! 13 images saved to {OUT}/")
