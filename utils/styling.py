"""
utils/styling.py
--------------------------------
Yahan dashboard ki DESIGN/STYLE rakhi hai (dark theme, KPI cards,
section headers, badges) - jo aapke reference screenshot jaisi
dikhti hai. Har page ke top par inject_custom_css() call karna hai.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta


def inject_custom_css():
    """Pura dashboard ko dark theme + card style dene wali CSS."""
    st.markdown(
        """
        <style>
        /* ---------- Overall App Background ---------- */
        .stApp {
            background-color: #0b1220;
        }
        section[data-testid="stSidebar"] {
            background-color: #0d1424;
            border-right: 1px solid #1f2937;
        }

        /* ---------- Hide default Streamlit chrome ---------- */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* ---------- Header block ---------- */
        .dash-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 28px;
        }
        .dash-title-row {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .dash-icon-box {
            font-size: 34px;
            line-height: 1;
        }
        .dash-title {
            font-size: 34px;
            font-weight: 800;
            color: #f8fafc;
            margin: 0;
        }
        .dash-subtitle {
            color: #94a3b8;
            font-size: 14px;
            margin-top: 4px;
        }
        .live-badge {
            background: rgba(34,197,94,0.12);
            border: 1px solid rgba(34,197,94,0.4);
            color: #22c55e;
            padding: 8px 16px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: 600;
            white-space: nowrap;
        }
        .live-dot {
            display: inline-block;
            width: 7px;
            height: 7px;
            background: #22c55e;
            border-radius: 50%;
            margin-right: 6px;
        }

        /* ---------- Section Header ---------- */
        .section-header {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #60a5fa;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 1.2px;
            text-transform: uppercase;
            margin: 28px 0 14px 0;
            border-top: 1px solid #1f2937;
            padding-top: 18px;
        }

        /* ---------- KPI Card ---------- */
        .kpi-card {
            background: linear-gradient(180deg, #111a2e 0%, #0e1626 100%);
            border: 1px solid #1f2937;
            border-radius: 14px;
            padding: 18px 18px 16px 18px;
            position: relative;
            overflow: hidden;
            margin-bottom: 14px;
            min-height: 132px;
        }
        .kpi-card::before {
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 4px;
            background: var(--accent, #3b82f6);
        }
        .kpi-icon { font-size: 22px; margin-bottom: 10px; }
        .kpi-label {
            font-size: 11px;
            letter-spacing: 1.1px;
            color: #94a3b8;
            text-transform: uppercase;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .kpi-value {
            font-size: 26px;
            font-weight: 800;
            color: #f8fafc;
            font-family: 'Courier New', monospace;
            margin-bottom: 4px;
        }
        .kpi-sub { font-size: 12px; color: #94a3b8; }
        .kpi-sub.positive { color: #22c55e; font-weight: 600; }
        .kpi-sub.negative { color: #ef4444; font-weight: 600; }

        /* ---------- Plain card (for tables / charts wrapper) ---------- */
        .panel-card {
            background: #0e1626;
            border: 1px solid #1f2937;
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 18px;
        }

        /* Streamlit dataframe dark tint */
        [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(icon: str, title: str, subtitle: str):
    """Top par icon + title + subtitle + LIVE badge dikhata hai."""
    now_str = datetime.now().strftime("%d %b %Y, %H:%M")
    st.markdown(
        f"""
        <div class="dash-header">
            <div>
                <div class="dash-title-row">
                    <div class="dash-icon-box">{icon}</div>
                    <div class="dash-title">{title}</div>
                </div>
                <div class="dash-subtitle">{subtitle}</div>
            </div>
            <div class="live-badge"><span class="live-dot"></span>LIVE &nbsp;·&nbsp; {now_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(icon: str, text: str):
    st.markdown(
        f'<div class="section-header">{icon} {text}</div>',
        unsafe_allow_html=True,
    )


def kpi_card(icon: str, label: str, value: str, sub_text: str = "",
             sub_class: str = "", accent: str = "#3b82f6") -> str:
    """Ek KPI card ka HTML banata hai. sub_class: '' | 'positive' | 'negative'"""
    return f"""
    <div class="kpi-card" style="--accent:{accent}">
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub {sub_class}">{sub_text}</div>
    </div>
    """


def render_kpi_row(cards: list):
    """List of kpi_card() html strings ko ek row me equal columns me dikhata hai."""
    cols = st.columns(len(cards))
    for col, html in zip(cols, cards):
        with col:
            st.markdown(html, unsafe_allow_html=True)


# ---------- Number formatting helpers (Indian style: Cr / Lakh) ----------

def fmt_cr(value: float) -> str:
    """₹ value ko Crore me format karta hai. Example: 44700000 -> ₹4.47 Cr"""
    return f"₹{value / 1e7:,.2f} Cr"


def fmt_lakh(value: float) -> str:
    """₹ value ko Lakh me format karta hai. Example: 8715000 -> ₹87.15 L"""
    return f"₹{value / 1e5:,.2f} L"


def fmt_inr_auto(value: float) -> str:
    """Value ke size ke hisaab se auto Cr/Lakh/plain me format karta hai."""
    value = float(value)
    if abs(value) >= 1e7:
        return fmt_cr(value)
    elif abs(value) >= 1e5:
        return fmt_lakh(value)
    else:
        return f"₹{value:,.0f}"


def fmt_pct(value: float) -> str:
    return f"{value:,.1f}%"


def fmt_duration(td) -> str:
    """Timedelta (Postgres INTERVAL se aata hai) ko 'Xh Ym Zs' format me dikhata hai."""
    if td is None or (isinstance(td, float) and pd.isna(td)):
        return "0h 0m 0s"
    if not isinstance(td, timedelta):
        try:
            td = pd.to_timedelta(td)
        except Exception:
            return "0h 0m 0s"
    total_seconds = int(td.total_seconds())
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s"


def add_total_row(df, label_col: str, sum_cols: list, computed_cols: dict = None, label: str = "TOTAL"):
    """
    Aggregated table ke neeche ek 'TOTAL' row add karta hai.

    df: aggregated dataframe (groupby ke baad wala)
    label_col: category column ka naam (e.g. 'Insurer', 'State')
    sum_cols: jo columns seedhe sum honge (Premium, NOP, etc.)
    computed_cols: {column_name: function(total_dict) -> value}
                   jo columns sum se nahi balki recompute karne hain
                   (jaise ATS, Cont%, Issuance% etc.) - sum hone ke
                   baad available total_dict se calculate hote hain.
    """
    import pandas as pd

    total = {col: None for col in df.columns}
    total[label_col] = label
    for col in sum_cols:
        total[col] = df[col].sum()
    if computed_cols:
        for col, fn in computed_cols.items():
            total[col] = fn(total)
    return pd.concat([df, pd.DataFrame([total])], ignore_index=True)
