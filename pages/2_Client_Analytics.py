"""
pages/2_Client_Analytics.py
--------------------------------
Professional Client Analytics Dashboard

This page is built to mirror the dark modern style of the first dashboard
and uses your Google Sheet data for KPI cards, filters, charts and tables.
"""

import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import SHEET_URL, WORKSHEETS
from utils.gsheet_connector import clear_cache, load_sheet_data
from utils.styling import (
    fmt_inr_auto,
    fmt_pct,
    inject_custom_css,
    kpi_card,
    render_header,
    render_kpi_row,
    section_header,
)

st.set_page_config(page_title="Client Analytics", page_icon="👥", layout="wide")
inject_custom_css()

PLOTLY_DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0e1626",
    plot_bgcolor="#0e1626",
    font=dict(color="#e2e8f0"),
    margin=dict(l=10, r=10, t=50, b=10),
)

MONTH_ORDER_APR_MAR = {
    "apr": 1, "april": 1,
    "may": 2,
    "jun": 3, "june": 3,
    "jul": 4, "july": 4,
    "aug": 5, "august": 5,
    "sep": 6, "sept": 6, "september": 6,
    "oct": 7, "october": 7,
    "nov": 8, "november": 8,
    "dec": 9, "december": 9,
    "jan": 10, "january": 10,
    "feb": 11, "february": 11,
    "mar": 12, "march": 12,
}

# =========================================================
# ------------------- LOAD DATA -----------------------------
# =========================================================
top_col1, top_col2 = st.columns([6, 1])
with top_col2:
    if st.button("🔄 Refresh Data"):
        clear_cache()
        st.rerun()

try:
    df = load_sheet_data(SHEET_URL, WORKSHEETS["client_analytics"])
except Exception as e:
    st.error(f"Google Sheet se data load nahi ho paya: {e}")
    st.stop()

if df.empty:
    st.warning("Sheet me data nahi mila. Sheet aur tab name check karein.")
    st.stop()

# ---------- Helpers ----------
def safe_div(a, b):
    return (a / b * 100) if b else 0


def find_first_col(columns, candidates):
    for col in candidates:
        if col in columns:
            return col
    return None


def normalize_status(value):
    if pd.isna(value):
        return ""
    s = str(value).strip().lower()
    if s in {"issued", "policy issued"}:
        return "Issued"
    if s in {"rejected", "policy rejected"}:
        return "Rejected"
    if s in {"policy cancel", "cancelled", "cancel"}:
        return "Cancelled"
    if s in {"counter offer acceptance pending", "pending"}:
        return "Pending"
    return str(value).strip()


def classify_policy_type(value):
    if pd.isna(value):
        return ""
    s = str(value).strip().lower()
    if "fresh" in s:
        return "Fresh"
    if "market" in s or "renewal" in s or "port" in s:
        return "Market Renewal"
    return str(value).strip()


def clean_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False).str.replace("₹", "", regex=False).str.strip(), errors="coerce").fillna(0)


def add_table_download(dataframe: pd.DataFrame, file_name: str, key: str):
    st.download_button(
        "Download CSV",
        data=dataframe.to_csv(index=False).encode("utf-8-sig"),
        file_name=file_name,
        mime="text/csv",
        key=key,
    )


# ---------- Data cleaning ----------
for num_col in [
    "Policy Premium (incl. GST)",
    "Policy Premium (excl. GST)",
    "Total Premium (incl. GST)",
    "Total Premium (excl. GST)",
    "Collected Premium",
    "Policy Sum Assured",
    "Total Sum Assured",
    "Rev PI Sum Assured",
    "Cyber Premium (incl. GST)",
    "Cyber Premium (excl. GST)",
    "GPA (excl. GST)",
    "GPA (inc. GST)",
    "CP Premium (incl. GST)",
    "CP Premium (excl. GST)",
]:
    if num_col in df.columns:
        df[num_col] = clean_numeric(df[num_col])

# Transaction date (requested by user)
transaction_date_col = find_first_col(df.columns, ["Transasction Date", "Transaction Date", "Booking Date"])
if transaction_date_col:
    df["Txn Date"] = pd.to_datetime(df[transaction_date_col], errors="coerce", dayfirst=True)
else:
    df["Txn Date"] = pd.NaT

if "Txn Date" in df.columns:
    df["Month"] = df["Txn Date"].dt.strftime("%b %Y")
    df["Month"] = df["Month"].fillna("")

for txt_col in [
    "Final Policy Status",
    "Booking Status",
    "Payment Status",
    "Source of Lead",
    "RM Name",
    "Team Leader",
    "Product",
    "Insurer",
    "Policy Type",
    "Region",
    "State",
    "City",
    "Association",
    "Specialization",
    "Latest Visit Source",
    "Policy Tenure",
    "Month",
    "Online/Offline",
    "Payment Mode",
]:
    if txt_col in df.columns:
        df[txt_col] = df[txt_col].astype(str).str.strip().replace({"-": "", "nan": ""})

# Preferred premium and sum assured columns
premium_col = find_first_col(
    df.columns,
    [
        "Total Premium (excl. GST)",
        "Total Premium (incl. GST)",
        "Policy Premium (excl. GST)",
        "Policy Premium (incl. GST)",
        "Collected Premium",
    ],
)

sum_assured_col = find_first_col(df.columns, ["Total Sum Assured", "Policy Sum Assured", "Rev PI Sum Assured"])
policy_col = find_first_col(df.columns, ["Policy Type", "Fresh/Port", "Type"])
status_source = find_first_col(df.columns, ["Final Policy Status", "Booking Status", "Policy Status", "Status"])
rm_col = find_first_col(df.columns, ["RM Name", "RM"])
team_col = find_first_col(df.columns, ["Team Leader", "Team"])
state_col = find_first_col(df.columns, ["State", "STATE"])
city_col = find_first_col(df.columns, ["City", "CITY"])
association_col = find_first_col(df.columns, ["Association", "Association Name"])
specialization_col = find_first_col(df.columns, ["Specialization", "Specialization Name"])
insurer_col = find_first_col(df.columns, ["Insurer", "Insurance Company"])
policy_type_col = find_first_col(df.columns, ["Policy Type", "Fresh/Port", "Type"])
region_col = find_first_col(df.columns, ["Region", "REGION"])
latest_visit_col = find_first_col(df.columns, ["Latest Visit Source", "Latest Visit"])
policy_tenure_col = find_first_col(df.columns, ["Policy Tenure", "Tenure"])
lead_col = find_first_col(df.columns, ["Client Name", "Lead ID", "Booking ID"])

if status_source:
    df["StatusNorm"] = df[status_source].apply(normalize_status)
else:
    df["StatusNorm"] = ""

if policy_type_col:
    df["Policy Bucket"] = df[policy_type_col].apply(classify_policy_type)
else:
    df["Policy Bucket"] = ""

# =========================================================
# ---------------------- FILTERS (sidebar) ------------------
# =========================================================
st.sidebar.header("🔍 Filters")
filtered_df = df.copy()

# Date range
if "Txn Date" in filtered_df.columns and filtered_df["Txn Date"].notna().any():
    min_date, max_date = filtered_df["Txn Date"].min(), filtered_df["Txn Date"].max()
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        filtered_df = filtered_df[
            (filtered_df["Txn Date"] >= pd.to_datetime(date_range[0]))
            & (filtered_df["Txn Date"] <= pd.to_datetime(date_range[1]))
        ]

# Multi-select filters
for col, label in [
    ("Month", "Month"),
    (rm_col, "RM Name"),
    (team_col, "Team Leader"),
    (state_col, "State"),
    (city_col, "City"),
    (association_col, "Association"),
    (specialization_col, "Specialization"),
    (insurer_col, "Insurer"),
    (policy_type_col, "Policy Type"),
    (policy_tenure_col, "Policy Tenure"),
    (region_col, "Region"),
    (latest_visit_col, "Latest Visit Source"),
    ("StatusNorm", "Final Policy Status"),
]:
    if col and col in filtered_df.columns:
        options = sorted([str(x).strip() for x in filtered_df[col].dropna().astype(str).unique().tolist() if str(x).strip()])
        selected = st.sidebar.multiselect(label, options, default=[])
        if selected:
            filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected)]

# Sum assured slider
if sum_assured_col and sum_assured_col in filtered_df.columns:
    min_sa = float(filtered_df[sum_assured_col].min())
    max_sa = float(filtered_df[sum_assured_col].max())
    if max_sa >= min_sa:
        sa_range = st.sidebar.slider(
            "Total Sum Assured",
            min_value=int(min_sa),
            max_value=int(max_sa),
            value=(int(min_sa), int(max_sa)),
        )
        filtered_df = filtered_df[
            (filtered_df[sum_assured_col] >= sa_range[0])
            & (filtered_df[sum_assured_col] <= sa_range[1])
        ]

# =========================================================
# ------------------- HEADER --------------------------------
# =========================================================
render_header(
    "👥",
    "Client Analytics",
    f"{len(filtered_df):,} records",
)

# =========================================================
# ------------------- KPI CALCULATIONS ----------------------
# =========================================================
if premium_col and premium_col in filtered_df.columns:
    total_premium = float(filtered_df[premium_col].sum())
else:
    total_premium = 0.0

total_nop = len(filtered_df)

issued_df = filtered_df[filtered_df["StatusNorm"] == "Issued"] if "StatusNorm" in filtered_df.columns else filtered_df.iloc[0:0]
rejected_df = filtered_df[filtered_df["StatusNorm"] == "Rejected"] if "StatusNorm" in filtered_df.columns else filtered_df.iloc[0:0]
fresh_df = filtered_df[filtered_df["Policy Bucket"] == "Fresh"] if "Policy Bucket" in filtered_df.columns else filtered_df.iloc[0:0]
market_df = filtered_df[filtered_df["Policy Bucket"] == "Market Renewal"] if "Policy Bucket" in filtered_df.columns else filtered_df.iloc[0:0]

issued_premium = float(issued_df[premium_col].sum()) if premium_col and not issued_df.empty else 0.0
rejected_premium = float(rejected_df[premium_col].sum()) if premium_col and not rejected_df.empty else 0.0
fresh_premium = float(fresh_df[premium_col].sum()) if premium_col and not fresh_df.empty else 0.0
market_premium = float(market_df[premium_col].sum()) if premium_col and not market_df.empty else 0.0

issued_nop = len(issued_df)
rejected_nop = len(rejected_df)
fresh_nop = len(fresh_df)
market_nop = len(market_df)

issued_pct = safe_div(issued_premium, total_premium)
rejected_pct = safe_div(rejected_premium, total_premium)
fresh_pct = safe_div(fresh_premium, total_premium)
market_pct = safe_div(market_premium, total_premium)

unique_clients = filtered_df[lead_col].nunique() if lead_col and lead_col in filtered_df.columns else len(filtered_df)
avg_ticket_size = (total_premium / total_nop) if total_nop else 0
avg_sum_assured = float(filtered_df[sum_assured_col].mean()) if sum_assured_col and sum_assured_col in filtered_df.columns else 0

# =========================================================
# ------------------- KPI CARDS ------------------------------
# =========================================================
section_header("📊", "Key Performance Indicators")

row1 = [
    kpi_card("💰", "TOTAL PREMIUM", fmt_inr_auto(total_premium), f"{total_nop:,} Total NOP", accent="#3b82f6"),
    kpi_card("✅", "ISSUED PREMIUM", fmt_inr_auto(issued_premium), f"{issued_nop:,} Issued NOP · {fmt_pct(issued_pct)}", accent="#22c55e"),
    kpi_card("❌", "REJECTED PREMIUM", fmt_inr_auto(rejected_premium), f"{rejected_nop:,} Rejected NOP · {fmt_pct(rejected_pct)}", accent="#ef4444"),
    kpi_card("🆕", "FRESH PREMIUM", fmt_inr_auto(fresh_premium), f"{fresh_nop:,} Fresh NOP · {fmt_pct(fresh_pct)}", accent="#06b6d4"),
]
render_kpi_row(row1)

row2 = [
    kpi_card("🔄", "MARKET RENEWAL PREMIUM", fmt_inr_auto(market_premium), f"{market_nop:,} Market Renewal NOP · {fmt_pct(market_pct)}", accent="#f59e0b"),
    kpi_card("👥", "UNIQUE CLIENT", f"{unique_clients:,}", "Count of unique Lead ID", accent="#a855f7"),
    kpi_card("📈", "AVERAGE TICKET SIZE", fmt_inr_auto(avg_ticket_size), "Total Premium / Total Records", accent="#ec4899"),
    kpi_card("🛡️", "AVERAGE SUM ASSURED", fmt_inr_auto(avg_sum_assured), "Average of Total Sum Assured", accent="#38bdf8"),
]
render_kpi_row(row2)

# =========================================================
# ------------------- CHARTS -------------------------------
# =========================================================
section_header("📈", "MOM Premium Trend")

mom_df = filtered_df.groupby("Month").agg(
    Total_Premium=(premium_col, "sum") if premium_col else ("Booking ID", "count"),
    Total_NOP=("Booking ID", "count") if "Booking ID" in filtered_df.columns else (lead_col, "count") if lead_col else (premium_col, "count"),
).reset_index()

if not mom_df.empty and "Month" in mom_df.columns:
    fig_mom = go.Figure()
    fig_mom.add_trace(go.Scatter(
        x=mom_df["Month"],
        y=mom_df["Total_Premium"],
        mode="lines+markers+text",
        name="Premium",
        text=[fmt_inr_auto(v) for v in mom_df["Total_Premium"]],
        textposition="top center",
        line=dict(color="#38bdf8", width=3),
        marker=dict(size=8, color="#38bdf8"),
    ))
    fig_mom.update_layout(**PLOTLY_DARK_LAYOUT, title="MOM Premium Trend")
    st.plotly_chart(fig_mom, width="stretch")

section_header("🍩", "Fresh vs Market Renewal & Insurer")
col1, col2 = st.columns(2)

with col1:
    if "Policy Bucket" in filtered_df.columns:
        policy_view = st.radio("Show by", ["Premium", "NOP Count"], horizontal=True, key="policy_view")
        if policy_view == "Premium":
            policy_data = filtered_df.groupby("Policy Bucket")[premium_col].sum().reset_index(name="Value") if premium_col else pd.DataFrame(columns=["Policy Bucket", "Value"])
            title = "Fresh vs Market Renewal Premium"
        else:
            policy_data = filtered_df.groupby("Policy Bucket").size().reset_index(name="Value")
            title = "Fresh vs Market Renewal NOP"
        policy_data = policy_data[policy_data["Policy Bucket"] != ""]
        if not policy_data.empty:
            fig_policy = px.pie(policy_data, names="Policy Bucket", values="Value", hole=0.6, title=title)
            fig_policy.update_traces(textinfo="value+percent", textposition="inside")
            fig_policy.update_layout(**PLOTLY_DARK_LAYOUT)
            st.plotly_chart(fig_policy, width="stretch")

with col2:
    if insurer_col and insurer_col in filtered_df.columns and premium_col:
        insurer_data = filtered_df.groupby(insurer_col)[premium_col].sum().reset_index(name="Premium")
        insurer_data = insurer_data.sort_values("Premium", ascending=False).head(8)
        fig_insurer = px.pie(insurer_data, names=insurer_col, values="Premium", hole=0.6, title="Insurer wise Premium")
        fig_insurer.update_traces(textinfo="value+percent", textposition="inside")
        fig_insurer.update_layout(**PLOTLY_DARK_LAYOUT)
        st.plotly_chart(fig_insurer, width="stretch")

section_header("🧭", "Status, Region & Top Clients")
col3, col4 = st.columns(2)

with col3:
    if "StatusNorm" in filtered_df.columns and premium_col:
        status_premium = filtered_df.groupby("StatusNorm")[premium_col].sum().reset_index(name="Premium")
        status_premium = status_premium[status_premium["StatusNorm"] != ""]
        fig_status = px.pie(status_premium, names="StatusNorm", values="Premium", hole=0.55, title="Final Policy Status wise Premium")
        fig_status.update_traces(textinfo="value+percent", textposition="inside")
        fig_status.update_layout(**PLOTLY_DARK_LAYOUT)
        st.plotly_chart(fig_status, width="stretch")

with col4:
    if region_col and region_col in filtered_df.columns and premium_col:
        region_premium = filtered_df.groupby(region_col)[premium_col].sum().reset_index(name="Premium")
        region_premium = region_premium.sort_values("Premium", ascending=False)
        fig_region = px.pie(region_premium, names=region_col, values="Premium", hole=0.55, title="Region wise Premium")
        fig_region.update_traces(textinfo="value+percent", textposition="inside")
        fig_region.update_layout(**PLOTLY_DARK_LAYOUT)
        st.plotly_chart(fig_region, width="stretch")

section_header("🏆", "Top 10 Client by Premium")
if lead_col and lead_col in filtered_df.columns and premium_col:
    client_df = filtered_df.groupby(lead_col)[premium_col].sum().reset_index(name="Premium")
    client_df = client_df.sort_values("Premium", ascending=False).head(10)
    client_df = client_df.sort_values("Premium", ascending=True).reset_index(drop=True)

    fig_client = go.Figure(go.Bar(
        x=client_df["Premium"],
        y=client_df[lead_col],
        orientation="h",
        text=[fmt_inr_auto(v) for v in client_df["Premium"]],
        textposition="outside",
        marker=dict(color="#38bdf8", line=dict(color="#0f172a", width=1.2)),
    ))
    # Merge base dark layout but avoid duplicate 'margin' key which causes TypeError
    layout_base = PLOTLY_DARK_LAYOUT.copy()
    layout_base.pop("margin", None)
    fig_client.update_layout(
        **layout_base,
        title="Top 10 Client by Premium",
        xaxis_title="Premium",
        yaxis_title="Client",
        bargap=0.25,
        margin=dict(l=20, r=20, t=50, b=20),
        showlegend=False,
        xaxis=dict(showgrid=False),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig_client, width="stretch")

# =========================================================
# ------------------- ANALYSIS TABLES -----------------------
# =========================================================
section_header("📋", "Analysis Tables")


def build_group_table(group_col, title, include_fresh_market=False):
    if group_col not in filtered_df.columns:
        return None
    base = filtered_df.groupby(group_col).agg(
        Total_Premium=(premium_col, "sum") if premium_col else (lead_col, "count"),
        NOP=(lead_col, "count") if lead_col else (premium_col, "count"),
    ).reset_index()
    base = base.sort_values("Total_Premium", ascending=False)
    base["ATS"] = base["Total_Premium"] / base["NOP"]
    base["Premium_Cont%"] = base["Total_Premium"] / total_premium * 100 if total_premium else 0
    base["NOP_Cont%"] = base["NOP"] / total_nop * 100 if total_nop else 0

    if include_fresh_market and premium_col:
        fresh = filtered_df.groupby(group_col).apply(lambda g: float(g.loc[g["Policy Bucket"] == "Fresh", premium_col].sum()) if "Policy Bucket" in g.columns else 0).reset_index(name="Fresh_Premium")
        market = filtered_df.groupby(group_col).apply(lambda g: float(g.loc[g["Policy Bucket"] == "Market Renewal", premium_col].sum()) if "Policy Bucket" in g.columns else 0).reset_index(name="Market_Renewal_Premium")
        base = base.merge(fresh, on=group_col, how="left").merge(market, on=group_col, how="left")
        base["Fresh_Premium%"] = base["Fresh_Premium"] / base["Total_Premium"] * 100
        base["Market_Renewal_Premium%"] = base["Market_Renewal_Premium"] / base["Total_Premium"] * 100

    total_row = pd.DataFrame([{
        group_col: "TOTAL",
        "Total_Premium": base["Total_Premium"].sum(),
        "NOP": base["NOP"].sum(),
        "ATS": (base["Total_Premium"].sum() / base["NOP"].sum()) if base["NOP"].sum() else 0,
        "Premium_Cont%": 100,
        "NOP_Cont%": 100,
    }])
    if include_fresh_market:
        total_row["Fresh_Premium"] = base["Fresh_Premium"].sum()
        total_row["Fresh_Premium%"] = (base["Fresh_Premium"].sum() / base["Total_Premium"].sum()) * 100 if base["Total_Premium"].sum() else 0
        total_row["Market_Renewal_Premium"] = base["Market_Renewal_Premium"].sum()
        total_row["Market_Renewal_Premium%"] = (base["Market_Renewal_Premium"].sum() / base["Total_Premium"].sum()) * 100 if base["Total_Premium"].sum() else 0

    display = pd.concat([base, total_row], ignore_index=True)
    return display

# Association table
association_table = build_group_table(association_col, "Association wise Analysis")
if association_table is not None:
    st.subheader("Association wise Analysis")
    add_table_download(association_table, "association_wise_analysis.csv", "download_association_wise_analysis")
    st.dataframe(
        association_table,
        width="stretch",
        height=320,
        hide_index=True,
        column_config={
            "Total_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Premium_Cont%": st.column_config.NumberColumn(format="%.1f%%"),
            "NOP_Cont%": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

# State table
state_table = build_group_table(state_col, "State wise Analysis")
if state_table is not None:
    st.subheader("State wise Analysis")
    add_table_download(state_table, "state_wise_analysis.csv", "download_state_wise_analysis")
    st.dataframe(
        state_table,
        width="stretch",
        height=320,
        hide_index=True,
        column_config={
            "Total_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Premium_Cont%": st.column_config.NumberColumn(format="%.1f%%"),
            "NOP_Cont%": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

# Latest visit source table
latest_visit_table = build_group_table(latest_visit_col, "Latest Visit Source Analysis")
if latest_visit_table is not None:
    st.subheader("Latest Visit Source Analysis")
    add_table_download(latest_visit_table, "latest_visit_source_analysis.csv", "download_latest_visit_source_analysis")
    st.dataframe(
        latest_visit_table,
        width="stretch",
        height=320,
        hide_index=True,
        column_config={
            "Total_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Premium_Cont%": st.column_config.NumberColumn(format="%.1f%%"),
            "NOP_Cont%": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

# Insurer table
insurer_table = build_group_table(insurer_col, "Insurer wise Analysis", include_fresh_market=True)
if insurer_table is not None:
    st.subheader("Insurer wise Analysis")
    add_table_download(insurer_table, "insurer_wise_analysis.csv", "download_insurer_wise_analysis")
    st.dataframe(
        insurer_table,
        width="stretch",
        height=320,
        hide_index=True,
        column_config={
            "Total_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Premium_Cont%": st.column_config.NumberColumn(format="%.1f%%"),
            "NOP_Cont%": st.column_config.NumberColumn(format="%.1f%%"),
            "Fresh_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Fresh_Premium%": st.column_config.NumberColumn(format="%.1f%%"),
            "Market_Renewal_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Market_Renewal_Premium%": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

# MOM analysis table
mom_table = filtered_df.groupby("Month").agg(
    Total_Premium=(premium_col, "sum") if premium_col else (lead_col, "count"),
    Total_NOP=(lead_col, "count") if lead_col else (premium_col, "count"),
).reset_index()
if not mom_table.empty:
    mom_table["ATS"] = mom_table["Total_Premium"] / mom_table["Total_NOP"]
    mom_table["Issued_Premium"] = filtered_df.groupby("Month").apply(lambda g: float(g.loc[g["StatusNorm"] == "Issued", premium_col].sum()) if premium_col and "StatusNorm" in g.columns else 0).reset_index(name="Issued_Premium")["Issued_Premium"]
    mom_table["Rejected_Premium"] = filtered_df.groupby("Month").apply(lambda g: float(g.loc[g["StatusNorm"] == "Rejected", premium_col].sum()) if premium_col and "StatusNorm" in g.columns else 0).reset_index(name="Rejected_Premium")["Rejected_Premium"]
    mom_table["Fresh_Premium"] = filtered_df.groupby("Month").apply(lambda g: float(g.loc[g["Policy Bucket"] == "Fresh", premium_col].sum()) if premium_col and "Policy Bucket" in g.columns else 0).reset_index(name="Fresh_Premium")["Fresh_Premium"]
    mom_table["Market_Renewal_Premium"] = filtered_df.groupby("Month").apply(lambda g: float(g.loc[g["Policy Bucket"] == "Market Renewal", premium_col].sum()) if premium_col and "Policy Bucket" in g.columns else 0).reset_index(name="Market_Renewal_Premium")["Market_Renewal_Premium"]
    mom_table["Issuance%"] = mom_table["Issued_Premium"] / mom_table["Total_Premium"] * 100
    mom_table["Rejection%"] = mom_table["Rejected_Premium"] / mom_table["Total_Premium"] * 100
    mom_table = mom_table.rename(columns={"Month": "Month"})
    st.subheader("MOM Analysis")
    add_table_download(mom_table, "mom_analysis.csv", "download_mom_analysis")
    st.dataframe(
        mom_table,
        width="stretch",
        height=320,
        hide_index=True,
        column_config={
            "Total_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Issued_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Rejected_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Fresh_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Market_Renewal_Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Issuance%": st.column_config.NumberColumn(format="%.1f%%"),
            "Rejection%": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
