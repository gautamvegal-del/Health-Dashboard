"""
utils/gsheet_connector.py
--------------------------------
Yeh file Google Sheet se data fetch karne ka common kaam karti hai.
Sabhi 4 pages isi function ko call karenge, sirf sheet name/url alag denge.
"""

import os
import re
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from urllib.parse import urlparse

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _clear_broken_local_proxy():
    """Remove dead Windows proxy placeholders that break Google API requests."""
    proxy_vars = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    for name in proxy_vars:
        value = os.environ.get(name, "")
        if "127.0.0.1:9" in value or "localhost:9" in value:
            os.environ.pop(name, None)


def _extract_sheet_key(sheet_url: str) -> str:
    """Google Sheet URL se spreadsheet key nikalta hai."""
    parsed = urlparse(sheet_url)
    parts = [part for part in parsed.path.split("/") if part]
    if "d" in parts:
        key_index = parts.index("d") + 1
        if key_index < len(parts):
            return parts[key_index]
    return sheet_url


def _cache_path(worksheet_name: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", worksheet_name).strip("_")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_dir = os.path.join(project_root, ".cache", "sheet_data")
    return os.path.join(cache_dir, f"{safe_name or 'worksheet'}.csv")


def _save_sheet_cache(worksheet_name: str, df: pd.DataFrame) -> None:
    path = _cache_path(worksheet_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def _load_sheet_cache(worksheet_name: str) -> pd.DataFrame | None:
    path = _cache_path(worksheet_name)
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def _load_excel_backup(worksheet_name: str) -> pd.DataFrame | None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for file_name in ("Health Calling Dashboard.xlsx", "Health Leads Utilisation.xlsx"):
        path = os.path.join(project_root, file_name)
        if not os.path.exists(path):
            continue
        try:
            workbook = pd.ExcelFile(path)
            if worksheet_name in workbook.sheet_names:
                return pd.read_excel(path, sheet_name=worksheet_name)
        except Exception:
            continue
    return None


@st.cache_resource(show_spinner=False)
def get_gsheet_client():
    """
    Google service account credentials se ek baar client banata hai.
    st.cache_resource isliye use kiya hai taaki har baar dobara
    authenticate na karna pade (fast load ke liye).

    Pehle local JSON file dhoondta hai (VS Code / local testing ke liye).
    Agar file nahi milti, to st.secrets se padhta hai (Streamlit Cloud
    deploy karne ke baad yeh use hoga).
    """
    import glob

    _clear_broken_local_proxy()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Pehle exact naam "service_account.json" dhoondte hain
    local_json_path = os.path.join(project_root, "service_account.json")

    if not os.path.exists(local_json_path):
        # Agar exact naam nahi mila, to project root me jo bhi .json file
        # mile (jaise Google Cloud se download ki gayi
        # "symbolic-math-xxxxx.json"), usko use kar lete hain.
        json_files = glob.glob(os.path.join(project_root, "*.json"))
        if json_files:
            local_json_path = json_files[0]

    if os.path.exists(local_json_path):
        creds = Credentials.from_service_account_file(local_json_path, scopes=SCOPES)
    else:
        # Local file kahin nahi mili -> Streamlit Cloud secrets se padhega
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

    client = gspread.authorize(creds)
    return client


@st.cache_data(ttl=1800, show_spinner="Google Sheet se data load ho raha hai...")
def load_sheet_data(sheet_url: str, worksheet_name: str) -> pd.DataFrame:
    """
    Diye gaye Google Sheet URL aur worksheet (tab) name se data nikalta hai
    aur pandas DataFrame return karta hai.

    ttl=1800 -> data 30 minute tak cache rahega, fir Google Sheet se refresh hoga.
    Agar aap chahte hain ki har baar latest data aaye to ttl kam kar dena
    ya page me 'Refresh Data' button laga dena (neeche example diya hai).
    """
    try:
        client = get_gsheet_client()
        sheet = client.open_by_key(_extract_sheet_key(sheet_url))
        worksheet = sheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        _save_sheet_cache(worksheet_name, df)
    except Exception as exc:
        cached_df = _load_sheet_cache(worksheet_name)
        if cached_df is not None:
            st.warning("Google Sheet temporarily reachable nahi hai. Last saved local data dikhaya ja raha hai.")
            df = cached_df
        else:
            backup_df = _load_excel_backup(worksheet_name)
            if backup_df is not None:
                st.warning("Google Sheet temporarily reachable nahi hai. Local Excel backup dikhaya ja raha hai.")
                df = backup_df
            else:
                raise exc

    # Column names ke extra spaces clean kar dete hain (common issue)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def clear_cache():
    """Manually data refresh karne ke liye (Refresh button me use hoga)."""
    load_sheet_data.clear()
