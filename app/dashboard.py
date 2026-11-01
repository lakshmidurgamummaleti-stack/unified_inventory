#!/usr/bin/env python3
"""
Unified Inventory Control Tower — Streamlit Dashboard
Best-in-class operational UI for inventory unification, ATP, reservations & anomalies.
"""

from __future__ import annotations
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from data_utils import normalize_ground_truth

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

st.set_page_config(
    page_title="Inventory Control Tower",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished look
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0ea5e9 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 40px rgba(14, 165, 233, 0.25);
    }
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stMetric { background: white; border-radius: 12px; padding: 0.75rem; border: 1px solid #e2e8f0; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
    .anomaly-high { color: #dc2626; font-weight: 600; }
    .anomaly-medium { color: #d97706; font-weight: 600; }
    .block-container { padding-top: 1.5rem; }
    [data-testid="stSidebar"] { background: #0f172a; }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stRadio label { color: #94a3b8 !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner="Loading inventory data…")
def load_all():
    products = pd.read_csv(DATA / "products.csv")
    skus = pd.read_csv(DATA / "skus.csv")
    locations = pd.read_csv(DATA / "locations.csv")
    balances = pd.read_csv(DATA / "inventory_balances.csv")
    movements = pd.read_csv(DATA / "inventory_movements.csv", parse_dates=["occurred_at"])
    orders = pd.read_csv(DATA / "orders.csv", parse_dates=["order_ts"])
    lines = pd.read_csv(DATA / "order_lines.csv")
    reservations = pd.read_csv(DATA / "reservations.csv", parse_dates=["reserved_at", "expires_at"])
    shipments = pd.read_csv(DATA / "shipments.csv")
    rules = pd.read_csv(DATA / "replenishment_rules.csv")
    gt = normalize_ground_truth(pd.read_csv(DATA / "ground_truth.csv"))
    with open(DATA / "manifest.json") as f:
        manifest = json.load(f)
    return {
        "products": products, "skus": skus, "locations": locations,
        "balances": balances, "movements": movements, "orders": orders,
        "lines": lines, "reservations": reservations, "shipments": shipments,
        "rules": rules, "gt": gt, "manifest": manifest,
    }

def header():
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;font-size:1.9rem;font-weight:700;">📦 Inventory Control Tower</h1>
        <p style="margin:0.4rem 0 0;opacity:0.9;font-size:1.05rem;">
            Unified view across stores · warehouses · online channels · reservations · safety stock · in-transit
        </p>
    </div>
    """, unsafe_allow_html=True)

def page_overview(data):
    header()
    bal = data["balances"]
    mov = data["movements"]
    orders = data["orders"]
    res = data["reservations"]
    gt = data["gt"]
    manifest = data["manifest"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("SKUs", f"{manifest['counts']['skus']:,}")
    c2.metric("Locations", f"{manifest['counts']['locations']:,}")
    c3.metric("On-hand Units", f"{int(bal['on_hand'].sum()):,}")
    c4.metric("Active Reservations", f"{len(res[res['status']=='active']):,}")
    c5.metric("Open Anomalies", f"{len(gt):,}", delta_color="inverse")

    st.markdown("---")
    col1, col2 = st.columns([1.4, 1])

    with col1:
        st.subheader("Inventory Position by Location Type")
        loc = data["locations"]
        merged = bal.merge(loc[["location_id", "location_type", "name"]], on="location_id", how="left")
        by_type = merged.groupby("location_type").agg(
            on_hand=("on_hand", "sum"),
            reserved=("reserved", "sum"),
            blocked=("blocked", "sum"),
            atp=("available_to_promise", "sum"),
        ).reset_index()
        fig = px.bar(
            by_type, x="location_type", y=["on_hand", "reserved", "blocked", "atp"],
            barmode="group",
            color_discrete_sequence=["#0ea5e9", "#f59e0b", "#ef4444", "#10b981"],
            labels={"value": "Units", "location_type": "Location Type", "variable": "Metric"},
        )
        fig.update_layout(height=380, margin=dict(t=30, b=20), legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Movement Mix (all events)")
        mix = mov["movement_type"].value_counts().reset_index()
        mix.columns = ["type", "count"]
        fig2 = px.pie(mix, values="count", names="type", hole=0.45,
                      color_discrete_sequence=px.colors.qualitative.Set2)
        fig2.update_layout(height=380, margin=dict(t=30, b=20))
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Orders by Channel & Status")
    oc = orders.groupby(["channel", "status"]).size().reset_index(name="count")
    fig3 = px.bar(oc, x="channel", y="count", color="status", barmode="stack",
                  color_discrete_sequence=px.colors.qualitative.Pastel)
    fig3.update_layout(height=360, margin=dict(t=20))
    st.plotly_chart(fig3, use_container_width=True)

def page_atp(data):
    header()
    st.subheader("Available-to-Promise (ATP) Explorer")
    st.caption("ATP = max(0, on_hand − reserved − blocked − safety stock − channel buffer + approved inbound)")

    bal = data["balances"].copy()
    loc = data["locations"]
    skus = data["skus"]
    products = data["products"]

    merged = bal.merge(loc[["location_id", "name", "location_type", "channel"]], on="location_id")
    merged = merged.merge(skus[["sku_id", "sku_code", "product_id", "unit_price"]], on="sku_id")
    merged = merged.merge(products[["product_id", "name", "category", "brand"]], on="product_id", suffixes=("_loc", "_prod"))

    c1, c2, c3 = st.columns(3)
    with c1:
        loc_filter = st.multiselect("Location type", options=sorted(merged["location_type"].unique()), default=None)
    with c2:
        cat_filter = st.multiselect("Category", options=sorted(merged["category"].unique()), default=None)
    with c3:
        min_atp = st.number_input("Min ATP", value=0, min_value=-100)

    df = merged.copy()
    if loc_filter:
        df = df[df["location_type"].isin(loc_filter)]
    if cat_filter:
        df = df[df["category"].isin(cat_filter)]
    df = df[df["available_to_promise"] >= min_atp]

    st.dataframe(
        df[["sku_id", "sku_code", "name_prod", "category", "name_loc", "location_type",
            "on_hand", "reserved", "blocked", "in_transit_in", "available_to_promise"]]
        .rename(columns={"name_prod": "product", "name_loc": "location"})
        .sort_values("available_to_promise", ascending=False)
        .head(500),
        use_container_width=True,
        height=420,
    )

    st.metric("Total ATP (filtered)", f"{int(df['available_to_promise'].sum()):,}")

def page_reservations(data):
    header()
    res = data["reservations"].copy()
    st.subheader("Online Reservations & Expiry")

    status_counts = res["status"].value_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active", int(status_counts.get("active", 0)))
    c2.metric("Fulfilled", int(status_counts.get("fulfilled", 0)))
    c3.metric("Expired", int(status_counts.get("expired", 0)))
    c4.metric("Cancelled / Released", int(status_counts.get("cancelled", 0) + status_counts.get("released", 0)))

    st.markdown("#### Reservation status distribution")
    fig = px.bar(status_counts.reset_index(), x="status", y="count",
                 color="status", color_discrete_sequence=px.colors.qualitative.Bold)
    fig.update_layout(height=300, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Active reservations (sample)")
    active = res[res["status"] == "active"].sort_values("expires_at")
    st.dataframe(active.head(200), use_container_width=True, height=350)

    st.info("On expiry the system must emit a `reservation_release` movement and free the reserved quantity. "
            "Expired-but-still-active rows are labelled in ground_truth.")

def page_movements(data):
    header()
    mov = data["movements"].copy()
    st.subheader("Immutable Inventory Movement Ledger")

    mtype = st.multiselect("Movement type", options=sorted(mov["movement_type"].unique()), default=None)
    df = mov if not mtype else mov[mov["movement_type"].isin(mtype)]

    daily = df.set_index("occurred_at").resample("D").size().reset_index(name="events")
    fig = px.area(daily, x="occurred_at", y="events", title="Movement volume over time")
    fig.update_layout(height=320, margin=dict(t=40))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df.sort_values("occurred_at", ascending=False).head(300),
        use_container_width=True,
        height=400,
    )

def page_anomalies(data):
    header()
    gt = data["gt"]
    st.subheader("Exception & Anomaly Workbench")
    st.caption("Ground-truth labels for deliberate edge cases — never mixed into input features.")

    if gt.empty:
        st.info("No anomaly scenarios are currently available.")
        return

    for _, row in gt.iterrows():
        sev = str(row.get("severity", "unknown"))
        color = "🔴" if sev.lower() == "high" else ("🟠" if sev.lower() == "medium" else "⚪")
        issue = row.get("issue_type", "Unknown issue")
        entity_id = row.get("entity_id", "Unknown entity")
        with st.expander(f"{color} {issue} · {entity_id}", expanded=False):
            st.write(f"**Entity:** {row.get('entity_type', 'Not provided')}")
            st.write(f"**Description:** {row.get('description', row.get('observed_condition', 'Not provided'))}")
            st.write(f"**Expected action:** {row.get('expected_action', 'Not provided')}")
            st.write(f"**Severity:** {sev}")

    st.markdown("---")
    st.dataframe(gt, use_container_width=True)

def page_orders(data):
    header()
    orders = data["orders"]
    lines = data["lines"]
    st.subheader("Orders & Fulfillment Traceability")

    c1, c2 = st.columns(2)
    with c1:
        channel = st.selectbox("Channel", ["All"] + sorted(orders["channel"].unique().tolist()))
    with c2:
        status = st.selectbox("Status", ["All"] + sorted(orders["status"].unique().tolist()))

    df = orders.copy()
    if channel != "All":
        df = df[df["channel"] == channel]
    if status != "All":
        df = df[df["status"] == status]

    st.dataframe(df.sort_values("order_ts", ascending=False).head(400), use_container_width=True, height=380)

    st.markdown("#### Order line detail (selected order)")
    oid = st.selectbox("Order ID", df["order_id"].head(100).tolist())
    st.dataframe(lines[lines["order_id"] == oid], use_container_width=True)

def page_data_quality(data):
    header()
    manifest = data["manifest"]
    st.subheader("Data Quality & Reproducibility")

    st.json(manifest["counts"])
    st.markdown(f"**Seed:** `{manifest['seed']}` · **Scale:** `{manifest['scale']}`")
    st.markdown("#### SHA-256 checksums (for reproducibility verification)")
    st.json(manifest.get("sha256", {}))

    if (DATA / "validation_summary.json").exists():
        with open(DATA / "validation_summary.json") as f:
            val = json.load(f)
        st.success(f"Validation passed: {val.get('passed_count', len(val.get('passed', [])))} checks · {val.get('failed_count', len(val.get('failed', [])))} failures")
        if val.get("warnings"):
            st.warning(val["warnings"])
        if val.get("failed"):
            st.error(val["failed"])

def main():
    data = load_all()

    with st.sidebar:
        st.markdown("## 🧭 Navigation")
        page = st.radio(
            "Go to",
            [
                "Overview",
                "ATP Explorer",
                "Reservations",
                "Movement Ledger",
                "Orders & Fulfillment",
                "Anomaly Workbench",
                "Data Quality",
            ],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.caption("Unified Inventory Platform")
        st.caption(f"Seed {data['manifest']['seed']} · {data['manifest']['scale']} scale")

    if page == "Overview":
        page_overview(data)
    elif page == "ATP Explorer":
        page_atp(data)
    elif page == "Reservations":
        page_reservations(data)
    elif page == "Movement Ledger":
        page_movements(data)
    elif page == "Orders & Fulfillment":
        page_orders(data)
    elif page == "Anomaly Workbench":
        page_anomalies(data)
    else:
        page_data_quality(data)

if __name__ == "__main__":
    main()
