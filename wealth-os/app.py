"""Wealth OS — local-first personal finance and wealth planning app.

Streamlit entry point. Run with: streamlit run app.py
"""
import streamlit as st

from wealth_os.config import APP_TITLE, DB_PATH
from wealth_os.db import get_connection, init_db
from wealth_os.transactions import count_transactions

st.set_page_config(page_title=APP_TITLE, layout="wide")
init_db()

st.title(APP_TITLE)
st.caption("A local-first personal finance and wealth planning app. All data stays on your machine.")

with get_connection() as conn:
    sqlite_version = conn.execute("SELECT sqlite_version()").fetchone()[0]

st.success(f"Connected to local database at `data/{DB_PATH.name}` (SQLite {sqlite_version})")
st.metric("Transactions imported", count_transactions())
st.info("Use **Import Transactions** in the sidebar to load a CSV.")
