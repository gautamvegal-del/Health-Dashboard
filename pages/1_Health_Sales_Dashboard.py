"""
pages/1_Health_Sales_Dashboard.py
--------------------------------
Health Sales Dashboard - Final version

Columns used from sheet:
Date, RM Name, YTD Premium, Policy Type, Insurer, Leader, Fresh/Port,
Policy Tenure, P&L, Payment Mode, Policy Status, YTD Target, Month

ASSUMPTIONS (agar yeh galat ho to bata dena, formula change kar denge):
- "YTD Achievement" = Sum of YTD Premium (saari rows ka, jo bhi filter laga ho)
- "Total NOP"       = Total policies count (saari rows, status irrespective)
- "ATS"             = YTD Achievement / Total NOP
- Policy Status column me values "Issued" aur "Rejected" expect kiye hain
  (jaisa likha hai exactly waisa hi case-sensitive match hota hai - agar
  sheet me "issued"/"ISSUED" hai to neeche bata dena, fix kar denge)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.gsheet_connector import load_sheet_data, clear_cache
from utils.styling import (
    inject_custom_css, render_header, section_header,
    kpi_card, render_kpi_row, fmt_inr_auto, fmt_pct,
)
from config import SHEET_URL, WORKSHEETS

st.set_page_config(page_title="Health Sales Dashboard", page_icon="💊", layout="wide")
inject_custom_css()

PLOTLY_DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0e1626",
    plot_bgcolor="#0e1626",
    font=dict(color="#e2e8f0"),
    margin=dict(l=10, r=10, t=50, b=10),
)

MONTH_ORDER_APR_MAR = {
    "april": 1, "apr": 1,
    "may": 2,
    "june": 3, "jun": 3,
    "july": 4, "jul": 4,
    "august": 5, "aug": 5,
    "september": 6, "sep": 6, "sept": 6,
    "october": 7, "oct": 7,
    "november": 8, "nov": 8,
    "december": 9, "dec": 9,
    "january": 10, "jan": 10,
    "february": 11, "feb": 11,
    "march": 12, "mar": 12,
}


def month_sort_key(month):
    month_text = str(month).strip().lower()
    first_word = month_text.split()[0] if month_text else ""
    return MONTH_ORDER_APR_MAR.get(first_word, 99), month_text


def sort_month_df(dataframe: pd.DataFrame, month_col: str = "Month") -> pd.DataFrame:
    if month_col not in dataframe.columns:
        return dataframe
    sorted_df = dataframe.copy()
    sorted_df["_month_sort"] = sorted_df[month_col].apply(month_sort_key)
    sorted_df = sorted_df.sort_values("_month_sort").drop(columns="_month_sort")
    return sorted_df


def add_table_download(dataframe: pd.DataFrame, file_name: str, key: str):
    st.download_button(
        "Download CSV",
        data=dataframe.to_csv(index=False).encode("utf-8-sig"),
        file_name=file_name,
        mime="text/csv",
        key=key,
    )

# =========================================================
# ------------------- LOAD DATA -----------------------------
# =========================================================
top_col1, top_col2 = st.columns([6, 1])
with top_col2:
    if st.button("🔄 Refresh Data"):
        clear_cache()
        st.rerun()

try:
    df = load_sheet_data(SHEET_URL, WORKSHEETS["health_sales"])
except Exception as e:
    st.error(f"Google Sheet se data load nahi ho paya: {e}")
    st.stop()

if df.empty:
    st.warning("Sheet me data nahi mila. Sheet aur tab name check karein.")
    st.stop()

# ---- Cleaning ----
for num_col in ["YTD Premium", "YTD Target", "P&L"]:
    if num_col in df.columns:
        df[num_col] = (
            df[num_col].astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("₹", "", regex=False)
            .str.strip()
        )
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

if "Date" in df.columns:
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)

for txt_col in ["Policy Status", "Fresh/Port"]:
    if txt_col in df.columns:
        df[txt_col] = df[txt_col].astype(str).str.strip()

# =========================================================
# ---------------------- FILTERS (sidebar) ------------------
# =========================================================
st.sidebar.header("🔍 Filters")

filtered_df = df.copy()

simple_filters = [
    "Month", "RM Name", "Fresh/Port", "Insurer",
    "Policy Tenure", "Leader", "Policy Status", "Policy Type",
]

for col in simple_filters:
    if col in df.columns:
        options = df[col].dropna().astype(str).unique().tolist()
        options = sorted(options, key=month_sort_key) if col == "Month" else sorted(options)
        selected = st.sidebar.multiselect(col, options, default=[])
        if selected:
            filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected)]

if "Date" in df.columns and df["Date"].notna().any():
    min_date, max_date = df["Date"].min(), df["Date"].max()
    date_range = st.sidebar.date_input(
        "Date", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        filtered_df = filtered_df[
            (filtered_df["Date"] >= pd.to_datetime(date_range[0]))
            & (filtered_df["Date"] <= pd.to_datetime(date_range[1]))
        ]

# =========================================================
# ------------------- HEADER --------------------------------
# =========================================================
render_header(
    "💊", "Health Sales Dashboard",
    f"{len(filtered_df):,} records · Filtered view",
)

# =========================================================
# ------------------- METRIC CALCULATIONS -------------------
# =========================================================
def safe_div(a, b):
    return (a / b * 100) if b else 0

ytd_target = filtered_df["YTD Target"].sum() if "YTD Target" in filtered_df else 0
ytd_achievement = filtered_df["YTD Premium"].sum() if "YTD Premium" in filtered_df else 0
ach_pct = safe_div(ytd_achievement, ytd_target)

total_nop = len(filtered_df)
ats = (ytd_achievement / total_nop) if total_nop else 0

issued_df = filtered_df[filtered_df["Policy Status"] == "Issued"] if "Policy Status" in filtered_df else filtered_df.iloc[0:0]
rejected_df = filtered_df[filtered_df["Policy Status"] == "Rejected"] if "Policy Status" in filtered_df else filtered_df.iloc[0:0]
fresh_df = filtered_df[filtered_df["Fresh/Port"] == "Fresh"] if "Fresh/Port" in filtered_df else filtered_df.iloc[0:0]
port_df = filtered_df[filtered_df["Fresh/Port"] == "Port"] if "Fresh/Port" in filtered_df else filtered_df.iloc[0:0]

issued_premium = issued_df["YTD Premium"].sum()
issued_nop = len(issued_df)
issued_pct = safe_div(issued_premium, ytd_achievement)

rejected_premium = rejected_df["YTD Premium"].sum()
rejected_nop = len(rejected_df)
rejected_pct = safe_div(rejected_premium, ytd_achievement)

fresh_premium = fresh_df["YTD Premium"].sum()
fresh_nop = len(fresh_df)
fresh_pct = safe_div(fresh_premium, ytd_achievement)

port_premium = port_df["YTD Premium"].sum()
port_nop = len(port_df)
port_pct = safe_div(port_premium, ytd_achievement)

# =========================================================
# ------------------- KPI CARDS ------------------------------
# =========================================================
section_header("📊", "Key Performance Indicators")

row1 = [
    kpi_card("🎯", "YTD TARGET", fmt_inr_auto(ytd_target), "", accent="#3b82f6"),
    kpi_card("📈", "YTD ACHIEVEMENT", fmt_inr_auto(ytd_achievement),
             f"{'▲' if ach_pct >= 100 else '▼'} {fmt_pct(ach_pct)} of target",
             sub_class="positive" if ach_pct >= 100 else "negative", accent="#22c55e"),
    kpi_card("✅", "ISSUED PREMIUM", fmt_inr_auto(issued_premium),
             f"{fmt_pct(issued_pct)} · {issued_nop:,} NOP", accent="#a855f7"),
    kpi_card("❌", "REJECTED PREMIUM", fmt_inr_auto(rejected_premium),
             f"{fmt_pct(rejected_pct)} · {rejected_nop:,} NOP", sub_class="negative", accent="#ef4444"),
]
render_kpi_row(row1)

row2 = [
    kpi_card("📋", "Number of Policies", f"{total_nop:,}", "", accent="#f59e0b"),
    kpi_card("💰", "Average Ticket Size", fmt_inr_auto(ats), "", accent="#06b6d4"),
    kpi_card("🆕", "FRESH PREMIUM", fmt_inr_auto(fresh_premium),
             f"{fmt_pct(fresh_pct)} · {fresh_nop:,} NOP", accent="#3b82f6"),
    kpi_card("🔄", "PORT PREMIUM", fmt_inr_auto(port_premium),
             f"{fmt_pct(port_pct)} · {port_nop:,} NOP", accent="#ec4899"),
]
render_kpi_row(row2)

if filtered_df.empty:
    st.info("Selected filters me data nahi mila.")
    st.stop()

# =========================================================
# ------------------- MONTHLY TREND CHARTS -------------------
# =========================================================
section_header("📈", "Monthly Trend")

trend_col1, trend_col2 = st.columns(2)

with trend_col1:
    if {"Month", "YTD Premium", "YTD Target"}.issubset(filtered_df.columns):
        monthly = filtered_df.groupby("Month").agg(
            Achievement=("YTD Premium", "sum"),
            Target=("YTD Target", "sum"),
        ).reset_index()
        monthly = sort_month_df(monthly)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=monthly["Month"], y=monthly["Target"], name="Target",
            mode="lines+markers+text", line=dict(color="#3b82f6", width=3),
            text=[fmt_inr_auto(v) for v in monthly["Target"]],
            textposition="top center", textfont=dict(size=11, color="#3b82f6"),
        ))
        fig.add_trace(go.Scatter(
            x=monthly["Month"], y=monthly["Achievement"], name="Achievement",
            mode="lines+markers+text", line=dict(color="#22c55e", width=3),
            text=[fmt_inr_auto(v) for v in monthly["Achievement"]],
            textposition="bottom center", textfont=dict(size=11, color="#22c55e"),
        ))
        fig.update_layout(
            **PLOTLY_DARK_LAYOUT,
            title="Monthly Target vs Achievement",
            yaxis=dict(title="Amount"),
            legend=dict(orientation="h", y=1.15),
        )
        st.plotly_chart(fig, use_container_width=True)

with trend_col2:
    if "Month" in filtered_df.columns:
        nop_trend = filtered_df.groupby("Month").size().reset_index(name="NOP")
        nop_trend = sort_month_df(nop_trend)
        fig_nop = go.Figure()
        fig_nop.add_trace(go.Scatter(
            x=nop_trend["Month"], y=nop_trend["NOP"], name="NOP",
            mode="lines+markers+text", line=dict(color="#a855f7", width=3),
            text=nop_trend["NOP"], textposition="top center",
            textfont=dict(size=11, color="#a855f7"),
        ))
        fig_nop.update_layout(**PLOTLY_DARK_LAYOUT, title="Monthly NOP Trend")
        st.plotly_chart(fig_nop, use_container_width=True)

# =========================================================
# ------------------- MONTH WISE SUMMARY TABLE ---------------
# =========================================================
section_header("📋", "Month wise Summary")

if "Month" in filtered_df.columns:
    def month_agg(g):
        ytd_p = g["YTD Premium"].sum()
        nop = len(g)
        issued = g.loc[g["Policy Status"] == "Issued", "YTD Premium"].sum() if "Policy Status" in g else 0
        fr = g.loc[g["Fresh/Port"] == "Fresh", "YTD Premium"].sum() if "Fresh/Port" in g else 0
        fr_nop = len(g[g["Fresh/Port"] == "Fresh"]) if "Fresh/Port" in g else 0
        pt = g.loc[g["Fresh/Port"] == "Port", "YTD Premium"].sum() if "Fresh/Port" in g else 0
        pt_nop = len(g[g["Fresh/Port"] == "Port"]) if "Fresh/Port" in g else 0
        return pd.Series({
            "YTD Target": g["YTD Target"].sum(),
            "YTD Premium": ytd_p,
            "Issued": issued,
            "Ach%": safe_div(issued, g["YTD Target"].sum()),
            "Issuance%": safe_div(issued, ytd_p),
            "NOP": nop,
            "ATS": (ytd_p / nop) if nop else 0,
            "Fresh Premium": fr,
            "Fresh NOP": fr_nop,
            "Fresh%": safe_div(fr, ytd_p),
            "Port Premium": pt,
            "Port NOP": pt_nop,
            "Port%": safe_div(pt, ytd_p),
        })

    month_table = filtered_df.groupby("Month").apply(month_agg).reset_index()
    if month_table.empty:
        st.info("Month wise summary ke liye data nahi mila.")
        st.stop()
    month_table = sort_month_df(month_table)
    month_total_premium = month_table["YTD Premium"].sum()
    month_total_nop = month_table["NOP"].sum()
    month_table_total = pd.DataFrame([{
        "Month": "TOTAL",
        "YTD Target": month_table["YTD Target"].sum(),
        "YTD Premium": month_total_premium,
        "Issued": month_table["Issued"].sum(),
        "Ach%": safe_div(month_table["Issued"].sum(), month_table["YTD Target"].sum()),
        "Issuance%": safe_div(month_table["Issued"].sum(), month_total_premium),
        "NOP": month_total_nop,
        "ATS": (month_total_premium / month_total_nop) if month_total_nop else 0,
        "Fresh Premium": month_table["Fresh Premium"].sum(),
        "Fresh NOP": month_table["Fresh NOP"].sum(),
        "Fresh%": safe_div(month_table["Fresh Premium"].sum(), month_total_premium),
        "Port Premium": month_table["Port Premium"].sum(),
        "Port NOP": month_table["Port NOP"].sum(),
        "Port%": safe_div(month_table["Port Premium"].sum(), month_total_premium),
    }])
    month_table_display = pd.concat([month_table, month_table_total], ignore_index=True)

    add_table_download(month_table_display, "month_wise_summary.csv", "download_month_wise_summary")
    st.dataframe(
        month_table_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "YTD Target": st.column_config.NumberColumn(format="₹%.0f"),
            "YTD Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Issued": st.column_config.NumberColumn(format="₹%.0f"),
            "Ach%": st.column_config.NumberColumn(format="%.1f%%"),
            "Issuance%": st.column_config.NumberColumn(format="%.1f%%"),
            "ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Fresh Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Fresh NOP": st.column_config.NumberColumn(format="%.0f"),
            "Fresh%": st.column_config.NumberColumn(format="%.1f%%"),
            "Port Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Port%": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

# =========================================================
# ------------------- RM PERFORMANCE TABLE --------------------
# =========================================================
section_header("👤", "RM Performance")

if "RM Name" in filtered_df.columns:
    def rm_agg(g):
        ytd_t = g["YTD Target"].sum()
        ytd_p = g["YTD Premium"].sum()
        iss = g.loc[g["Policy Status"] == "Issued", "YTD Premium"].sum() if "Policy Status" in g else 0
        nop = len(g)
        fr = g.loc[g["Fresh/Port"] == "Fresh", "YTD Premium"].sum() if "Fresh/Port" in g else 0
        fr_nop = len(g[g["Fresh/Port"] == "Fresh"]) if "Fresh/Port" in g else 0
        pt = g.loc[g["Fresh/Port"] == "Port", "YTD Premium"].sum() if "Fresh/Port" in g else 0
        pt_nop = len(g[g["Fresh/Port"] == "Port"]) if "Fresh/Port" in g else 0
        return pd.Series({
            "YTD Target": ytd_t,
            "YTD Premium": ytd_p,
            "Issued Premium": iss,
            "Ach%": safe_div(iss, ytd_t),
            "NOP": nop,
            "ATS": (ytd_p / nop) if nop else 0,
            "Issuance%": safe_div(iss, ytd_p),
            "Fresh Premium": fr,
            "Fresh NOP": fr_nop,
            "Fresh%": safe_div(fr, ytd_p),
            "Port Premium": pt,
            "Port NOP": pt_nop,
            "Port%": safe_div(pt, ytd_p),
        })

    rm_table = filtered_df.groupby("RM Name").apply(rm_agg).reset_index()
    rm_table = rm_table.sort_values("Ach%", ascending=False)

    rm_total = pd.DataFrame([{
        "RM Name": "TOTAL",
        "YTD Target": rm_table["YTD Target"].sum(),
        "YTD Premium": rm_table["YTD Premium"].sum(),
        "Issued Premium": rm_table["Issued Premium"].sum(),
        "Ach%": safe_div(rm_table["Issued Premium"].sum(), rm_table["YTD Target"].sum()),
        "NOP": rm_table["NOP"].sum(),
        "ATS": (rm_table["YTD Premium"].sum() / rm_table["NOP"].sum()) if rm_table["NOP"].sum() else 0,
        "Issuance%": safe_div(rm_table["Issued Premium"].sum(), rm_table["YTD Premium"].sum()),
        "Fresh Premium": rm_table["Fresh Premium"].sum(),
        "Fresh NOP": rm_table["Fresh NOP"].sum(),
        "Fresh%": safe_div(rm_table["Fresh Premium"].sum(), rm_table["YTD Premium"].sum()),
        "Port Premium": rm_table["Port Premium"].sum(),
        "Port NOP": rm_table["Port NOP"].sum(),
        "Port%": safe_div(rm_table["Port Premium"].sum(), rm_table["YTD Premium"].sum()),
    }])
    rm_table_display = pd.concat([rm_table, rm_total], ignore_index=True)

    add_table_download(rm_table_display, "rm_performance.csv", "download_rm_performance")
    st.dataframe(
        rm_table_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "YTD Target": st.column_config.NumberColumn(format="₹%.0f"),
            "YTD Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Issued Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Ach%": st.column_config.NumberColumn(format="%.1f%%"),
            "ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Issuance%": st.column_config.NumberColumn(format="%.1f%%"),
            "Fresh Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Fresh%": st.column_config.NumberColumn(format="%.1f%%"),
            "Port Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Port%": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

# =========================================================
# ------------------- FRESH VS PORT DONUT ----------------------
# =========================================================
section_header("🍩", "Fresh vs Port")

donut_col1, donut_col2 = st.columns([1, 2])
with donut_col1:
    metric_choice = st.radio("Show by", ["Premium", "NOP Count"], horizontal=True, key="fp_metric")

with donut_col2:
    pass

if "Fresh/Port" in filtered_df.columns:
    if metric_choice == "Premium":
        fp_data = filtered_df.groupby("Fresh/Port")["YTD Premium"].sum().reset_index()
        fig_fp = px.pie(fp_data, names="Fresh/Port", values="YTD Premium", hole=0.6,
                         title="Fresh vs Port - Premium",
                         color_discrete_sequence=["#3b82f6", "#ec4899"])
    else:
        fp_data = filtered_df.groupby("Fresh/Port").size().reset_index(name="NOP")
        fig_fp = px.pie(fp_data, names="Fresh/Port", values="NOP", hole=0.6,
                         title="Fresh vs Port - NOP Count",
                         color_discrete_sequence=["#3b82f6", "#ec4899"])
    fig_fp.update_layout(**PLOTLY_DARK_LAYOUT)
    st.plotly_chart(fig_fp, use_container_width=True)

# =========================================================
# ------------------- INSURER WISE FRESH/PORT TABLE ------------
# =========================================================
section_header("🛡️", "Insurer wise Fresh vs Port")

if "Insurer" in filtered_df.columns and "Fresh/Port" in filtered_df.columns:
    def insurer_agg(g):
        fr = g.loc[g["Fresh/Port"] == "Fresh", "YTD Premium"].sum()
        fr_nop = len(g[g["Fresh/Port"] == "Fresh"])
        pt = g.loc[g["Fresh/Port"] == "Port", "YTD Premium"].sum()
        pt_nop = len(g[g["Fresh/Port"] == "Port"])
        total = fr + pt
        return pd.Series({
            "Fresh Premium": fr,
            "Fresh NOP": fr_nop,
            "Fresh ATS": (fr / fr_nop) if fr_nop else 0,
            "Fresh%": safe_div(fr, total),
            "Port Premium": pt,
            "Port NOP": pt_nop,
            "Port ATS": (pt / pt_nop) if pt_nop else 0,
            "Port%": safe_div(pt, total),
        })

    insurer_table = filtered_df.groupby("Insurer").apply(insurer_agg).reset_index()
    insurer_table = insurer_table.sort_values("Fresh Premium", ascending=False)

    insurer_total = pd.DataFrame([{
        "Insurer": "TOTAL",
        "Fresh Premium": insurer_table["Fresh Premium"].sum(),
        "Fresh NOP": insurer_table["Fresh NOP"].sum(),
        "Fresh ATS": (insurer_table["Fresh Premium"].sum() / insurer_table["Fresh NOP"].sum())
                     if insurer_table["Fresh NOP"].sum() else 0,
        "Fresh%": safe_div(insurer_table["Fresh Premium"].sum(),
                            insurer_table["Fresh Premium"].sum() + insurer_table["Port Premium"].sum()),
        "Port Premium": insurer_table["Port Premium"].sum(),
        "Port NOP": insurer_table["Port NOP"].sum(),
        "Port ATS": (insurer_table["Port Premium"].sum() / insurer_table["Port NOP"].sum())
                    if insurer_table["Port NOP"].sum() else 0,
        "Port%": safe_div(insurer_table["Port Premium"].sum(),
                           insurer_table["Fresh Premium"].sum() + insurer_table["Port Premium"].sum()),
    }])
    insurer_table_display = pd.concat([insurer_table, insurer_total], ignore_index=True)

    add_table_download(insurer_table_display, "insurer_wise_fresh_vs_port.csv", "download_insurer_wise_fresh_vs_port")
    st.dataframe(
        insurer_table_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Fresh Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Fresh ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Fresh%": st.column_config.NumberColumn(format="%.1f%%"),
            "Port Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "Port ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Port%": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

# =========================================================
# ------------------- LEADER WISE CHARTS -----------------------
# =========================================================
section_header("🏆", "Leader wise Performance")

leader_col1, leader_col2 = st.columns(2)

if "Leader" in filtered_df.columns:
    with leader_col1:
        leader_contrib = filtered_df.groupby("Leader")["YTD Premium"].sum().reset_index()
        leader_contrib["Contribution%"] = leader_contrib["YTD Premium"] / leader_contrib["YTD Premium"].sum() * 100
        fig_lc = px.pie(leader_contrib, names="Leader", values="Contribution%", hole=0.5,
                         title="Leader wise Premium Contribution %")
        fig_lc.update_layout(**PLOTLY_DARK_LAYOUT)
        st.plotly_chart(fig_lc, use_container_width=True)

    with leader_col2:
        leader_perf = filtered_df.groupby("Leader").agg(
            YTD_Premium=("YTD Premium", "sum"),
        ).reset_index()
        issued_by_leader = (
            filtered_df[filtered_df["Policy Status"] == "Issued"]
            .groupby("Leader")["YTD Premium"]
            .sum()
            .rename("Issued_Premium")
            .reset_index()
        ) if "Policy Status" in filtered_df.columns else pd.DataFrame(columns=["Leader", "Issued_Premium"])
        leader_perf = leader_perf.merge(issued_by_leader, on="Leader", how="left")
        leader_perf["Issued_Premium"] = leader_perf["Issued_Premium"].fillna(0)
        leader_perf["Issued%"] = leader_perf.apply(
            lambda r: safe_div(r["Issued_Premium"], r["YTD_Premium"]), axis=1
        )
        leader_perf = leader_perf.sort_values("YTD_Premium", ascending=False)

        fig_lp = go.Figure()
        fig_lp.add_trace(go.Bar(
            x=leader_perf["Leader"],
            y=leader_perf["YTD_Premium"],
            name="YTD Premium",
            marker_color="#3b82f6",
            text=[fmt_inr_auto(v) for v in leader_perf["YTD_Premium"]],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>YTD Premium: %{customdata}<extra></extra>",
            customdata=[fmt_inr_auto(v) for v in leader_perf["YTD_Premium"]],
        ))
        fig_lp.add_trace(go.Bar(
            x=leader_perf["Leader"],
            y=leader_perf["Issued_Premium"],
            name="Issued Premium",
            marker_color="#22c55e",
            text=[fmt_inr_auto(v) for v in leader_perf["Issued_Premium"]],
            textposition="outside",
            customdata=[
                [fmt_inr_auto(row["Issued_Premium"]), fmt_pct(row["Issued%"])]
                for _, row in leader_perf.iterrows()
            ],
            hovertemplate="<b>%{x}</b><br>Issued Premium: %{customdata[0]}<br>Issued%: %{customdata[1]}<extra></extra>",
        ))
        fig_lp.update_layout(
            **PLOTLY_DARK_LAYOUT,
            title="Leader wise YTD Premium vs Issued Premium",
            barmode="group",
            yaxis=dict(title="Premium"),
            legend=dict(orientation="h", y=1.15),
        )
        st.plotly_chart(fig_lp, use_container_width=True)

# =========================================================
# ------------------- POLICY TENURE WISE TABLE -----------------
# =========================================================
section_header("📆", "Policy Tenure wise Breakup")

if "Policy Tenure" in filtered_df.columns:
    tenure_table = filtered_df.groupby("Policy Tenure").agg(
        Premium=("YTD Premium", "sum"),
    ).reset_index()
    tenure_table["NOP"] = filtered_df.groupby("Policy Tenure").size().values
    tenure_table["ATS"] = tenure_table["Premium"] / tenure_table["NOP"]
    tenure_table["Premium Contribution%"] = tenure_table["Premium"] / tenure_table["Premium"].sum() * 100
    tenure_table["NOP Contribution%"] = tenure_table["NOP"] / tenure_table["NOP"].sum() * 100
    tenure_table = tenure_table.sort_values("Premium", ascending=False)

    tenure_total = pd.DataFrame([{
        "Policy Tenure": "TOTAL",
        "Premium": tenure_table["Premium"].sum(),
        "NOP": tenure_table["NOP"].sum(),
        "ATS": (tenure_table["Premium"].sum() / tenure_table["NOP"].sum()) if tenure_table["NOP"].sum() else 0,
        "Premium Contribution%": 100.0,
        "NOP Contribution%": 100.0,
    }])
    tenure_table_display = pd.concat([tenure_table, tenure_total], ignore_index=True)

    add_table_download(tenure_table_display, "policy_tenure_wise_breakup.csv", "download_policy_tenure_wise_breakup")
    st.dataframe(
        tenure_table_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Premium": st.column_config.NumberColumn(format="₹%.0f"),
            "ATS": st.column_config.NumberColumn(format="₹%.0f"),
            "Premium Contribution%": st.column_config.NumberColumn(format="%.1f%%"),
            "NOP Contribution%": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

# =========================================================
# ------------------- RAW DATA -----------------------------
# =========================================================
with st.expander("📄 Raw Data Dekhein"):
    add_table_download(filtered_df, "health_sales_raw_data.csv", "download_health_sales_raw_data")
    st.dataframe(filtered_df, use_container_width=True)
