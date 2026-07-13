"""
pages/3_Calling_Dashboard.py
--------------------------------
Calling Dashboard - Postgres (Supabase) se connect hai.

IMPORTANT: 1.5M+ rows hai isliye yahan kabhi "saara data Python me load"
nahi karte. Har KPI/Chart/Table seedha SQL me SUM/COUNT/GROUP BY karke,
chhota already-aggregated result hi lata hai. Yeh dashboard ko fast rakhta hai.

ASSUMPTION (agar galat ho to bata dena, 1 line change karke fix kar denge):
- "Connected Call" -> "System Disposition" column me value "connected" expect kiya
  hai (case-insensitive match). Neeche CONNECTED_STATUS_VALUE variable me
  hi yeh set hai - agar aapke data me alag spelling/value hai (jaise
  "Connected", "Answered", etc.) to sirf yeh ek line change kar dena.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.pg_connector import run_query as run_pg_query, clear_query_cache
from utils.styling import (
    inject_custom_css, render_header, section_header,
    kpi_card, render_kpi_row, fmt_pct, fmt_duration,
)

st.set_page_config(page_title="Calling Dashboard", page_icon="📞", layout="wide")
inject_custom_css()

def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    return run_pg_query(sql, params, section="postgres")

PLOTLY_DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0e1626",
    plot_bgcolor="#0e1626",
    font=dict(color="#e2e8f0"),
    margin=dict(l=10, r=10, t=50, b=10),
)

TABLE_NAME = "calling_dashboard"
# Use exact normalized System Disposition match for connected calls.
CONNECTED_STATUS_VALUE = "connected"

def safe_div(a, b):
    return (a / b * 100) if b else 0


def add_table_download(dataframe: pd.DataFrame, file_name: str, key: str):
    st.download_button(
        "Download CSV",
        data=dataframe.to_csv(index=False).encode("utf-8-sig"),
        file_name=file_name,
        mime="text/csv",
        key=key,
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_month_options() -> pd.DataFrame:
    return run_query(f"""
        SELECT DISTINCT
            DATE_TRUNC('month', "Call Date")::date AS month_key,
            TO_CHAR(DATE_TRUNC('month', "Call Date"), 'Mon YYYY') AS month_label
        FROM {TABLE_NAME}
        WHERE "Call Date" IS NOT NULL
        ORDER BY month_key
    """)


@st.cache_data(ttl=300, show_spinner=False)
def load_distinct_values(column: str) -> list:
    sql = f'SELECT DISTINCT "{column}" AS value FROM {TABLE_NAME} WHERE "{column}" IS NOT NULL ORDER BY 1'
    df = run_query(sql)
    return df["value"].dropna().tolist()


@st.cache_data(ttl=300, show_spinner=False)
def load_date_bounds() -> pd.DataFrame:
    return run_query(f'SELECT MIN("Call Date") AS min_d, MAX("Call Date") AS max_d FROM {TABLE_NAME}')

# =========================================================
# ------------------- TOP BAR --------------------------------
# =========================================================
top_col1, top_col2 = st.columns([6, 1])
with top_col2:
    if st.button("🔄 Refresh Data"):
        clear_query_cache()
        load_month_options.clear()
        load_distinct_values.clear()
        load_date_bounds.clear()
        st.rerun()

# =========================================================
# ------------------- FILTER OPTIONS (distinct values) --------
# =========================================================
try:
    months_df = load_month_options()
    employee_options = load_distinct_values("Employee Name")
    tl_options = load_distinct_values("Reporting TL")
    sysdisp_options = load_distinct_values("System Disposition")
    labeldisp_options = load_distinct_values("Label Disposition")
    date_bounds = load_date_bounds()
except Exception as e:
    st.error(f"Postgres se data load nahi ho paya: {e}")
    st.stop()

month_options = months_df["month_key"].tolist()
month_labels = {row["month_key"]: row["month_label"] for _, row in months_df.iterrows()}

# =========================================================
# ---------------------- FILTERS (sidebar) ------------------
# =========================================================
st.sidebar.header("🔍 Filters")

selected_months = st.sidebar.multiselect(
    "Month",
    month_options,
    default=[],
    format_func=lambda x: month_labels.get(x, x),
)

min_date = date_bounds["min_d"].iloc[0]
max_date = date_bounds["max_d"].iloc[0]
date_range = None
if pd.notna(min_date) and pd.notna(max_date):
    date_range = st.sidebar.date_input("Date", value=(min_date, max_date), min_value=min_date, max_value=max_date)

selected_employees = st.sidebar.multiselect("Employee Name", employee_options, default=[])
selected_tls = st.sidebar.multiselect("Reporting TL", tl_options, default=[])
selected_sysdisp = st.sidebar.multiselect("System Disposition", sysdisp_options, default=[])
selected_labeldisp = st.sidebar.multiselect("Label Disposition", labeldisp_options, default=[])

# =========================================================
# ------------------- BUILD WHERE CLAUSE -----------------------
# =========================================================
def build_filters():
    conditions = []
    params = {}

    def add_multiselect_filter(column, param_name, selected_values, all_values):
        if not selected_values:
            return
        if set(selected_values) == set(all_values):
            return
        conditions.append(f'"{column}" = ANY(%({param_name})s)')
        params[param_name] = selected_values

    if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
        conditions.append('"Call Date" BETWEEN %(date_from)s AND %(date_to)s')
        params["date_from"] = date_range[0]
        params["date_to"] = date_range[1]

    if selected_months:
        month_conditions = []
        for i, month_start in enumerate(selected_months):
            month_end = (pd.Timestamp(month_start) + pd.DateOffset(months=1)).date()
            start_key = f"month_start_{i}"
            end_key = f"month_end_{i}"
            month_conditions.append(f'("Call Date" >= %({start_key})s AND "Call Date" < %({end_key})s)')
            params[start_key] = month_start
            params[end_key] = month_end
        conditions.append(f"({' OR '.join(month_conditions)})")

    add_multiselect_filter("Employee Name", "employees", selected_employees, employee_options)
    add_multiselect_filter("Reporting TL", "tls", selected_tls, tl_options)
    add_multiselect_filter("System Disposition", "sysdisp", selected_sysdisp, sysdisp_options)
    add_multiselect_filter("Label Disposition", "labeldisp", selected_labeldisp, labeldisp_options)

    where_sql = " AND ".join(conditions) if conditions else "1=1"
    return where_sql, params


WHERE_SQL, PARAMS = build_filters()

# =========================================================
# ------------------- HEADER --------------------------------
# =========================================================
render_header("📞", "Calling Dashboard", "")

# =========================================================
# ------------------- KPI QUERY -------------------------------
# =========================================================
kpi_sql = f"""
    SELECT
        COUNT(*) AS total_calls,
        COUNT(*) FILTER (WHERE "Unique Dials" = 1) AS unique_dials,
        COALESCE(SUM("Talktime"), INTERVAL '0') AS total_talktime,
        COUNT(*) FILTER (WHERE LOWER(TRIM("System Disposition")) = LOWER(%(connected_status)s)) AS connected_calls
    FROM {TABLE_NAME}
    WHERE {WHERE_SQL}
"""
kpi_params = {"connected_status": CONNECTED_STATUS_VALUE, **PARAMS}
kpi_row = run_query(kpi_sql, kpi_params).iloc[0]

total_calls = int(kpi_row["total_calls"])
unique_dials = int(kpi_row["unique_dials"])
total_talktime = kpi_row["total_talktime"]
connected_calls = int(kpi_row["connected_calls"])

connectivity_pct = safe_div(connected_calls, total_calls)
avg_talktime = (total_talktime / connected_calls) if connected_calls else pd.Timedelta(0)

# =========================================================
# ------------------- KPI CARDS ------------------------------
# =========================================================
section_header("📊", "Key Performance Indicators")

row1 = [
    kpi_card("📞", "TOTAL CALLS", f"{total_calls:,}", "", accent="#3b82f6"),
    kpi_card("🎯", "UNIQUE DIALS", f"{unique_dials:,}", "", accent="#a855f7"),
    kpi_card("⏱️", "TOTAL TALK TIME", fmt_duration(total_talktime), "", accent="#22c55e"),
    kpi_card("📈", "AVG TALKTIME / CONNECTED CALL", fmt_duration(avg_talktime), "", accent="#f59e0b"),
]
render_kpi_row(row1)

row2 = [
    kpi_card("✅", "CONNECTED CALLS", f"{connected_calls:,}", "", accent="#10b981"),
    kpi_card("📊", "CONNECTIVITY %", fmt_pct(connectivity_pct), "", accent="#06b6d4"),
]
cols = st.columns([1, 1, 1, 1])
with cols[0]:
    st.markdown(row2[0], unsafe_allow_html=True)
with cols[1]:
    st.markdown(row2[1], unsafe_allow_html=True)

# =========================================================
# ------------------- MOM TREND CHART --------------------------
# =========================================================
section_header("📈", "MOM Total Calls vs Unique Calls")

mom_sql = f"""
    SELECT
        TO_CHAR(DATE_TRUNC('month', "Call Date"), 'Mon YYYY') AS month,
        DATE_TRUNC('month', "Call Date") AS month_dt,
        COUNT(*) AS total_calls,
        COUNT(*) FILTER (WHERE "Unique Dials" = 1) AS unique_calls
    FROM {TABLE_NAME}
    WHERE {WHERE_SQL}
    GROUP BY month, month_dt
    ORDER BY month_dt
"""
mom_df = run_query(mom_sql, PARAMS)

if not mom_df.empty:
    fig_mom = go.Figure()
    fig_mom.add_trace(go.Scatter(
        x=mom_df["month"], y=mom_df["total_calls"], name="Total Calls",
        mode="lines+markers+text", line=dict(color="#3b82f6", width=3),
        text=mom_df["total_calls"], textposition="top center",
        textfont=dict(size=11, color="#3b82f6"),
    ))
    fig_mom.add_trace(go.Scatter(
        x=mom_df["month"], y=mom_df["unique_calls"], name="Unique Calls",
        mode="lines+markers+text", line=dict(color="#a855f7", width=3),
        text=mom_df["unique_calls"], textposition="bottom center",
        textfont=dict(size=11, color="#a855f7"),
    ))
    fig_mom.update_layout(**PLOTLY_DARK_LAYOUT, title="MOM Total Calls vs Unique Calls",
                           legend=dict(orientation="h", y=1.15))
    st.plotly_chart(fig_mom, use_container_width=True)

# =========================================================
# ------------------- DISPOSITION CHARTS -----------------------
# =========================================================
section_header("📊", "Disposition Analysis")

disp_col1, disp_col2 = st.columns(2)

with disp_col1:
    sysdisp_sql = f"""
        SELECT "System Disposition" AS disposition, COUNT(*) AS calls
        FROM {TABLE_NAME}
        WHERE {WHERE_SQL}
        GROUP BY "System Disposition"
        ORDER BY calls DESC
    """
    sysdisp_df = run_query(sysdisp_sql, PARAMS)
    if not sysdisp_df.empty:
        sysdisp_df["percent"] = sysdisp_df["calls"] / sysdisp_df["calls"].sum()
        fig_sys = px.pie(sysdisp_df, names="disposition", values="calls", title="System Disposition")
        fig_sys.update_traces(textinfo="label+percent+value", hovertemplate="%{label}: %{value} (%{percent})")
        fig_sys.update_layout(**PLOTLY_DARK_LAYOUT)
        st.plotly_chart(fig_sys, use_container_width=True)

with disp_col2:
    labeldisp_sql = f"""
        SELECT "Label Disposition" AS disposition, COUNT(*) AS calls
        FROM {TABLE_NAME}
        WHERE {WHERE_SQL}
        GROUP BY "Label Disposition"
        ORDER BY calls DESC
    """
    labeldisp_df = run_query(labeldisp_sql, PARAMS)
    if not labeldisp_df.empty:
        fig_label = px.bar(labeldisp_df, x="disposition", y="calls", title="Label Disposition",
                            category_orders={"disposition": labeldisp_df["disposition"].tolist()})
        fig_label.update_traces(marker_color="#ec4899", text=labeldisp_df["calls"], textposition="outside")
        fig_label.update_layout(**PLOTLY_DARK_LAYOUT)
        st.plotly_chart(fig_label, use_container_width=True)

# =========================================================
# ------------------- AGENT WISE PERFORMANCE -----------------------
# =========================================================
section_header("👤", "Agent wise Performance")

agent_sql = f"""
    SELECT
        "Employee Name" AS employee_name,
        COUNT(*) AS total_calls,
        COUNT(*) FILTER (WHERE "Unique Dials" = 1) AS unique_dials,
        COUNT(*) FILTER (WHERE LOWER(TRIM("System Disposition")) = LOWER(%(connected_status)s)) AS connected_calls,
        COALESCE(SUM("Talktime"), INTERVAL '0') AS total_talktime
    FROM {TABLE_NAME}
    WHERE {WHERE_SQL}
    GROUP BY "Employee Name"
    ORDER BY total_calls DESC
"""
agent_params = {"connected_status": CONNECTED_STATUS_VALUE, **PARAMS}
agent_df = run_query(agent_sql, agent_params)

if not agent_df.empty:
    agent_df["Connectivity%"] = agent_df.apply(
        lambda r: safe_div(r["connected_calls"], r["total_calls"]), axis=1)
    agent_df["Avg Talktime"] = agent_df.apply(
        lambda r: (r["total_talktime"] / r["connected_calls"]) if r["connected_calls"] else pd.Timedelta(0), axis=1)
    agent_df["Total Talktime (display)"] = agent_df["total_talktime"].apply(fmt_duration)
    agent_df["Avg Talktime (display)"] = agent_df["Avg Talktime"].apply(fmt_duration)

    agent_display = agent_df.rename(columns={
        "employee_name": "Employee Name",
        "total_calls": "Total Calls",
        "unique_dials": "Unique Dials",
        "connected_calls": "Connected Calls",
    })[[
        "Employee Name", "Total Calls", "Unique Dials", "Connected Calls",
        "Connectivity%", "Total Talktime (display)", "Avg Talktime (display)",
    ]].rename(columns={
        "Total Talktime (display)": "Total Talktime",
        "Avg Talktime (display)": "Avg Talktime",
    })

    agent_totals = {
        "Employee Name": "TOTAL",
        "Total Calls": int(agent_df["total_calls"].sum()),
        "Unique Dials": int(agent_df["unique_dials"].sum()),
        "Connected Calls": int(agent_df["connected_calls"].sum()),
        "Connectivity%": safe_div(agent_df["connected_calls"].sum(), agent_df["total_calls"].sum()),
        "Total Talktime": fmt_duration(agent_df["total_talktime"].sum()),
        "Avg Talktime": fmt_duration(
            agent_df["total_talktime"].sum() / agent_df["connected_calls"].sum()
            if agent_df["connected_calls"].sum() else pd.Timedelta(0)
        ),
    }
    agent_display = pd.concat([agent_display, pd.DataFrame([agent_totals])], ignore_index=True)

    add_table_download(agent_display, "agent_wise_performance.csv", "download_agent_wise_performance")
    st.dataframe(
        agent_display, use_container_width=True, hide_index=True,
        column_config={"Connectivity%": st.column_config.NumberColumn(format="%.1f%%")},
    )

# =========================================================
# ------------------- TL WISE PERFORMANCE -----------------------
# =========================================================
section_header("🏆", "TL wise Performance")

tl_sql = f"""
    SELECT
        "Reporting TL" AS reporting_tl,
        COUNT(*) AS total_calls,
        COUNT(*) FILTER (WHERE "Unique Dials" = 1) AS unique_dials,
        COUNT(*) FILTER (WHERE LOWER(TRIM("System Disposition")) = LOWER(%(connected_status)s)) AS connected_calls,
        COALESCE(SUM("Talktime"), INTERVAL '0') AS total_talktime,
        COUNT(DISTINCT "Employee Name") AS agents
    FROM {TABLE_NAME}
    WHERE {WHERE_SQL}
    GROUP BY "Reporting TL"
    ORDER BY total_calls DESC
"""
tl_params = {"connected_status": CONNECTED_STATUS_VALUE, **PARAMS}
tl_df = run_query(tl_sql, tl_params)

if not tl_df.empty:
    tl_df["Connectivity%"] = tl_df.apply(
        lambda r: safe_div(r["connected_calls"], r["total_calls"]), axis=1)
    tl_df["Avg Talktime"] = tl_df.apply(
        lambda r: (r["total_talktime"] / r["connected_calls"]) if r["connected_calls"] else pd.Timedelta(0), axis=1)
    tl_df["Total Talktime (display)"] = tl_df["total_talktime"].apply(fmt_duration)
    tl_df["Avg Talktime (display)"] = tl_df["Avg Talktime"].apply(fmt_duration)

    tl_display = tl_df.rename(columns={
        "reporting_tl": "Reporting TL",
        "total_calls": "Total Calls",
        "unique_dials": "Unique Dials",
        "connected_calls": "Connected Calls",
        "agents": "Agents",
    })[[
        "Reporting TL", "Total Calls", "Unique Dials", "Connected Calls",
        "Connectivity%", "Total Talktime (display)", "Avg Talktime (display)", "Agents",
    ]].rename(columns={
        "Total Talktime (display)": "Total Talktime",
        "Avg Talktime (display)": "Avg Talktime",
    })

    tl_totals = {
        "Reporting TL": "TOTAL",
        "Total Calls": int(tl_df["total_calls"].sum()),
        "Unique Dials": int(tl_df["unique_dials"].sum()),
        "Connected Calls": int(tl_df["connected_calls"].sum()),
        "Connectivity%": safe_div(tl_df["connected_calls"].sum(), tl_df["total_calls"].sum()),
        "Total Talktime": fmt_duration(tl_df["total_talktime"].sum()),
        "Avg Talktime": fmt_duration(
            tl_df["total_talktime"].sum() / tl_df["connected_calls"].sum()
            if tl_df["connected_calls"].sum() else pd.Timedelta(0)
        ),
        "Agents": int(tl_df["agents"].sum()),
    }
    tl_display = pd.concat([tl_display, pd.DataFrame([tl_totals])], ignore_index=True)

    add_table_download(tl_display, "tl_wise_performance.csv", "download_tl_wise_performance")
    st.dataframe(
        tl_display, use_container_width=True, hide_index=True,
        column_config={"Connectivity%": st.column_config.NumberColumn(format="%.1f%%")},
    )
