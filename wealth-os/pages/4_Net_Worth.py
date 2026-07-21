"""Manual asset/liability tracking and net worth view."""
import pandas as pd
import plotly.express as px
import streamlit as st

from wealth_os.config import APP_TITLE
from wealth_os.db import init_db
from wealth_os.net_worth import (
    add_item,
    delete_item,
    get_current_net_worth,
    get_items,
    get_latest_balances,
    get_net_worth_history,
    record_balance,
)

st.set_page_config(page_title=f"Net Worth — {APP_TITLE}", layout="wide")
init_db()

st.title("Net Worth")

# --- Manage items ---
st.subheader("Assets & Liabilities")
items = get_items()
if len(items) > 0:
    st.dataframe(items[["name", "type"]], width="stretch", hide_index=True)
else:
    st.write("No items yet — add one below.")

item_col1, item_col2 = st.columns(2)
with item_col1:
    with st.form("add_item_form", clear_on_submit=True):
        new_name = st.text_input("Name (e.g. Chase Checking)")
        new_type = st.radio("Type", ["asset", "liability"], horizontal=True)
        if st.form_submit_button("Add") and new_name:
            add_item(new_name, new_type)
            st.rerun()

with item_col2:
    with st.form("delete_item_form", clear_on_submit=True):
        item_ids_by_name = dict(zip(items["name"], items["id"])) if len(items) > 0 else {}
        delete_name = st.selectbox("Delete", [""] + list(item_ids_by_name.keys()))
        st.caption("Also deletes that item's balance history.")
        if st.form_submit_button("Delete") and delete_name:
            delete_item(int(item_ids_by_name[delete_name]))
            st.rerun()

st.divider()

# --- Record a balance ---
st.subheader("Record a balance")
if len(items) == 0:
    st.write("Add an asset or liability above before recording a balance.")
else:
    with st.form("record_balance_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            item_ids_by_name = dict(zip(items["name"], items["id"]))
            balance_item_name = st.selectbox("Item", list(item_ids_by_name.keys()))
        with col2:
            balance_date = st.date_input("Date", value=pd.Timestamp.today().date())
        with col3:
            balance_value = st.number_input("Value", min_value=0.0, step=100.0)
        if st.form_submit_button("Save balance"):
            record_balance(
                int(item_ids_by_name[balance_item_name]),
                balance_date.strftime("%Y-%m-%d"),
                balance_value,
            )
            st.success(f"Recorded {balance_item_name}: ${balance_value:,.2f} on {balance_date}")
            st.rerun()

st.divider()

# --- Current net worth ---
st.subheader("Current Net Worth")
net_worth = get_current_net_worth()
k1, k2, k3 = st.columns(3)
k1.metric("Assets", f"${net_worth['assets']:,.2f}")
k2.metric("Liabilities", f"${net_worth['liabilities']:,.2f}")
k3.metric("Net Worth", f"${net_worth['net_worth']:,.2f}")

latest = get_latest_balances().dropna(subset=["value"])
if len(latest) > 0:
    fig = px.bar(latest, x="name", y="value", color="type")
    st.plotly_chart(fig, width="stretch")

st.divider()

# --- Net worth over time ---
st.subheader("Net Worth Over Time")
history = get_net_worth_history()
if len(history) == 0:
    st.write("Record at least one balance to see the net worth trend over time.")
else:
    fig2 = px.line(history, x="date", y="net_worth", markers=True)
    st.plotly_chart(fig2, width="stretch")
