"""
pages/4_Leads_Utilisation.py
--------------------------------
Leads Utilisation dashboard connected to Supabase via utils.pg_connector.
Yeh page SQL aggregation + cache based structure use karta hai.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.pg_connector import run_query, clear_query_cache
from utils.styling import (
    inject_custom_css,
    render_header,
    section_header,
    kpi_card,
    render_kpi_row,
    fmt_inr_auto,
    fmt_pct,
    add_total_row,
)

st.set_page_config(page_title="Leads Utilisation", page_icon="📈", layout="wide")
inject_custom_css()

TABLE_NAME = "leads_utilisation"
DATE_COLUMN = "Visit Date"
STATUS_COLUMN = "LEAD STATUS"
SOURCE_COLUMN = "LEAD SOURCE"
RM_COLUMN = "Allocated To Name"
TEAM_LEADER_COLUMN = "Team Leader"
DATA_SOURCE_COLUMN = "Data Source"
ASSOCIATION_COLUMN = "Association"
MAIN_DISPOSITION_COLUMN = "Main Disposition"
SUB_DISPOSITION_COLUMN = "Sub Disposition"
PREMIUM_COLUMN = "PREMIUM"
BOOKING_DATE_COLUMN = "BOOKING DATE"

PLOTLY_DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0e1626",
    plot_bgcolor="#0e1626",
    font=dict(color="#e2e8f0"),
    margin=dict(l=10, r=10, t=50, b=10),
)


def safe_div(a, b):
    return (a / b * 100) if b else 0


def safe_ratio(a, b):
    return (a / b) if b else 0


def add_table_download(dataframe: pd.DataFrame, file_name: str, key: str):
    st.download_button(
        "Download CSV",
        data=dataframe.to_csv(index=False).encode("utf-8-sig"),
        file_name=file_name,
        mime="text/csv",
        key=key,
    )


def filter_condition(column, param_name):
    return f'"{column}" = ANY(%({param_name})s)'


def add_optional_multiselect_filter(conditions, params, column, param_name, selected_values, all_values):
    """
    Default Streamlit multiselects select every visible non-null value. If we
    still add an SQL filter in that state, database NULL rows get excluded.
    Treat "all selected" and "none selected" as no filter so default totals
    match the raw table count.
    """
    if not selected_values:
        return

    if set(selected_values) == set(all_values):
        return

    conditions.append(filter_condition(column, param_name))
    params[param_name] = selected_values


@st.cache_data(ttl=300, show_spinner=False)
def get_date_bounds() -> pd.DataFrame:
    sql = f'SELECT MIN("{DATE_COLUMN}") AS min_d, MAX("{DATE_COLUMN}") AS max_d FROM {TABLE_NAME}'
    return run_query(sql, None, section="postgres_leads")


@st.cache_data(ttl=300, show_spinner=False)
def load_distinct_values(column: str) -> list:
    sql = f'SELECT DISTINCT "{column}" AS value FROM {TABLE_NAME} WHERE "{column}" IS NOT NULL ORDER BY 1'
    df = run_query(sql, None, section="postgres_leads")
    return df["value"].dropna().tolist()


@st.cache_data(ttl=300, show_spinner=False)
def load_month_options() -> pd.DataFrame:
    sql = f"""
        SELECT DISTINCT
            to_char("{DATE_COLUMN}", 'YYYY-MM') AS month_key,
            to_char("{DATE_COLUMN}", 'Mon YYYY') AS month_label
        FROM {TABLE_NAME}
        WHERE "{DATE_COLUMN}" IS NOT NULL
        ORDER BY month_key
    """
    return run_query(sql, None, section="postgres_leads")


def build_filters(
    visit_date_range,
    selected_months,
    selected_rms,
    selected_team_leaders,
    selected_lead_sources,
    selected_data_sources,
    selected_associations,
    selected_main_dispositions,
    selected_sub_dispositions,
    all_filter_values,
):
    conditions = ["1=1"]
    params = {}

    if visit_date_range and isinstance(visit_date_range, tuple) and len(visit_date_range) == 2:
        conditions.append(f'"{DATE_COLUMN}" BETWEEN %(date_from)s AND %(date_to)s')
        params["date_from"] = visit_date_range[0]
        params["date_to"] = visit_date_range[1]

    if selected_months:
        conditions.append(f"to_char(\"{DATE_COLUMN}\", 'YYYY-MM') = ANY(%(months)s)")
        params["months"] = selected_months

    add_optional_multiselect_filter(conditions, params, RM_COLUMN, "rms", selected_rms, all_filter_values["rms"])
    add_optional_multiselect_filter(conditions, params, TEAM_LEADER_COLUMN, "team_leaders", selected_team_leaders, all_filter_values["team_leaders"])
    add_optional_multiselect_filter(conditions, params, SOURCE_COLUMN, "lead_sources", selected_lead_sources, all_filter_values["lead_sources"])
    add_optional_multiselect_filter(conditions, params, DATA_SOURCE_COLUMN, "data_sources", selected_data_sources, all_filter_values["data_sources"])
    add_optional_multiselect_filter(conditions, params, ASSOCIATION_COLUMN, "associations", selected_associations, all_filter_values["associations"])
    add_optional_multiselect_filter(conditions, params, MAIN_DISPOSITION_COLUMN, "main_dispositions", selected_main_dispositions, all_filter_values["main_dispositions"])
    add_optional_multiselect_filter(conditions, params, SUB_DISPOSITION_COLUMN, "sub_dispositions", selected_sub_dispositions, all_filter_values["sub_dispositions"])

    return " AND ".join(conditions), params


@st.cache_data(ttl=300, show_spinner=False)
def load_summary(where_sql: str, params: dict) -> pd.DataFrame:
    sql = f"""
        SELECT
            COUNT(*) AS total_leads,
            COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') AS converted_leads,
            SUM("{PREMIUM_COLUMN}") AS total_premium
        FROM {TABLE_NAME}
        WHERE {where_sql}
    """
    return run_query(sql, params, section="postgres_leads")


@st.cache_data(ttl=300, show_spinner=False)
def load_lead_source_analysis(where_sql: str, params: dict) -> pd.DataFrame:
    sql = f"""
        SELECT
            "{SOURCE_COLUMN}" AS lead_source,
            COUNT(*) AS total_leads,
            COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') AS converted_leads
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY "{SOURCE_COLUMN}"
        ORDER BY total_leads DESC
    """
    return run_query(sql, params, section="postgres_leads")


@st.cache_data(ttl=300, show_spinner=False)
def load_lead_source_conversion(where_sql: str, params: dict) -> pd.DataFrame:
    sql = f"""
        SELECT
            "{SOURCE_COLUMN}" AS lead_source,
            COUNT(*) AS total_leads,
            COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') AS converted_leads,
            CASE WHEN COUNT(*) = 0 THEN 0 ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') / COUNT(*), 1) END AS conversion_pct
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY "{SOURCE_COLUMN}"
        ORDER BY conversion_pct DESC
    """
    return run_query(sql, params, section="postgres_leads")


@st.cache_data(ttl=300, show_spinner=False)
def load_mom_trend(where_sql: str, params: dict) -> pd.DataFrame:
    sql = f"""
        SELECT
            date_trunc('month', "{DATE_COLUMN}")::date AS month_date,
            COUNT(*) AS total_leads,
            COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') AS converted_leads
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY month_date
        ORDER BY month_date
    """
    return run_query(sql, params, section="postgres_leads")


@st.cache_data(ttl=300, show_spinner=False)
def load_top_rm_conversion(where_sql: str, params: dict) -> pd.DataFrame:
    sql = f"""
        SELECT
            "{RM_COLUMN}" AS rm_name,
            COUNT(*) AS total_leads,
            COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') AS converted_leads,
            CASE WHEN COUNT(*) = 0 THEN 0 ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') / COUNT(*), 1) END AS conversion_pct
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY "{RM_COLUMN}"
        ORDER BY conversion_pct DESC
        LIMIT 10
    """
    return run_query(sql, params, section="postgres_leads")


@st.cache_data(ttl=300, show_spinner=False)
def load_main_disposition(where_sql: str, params: dict) -> pd.DataFrame:
    sql = f"""
        SELECT
            "{MAIN_DISPOSITION_COLUMN}" AS main_disposition,
            COUNT(*) AS leads
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY "{MAIN_DISPOSITION_COLUMN}"
        ORDER BY leads DESC
    """
    return run_query(sql, params, section="postgres_leads")


@st.cache_data(ttl=300, show_spinner=False)
def load_sub_disposition(where_sql: str, params: dict) -> pd.DataFrame:
    sql = f"""
        SELECT
            "{SUB_DISPOSITION_COLUMN}" AS sub_disposition,
            COUNT(*) AS leads
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY "{SUB_DISPOSITION_COLUMN}"
        ORDER BY leads DESC
    """
    return run_query(sql, params, section="postgres_leads")


@st.cache_data(ttl=300, show_spinner=False)
def load_rm_detail(where_sql: str, params: dict) -> pd.DataFrame:
    sql = f"""
        SELECT
            "{RM_COLUMN}" AS rm_name,
            "{SOURCE_COLUMN}" AS lead_source,
            COUNT(*) AS total_leads,
            COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') AS converted_leads,
            SUM("{PREMIUM_COLUMN}") AS premium,
            CASE WHEN COUNT(*) = 0 THEN 0 ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') / COUNT(*), 1) END AS conversion_pct
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY "{RM_COLUMN}", "{SOURCE_COLUMN}"
        ORDER BY "{RM_COLUMN}", total_leads DESC
    """
    return run_query(sql, params, section="postgres_leads")


@st.cache_data(ttl=300, show_spinner=False)
def load_source_summary(where_sql: str, params: dict) -> pd.DataFrame:
    sql = f"""
        SELECT
            "{SOURCE_COLUMN}" AS lead_source,
            COUNT(*) AS total_leads,
            COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') AS converted_leads,
            SUM("{PREMIUM_COLUMN}") AS premium,
            CASE WHEN COUNT(*) = 0 THEN 0 ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE LOWER(TRIM("{STATUS_COLUMN}")) = 'converted') / COUNT(*), 1) END AS conversion_pct
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY "{SOURCE_COLUMN}"
        ORDER BY total_leads DESC
    """
    return run_query(sql, params, section="postgres_leads")


# -------------------- PAGE LAYOUT --------------------
filter_col, refresh_col = st.columns([6, 1])
with refresh_col:
    if st.button("Refresh Data"):
        clear_query_cache()
        st.rerun()

st.sidebar.header("Filters")

bounds_df = get_date_bounds()
min_date = bounds_df.at[0, "min_d"] if not bounds_df.empty else None
max_date = bounds_df.at[0, "max_d"] if not bounds_df.empty else None

if min_date is not None and max_date is not None:
    min_date_value = min_date if isinstance(min_date, pd.Timestamp) else min_date
    max_date_value = max_date if isinstance(max_date, pd.Timestamp) else max_date
    if hasattr(min_date_value, "date"):
        min_date_value = min_date_value.date()
    if hasattr(max_date_value, "date"):
        max_date_value = max_date_value.date()

    visit_date_range = st.sidebar.date_input(
        "Visit Date",
        value=(min_date_value, max_date_value),
        min_value=min_date_value,
        max_value=max_date_value,
    )
else:
    visit_date_range = st.sidebar.date_input("Visit Date", value=None)

month_df = load_month_options()
month_keys = month_df["month_key"].tolist() if not month_df.empty else []
month_labels = {row["month_key"]: row["month_label"] for _, row in month_df.iterrows()}
selected_months = st.sidebar.multiselect(
    "Month",
    options=month_keys,
    default=month_keys,
    format_func=lambda x: month_labels.get(x, x),
)

rm_options = load_distinct_values(RM_COLUMN)
team_leader_options = load_distinct_values(TEAM_LEADER_COLUMN)
lead_source_options = load_distinct_values(SOURCE_COLUMN)
data_source_options = load_distinct_values(DATA_SOURCE_COLUMN)
association_options = load_distinct_values(ASSOCIATION_COLUMN)
main_disposition_options = load_distinct_values(MAIN_DISPOSITION_COLUMN)
sub_disposition_options = load_distinct_values(SUB_DISPOSITION_COLUMN)

selected_rms = st.sidebar.multiselect("RM Name", rm_options, default=rm_options)
selected_team_leaders = st.sidebar.multiselect("Team Leader", team_leader_options, default=team_leader_options)
selected_lead_sources = st.sidebar.multiselect("Lead Source", lead_source_options, default=lead_source_options)
selected_data_sources = st.sidebar.multiselect("Data Source", data_source_options, default=data_source_options)
selected_associations = st.sidebar.multiselect("Association", association_options, default=association_options)
selected_main_dispositions = st.sidebar.multiselect("Main Disposition", main_disposition_options, default=main_disposition_options)
selected_sub_dispositions = st.sidebar.multiselect("Sub Disposition", sub_disposition_options, default=sub_disposition_options)

all_filter_values = {
    "rms": rm_options,
    "team_leaders": team_leader_options,
    "lead_sources": lead_source_options,
    "data_sources": data_source_options,
    "associations": association_options,
    "main_dispositions": main_disposition_options,
    "sub_dispositions": sub_disposition_options,
}

where_sql, params = build_filters(
    visit_date_range,
    selected_months,
    selected_rms,
    selected_team_leaders,
    selected_lead_sources,
    selected_data_sources,
    selected_associations,
    selected_main_dispositions,
    selected_sub_dispositions,
    all_filter_values,
)

render_header("📈", "Leads Utilisation", "Data analytics for leads, conversion, premium, and RM performance.")

try:
    summary_df = load_summary(where_sql, params)
    source_analysis_df = load_lead_source_analysis(where_sql, params)
    source_conversion_df = load_lead_source_conversion(where_sql, params)
    mom_df = load_mom_trend(where_sql, params)
    top_rm_df = load_top_rm_conversion(where_sql, params)
    main_disposition_df = load_main_disposition(where_sql, params)
    sub_disposition_df = load_sub_disposition(where_sql, params)
    rm_detail_df = load_rm_detail(where_sql, params)
    source_summary_df = load_source_summary(where_sql, params)
except Exception as e:
    st.error("Dashboard query execution me problem aayi. Column names aur schema check karo.")
    st.exception(e)
    st.stop()

if summary_df.empty:
    st.info("Koi data nahi mila. Filters aur table ko check karein.")
    st.stop()

summary = summary_df.iloc[0]
total_leads = int(summary["total_leads"] or 0)
converted_leads = int(summary["converted_leads"] or 0)
total_premium = float(summary["total_premium"] or 0)
avg_premium_per_converted = total_premium / converted_leads if converted_leads else 0
conversion_pct = safe_div(converted_leads, total_leads)

section_header("📊", "Key Performance Indicators")

kpi_cards = [
    kpi_card("📌", "Total Leads", f"{total_leads:,}"),
    kpi_card("✅", "Converted Leads", f"{converted_leads:,}"),
    kpi_card("📈", "Conversion %", fmt_pct(conversion_pct)),
    kpi_card("💰", "Total Premium", fmt_inr_auto(total_premium)),
    kpi_card("📊", "Avg Premium / Lead", fmt_inr_auto(avg_premium_per_converted)),
]
render_kpi_row(kpi_cards[:3])
render_kpi_row(kpi_cards[3:])

section_header("📈", "Charts")

# Lead Source Analysis
if not source_analysis_df.empty:
    fig_source_analysis = px.bar(
        source_analysis_df,
        x="lead_source",
        y=["total_leads", "converted_leads"],
        title="Lead Source Analysis",
        template="plotly_dark",
        barmode="group",
        text_auto=True,
    )
    fig_source_analysis.update_layout(**PLOTLY_DARK_LAYOUT, xaxis_title="Lead Source", yaxis_title="Leads")
    st.plotly_chart(fig_source_analysis, use_container_width=True)
else:
    st.info("Lead source analysis ke liye data nahi mila.")

# Lead Source Conversion Rate
if not source_conversion_df.empty:
    fig_source_conv = px.bar(
        source_conversion_df,
        x="lead_source",
        y="conversion_pct",
        title="Lead Source Conversion Rate %",
        template="plotly_dark",
        text_auto=True,
    )
    fig_source_conv.update_layout(**PLOTLY_DARK_LAYOUT, xaxis_title="Lead Source", yaxis_title="Conversion %")
    st.plotly_chart(fig_source_conv, use_container_width=True)
else:
    st.info("Lead source conversion data nahi mila.")

# MOM Trend
if not mom_df.empty:
    mom_df = mom_df.sort_values("month_date")
    mom_df["month_date"] = pd.to_datetime(mom_df["month_date"], errors="coerce")
    mom_df["month_label"] = mom_df["month_date"].dt.strftime("%b %Y")
    fig_mom = px.line(
        mom_df,
        x="month_label",
        y=["total_leads", "converted_leads"],
        title="MOM Trend",
        template="plotly_dark",
        markers=True,
    )
    fig_mom.update_traces(
        mode="lines+markers+text",
        texttemplate="%{y:,.0f}",
        textposition="top center",
        textfont=dict(size=13, color="#e2e8f0"),
    )
    fig_mom.update_layout(**PLOTLY_DARK_LAYOUT, xaxis_title="Month", yaxis_title="Leads")
    max_mom_value = mom_df[["total_leads", "converted_leads"]].max().max()
    fig_mom.update_yaxes(range=[0, max_mom_value * 1.15 if max_mom_value else 1])
    st.plotly_chart(fig_mom, use_container_width=True)
else:
    st.info("MOM trend data nahi mila.")

# Top 10 RM by Conversion Rate
if not top_rm_df.empty:
    fig_top_rm = px.bar(
        top_rm_df,
        x="conversion_pct",
        y="rm_name",
        title="Top 10 RM by Conversion Rate %",
        template="plotly_dark",
        orientation="h",
        text_auto=True,
    )
    fig_top_rm.update_layout(**PLOTLY_DARK_LAYOUT, xaxis_title="Conversion %", yaxis_title="RM Name")
    st.plotly_chart(fig_top_rm, use_container_width=True)
else:
    st.info("RM conversion data nahi mila.")

# Main Disposition
if not main_disposition_df.empty:
    fig_main_disp = px.pie(
        main_disposition_df,
        names="main_disposition",
        values="leads",
        title="Main Disposition Analysis",
        template="plotly_dark",
    )
    fig_main_disp.update_traces(textinfo="percent+label")
    st.plotly_chart(fig_main_disp, use_container_width=True)
else:
    st.info("Main disposition data nahi mila.")

# Sub Disposition Label
if not sub_disposition_df.empty:
    fig_sub_disp = px.bar(
        sub_disposition_df,
        x="sub_disposition",
        y="leads",
        title="Sub Disposition Label",
        template="plotly_dark",
        text_auto=True,
    )
    fig_sub_disp.update_layout(**PLOTLY_DARK_LAYOUT, xaxis_title="Sub Disposition", yaxis_title="Leads")
    st.plotly_chart(fig_sub_disp, use_container_width=True)
else:
    st.info("Sub disposition data nahi mila.")

section_header("📋", "Tables")

# RM wise Detailed Performance
if not rm_detail_df.empty:
    rm_detail_df["conversion_pct"] = rm_detail_df["conversion_pct"].fillna(0)
    rm_detail_df["premium"] = rm_detail_df["premium"].fillna(0)
    rm_detail_df["ats"] = rm_detail_df.apply(lambda row: safe_ratio(row["premium"], row["converted_leads"]), axis=1)
    rm_detail_df = rm_detail_df.sort_values(["rm_name", "total_leads", "lead_source"], ascending=[True, False, True])

    rm_blocks = []
    for rm_name, group in rm_detail_df.groupby("rm_name", sort=False):
        rm_blocks.append(group)
        total_leads_for_rm = group["total_leads"].sum()
        premium_for_rm = group["premium"].sum()
        rm_blocks.append(pd.DataFrame([{
            "rm_name": f"{rm_name} Total",
            "lead_source": "",
            "total_leads": total_leads_for_rm,
            "converted_leads": group["converted_leads"].sum(),
            "premium": premium_for_rm,
            "conversion_pct": safe_div(group["converted_leads"].sum(), total_leads_for_rm),
            "ats": safe_ratio(premium_for_rm, group["converted_leads"].sum()),
        }]))

    rm_total = pd.concat(rm_blocks, ignore_index=True)
    grand_total_leads = rm_detail_df["total_leads"].sum()
    grand_total_premium = rm_detail_df["premium"].sum()
    rm_total = pd.concat([rm_total, pd.DataFrame([{
        "rm_name": "TABLE TOTAL",
        "lead_source": "",
        "total_leads": grand_total_leads,
        "converted_leads": rm_detail_df["converted_leads"].sum(),
        "premium": grand_total_premium,
        "conversion_pct": safe_div(rm_detail_df["converted_leads"].sum(), grand_total_leads),
        "ats": safe_ratio(grand_total_premium, rm_detail_df["converted_leads"].sum()),
    }])], ignore_index=True)

    rm_total = rm_total.rename(columns={
        "rm_name": "RM Name",
        "lead_source": "Lead Source",
        "total_leads": "Leads",
        "converted_leads": "Converted Leads",
        "premium": "Premium",
        "conversion_pct": "Conversion%",
        "ats": "ATS",
    })
    st.write("### RM wise Detailed Performance")
    add_table_download(rm_total, "rm_wise_detailed_performance.csv", "download_rm_wise_detailed_performance")
    st.dataframe(rm_total.style.format({
        "Premium": fmt_inr_auto,
        "Conversion%": lambda v: fmt_pct(v),
        "ATS": fmt_inr_auto,
    }), use_container_width=True)
else:
    st.info("RM detail table data nahi mila.")

# Source wise Summary
if not source_summary_df.empty:
    source_summary_df["conversion_pct"] = source_summary_df["conversion_pct"].fillna(0)
    source_summary_df["premium"] = source_summary_df["premium"].fillna(0)
    source_summary_df["ats"] = source_summary_df.apply(lambda row: safe_ratio(row["premium"], row["converted_leads"]), axis=1)
    source_total = add_total_row(
        source_summary_df,
        label_col="lead_source",
        sum_cols=["total_leads", "converted_leads", "premium"],
        computed_cols={
            "conversion_pct": lambda totals: safe_div(totals["converted_leads"], totals["total_leads"]),
            "ats": lambda totals: safe_ratio(totals["premium"], totals["converted_leads"]),
        },
        label="TOTAL",
    )
    source_total = source_total.rename(columns={
        "lead_source": "Lead Source",
        "total_leads": "Leads",
        "converted_leads": "Converted Leads",
        "premium": "Premium",
        "conversion_pct": "Conversion%",
        "ats": "ATS",
    })
    st.write("### Source wise Summary")
    add_table_download(source_total, "source_wise_summary.csv", "download_source_wise_summary")
    st.dataframe(source_total.style.format({
        "Premium": fmt_inr_auto,
        "Conversion%": lambda v: fmt_pct(v),
        "ATS": fmt_inr_auto,
    }), use_container_width=True)
else:
    st.info("Source summary table data nahi mila.")
