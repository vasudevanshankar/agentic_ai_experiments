"""Wealth OS — local-first personal finance and wealth planning app.

Streamlit entry point. Run with: streamlit run app.py
"""
import streamlit as st

from wealth_os.config import APP_TITLE, DB_PATH
from wealth_os.db import get_connection

st.set_page_config(page_title=APP_TITLE, layout="wide")

st.title(APP_TITLE)
st.caption("A local-first personal finance and wealth planning app. All data stays on your machine.")

with get_connection() as conn:
    sqlite_version = conn.execute("SELECT sqlite_version()").fetchone()[0]

st.success(f"Connected to local database at `data/{DB_PATH.name}` (SQLite {sqlite_version})")
st.info("Project scaffold complete. CSV import, categorization, and dashboards come next.")
