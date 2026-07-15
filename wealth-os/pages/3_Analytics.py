"""Spending analytics: monthly trends, category breakdown, and a filterable table."""
import pandas as pd
import plotly.express as px
import streamlit as st

from wealth_os.analytics import category_breakdown, monthly_category_totals
from wealth_os.config import APP_TITLE
from wealth_os.db import init_db
from wealth_os.transactions import get_all_transactions

st.set_page_config(page_title=f"Analytics — {APP_TITLE}", layout="wide")
init_db()

st.title("Spending Analytics")

transactions = get_all_transactions()
if len(transactions) == 0:
    st.info("No transactions yet. Import some on the Import Transactions page.")
    st.stop()

transactions["category"] = transactions["category"].fillna("Uncategorized")
transactions["date"] = pd.to_datetime(transactions["date"])

st.subheader("Filters")
col1, col2, col3, col4 = st.columns(4)
min_date, max_date = transactions["date"].min().date(), transactions["date"].max().date()
with col1:
    date_range = st.date_input(
        "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )
with col2:
    accounts = st.multiselect("Account", sorted(transactions["account"].unique()))
with col3:
    categories = st.multiselect("Category", sorted(transactions["category"].unique()))
with col4:
    search = st.text_input("Description contains")

filtered = transactions.copy()
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[(filtered["date"].dt.date >= start) & (filtered["date"].dt.date <= end)]
if accounts:
    filtered = filtered[filtered["account"].isin(accounts)]
if categories:
    filtered = filtered[filtered["category"].isin(categories)]
if search:
    filtered = filtered[filtered["description"].str.contains(search, case=False, na=False)]

st.divider()

spend = -filtered.loc[filtered["amount"] < 0, "amount"].sum()
income = filtered.loc[filtered["amount"] > 0, "amount"].sum()
net = filtered["amount"].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Spend", f"${spend:,.2f}")
k2.metric("Income", f"${income:,.2f}")
k3.metric("Net", f"${net:,.2f}")
k4.metric("Transactions", len(filtered))

st.divider()

st.subheader("Monthly spend by category")
monthly = monthly_category_totals(filtered)
if len(monthly) == 0:
    st.write("No spending in this range.")
else:
    fig = px.bar(monthly, x="month", y="spend", color="category", barmode="stack")
    st.plotly_chart(fig, width="stretch")

st.subheader("Category breakdown")
breakdown = category_breakdown(filtered)
if len(breakdown) == 0:
    st.write("No spending in this range.")
else:
    fig2 = px.bar(breakdown, x="category", y="spend")
    st.plotly_chart(fig2, width="stretch")

st.divider()

st.subheader("Transactions")
st.caption("Click a column header to sort.")
st.dataframe(
    filtered[["date", "description", "amount", "account", "category"]].sort_values(
        "date", ascending=False
    ),
    width="stretch",
    hide_index=True,
)
