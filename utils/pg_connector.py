"""
utils/pg_connector.py
--------------------------------
Postgres se data lane ka common function. Calling Dashboard (aur aage
jo bhi SQL-based dashboards banenge) isi ko use karenge.

IMPORTANT: 1.5M+ rows hai isliye hum kabhi "SELECT * FROM table" pura
nahi karenge. Hamesha SQL me hi SUM/COUNT/GROUP BY/WHERE laga ke
sirf chhota, already-aggregated result Python me layenge. Yeh
dashboard ko fast rakhega.
"""

import streamlit as st
import pandas as pd
import psycopg2
from pathlib import Path
import tomllib

print(f"DEBUG: loaded utils.pg_connector from {__file__}")


def _load_secrets_section(section: str) -> dict:
    candidates = [
        Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml",
        Path.cwd() / ".streamlit" / "secrets.toml",
    ]

    for config_path in candidates:
        if not config_path.exists():
            continue

        try:
            raw = config_path.read_text(encoding="utf-8")
            parsed = tomllib.loads(raw)
            if section in parsed:
                return parsed[section]
        except Exception:
            pass

    if section in st.secrets:
        return st.secrets[section]

    raise KeyError(f"Secrets section '{section}' not found in .streamlit/secrets.toml")


@st.cache_resource(show_spinner=False)
def get_pg_connection(section: str = "postgres"):
    """Postgres connection object ek baar banata hai (cached)."""
    pg = _load_secrets_section(section)
    return psycopg2.connect(
        host=pg["host"],
        port=pg["port"],
        dbname=pg.get("dbname") or pg.get("database"),
        user=pg["user"],
        password=pg["password"],
    )


@st.cache_data(ttl=300, show_spinner="Database se data la rahe hain...")
def run_query(sql: str, params: dict | None = None, section: str = "postgres") -> pd.DataFrame:
    """
    Koi bhi SQL query chala ke pandas DataFrame return karta hai.
    Example:
        df = run_query('SELECT "Employee Name", COUNT(*) as calls
                         FROM calling_dashboard GROUP BY "Employee Name"')
    """
    conn = get_pg_connection(section)
    return pd.read_sql(sql, conn, params=params)


def clear_query_cache():
    """Manually cache clear karne ke liye (Refresh button me use hoga)."""
    run_query.clear()
    get_pg_connection.clear()
