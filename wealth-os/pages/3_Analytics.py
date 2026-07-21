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

st.subheader("Period")
period_type = st.radio("Period", ["Month", "Year to date", "All time"], horizontal=True, label_visibility="collapsed")

if period_type == "Month":
    available_months = sorted(transactions["date"].dt.to_period("M").astype(str).unique(), reverse=True)
    selected_month = st.selectbox(
        "Month",
        available_months,
        format_func=lambda m: pd.Period(m).strftime("%B %Y"),
    )
    period = pd.Period(selected_month)
    period_start, period_end = period.start_time.date(), period.end_time.date()
elif period_type == "Year to date":
    latest = transactions["date"].max()
    period_start = pd.Timestamp(year=latest.year, month=1, day=1).date()
    period_end = latest.date()
else:
    period_start = transactions["date"].min().date()
    period_end = transactions["date"].max().date()

st.subheader("Filters")
col2, col3, col4 = st.columns(3)
with col2:
    accounts = st.multiselect("Account", sorted(transactions["account"].unique()))
with col3:
    categories = st.multiselect("Category", sorted(transactions["category"].unique()))
with col4:
    search = st.text_input("Description contains")

filtered = transactions[
    (transactions["date"].dt.date >= period_start) & (transactions["date"].dt.date <= period_end)
].copy()
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

if period_type != "Month":
    st.subheader("Monthly spend by category")
    monthly = monthly_category_totals(filtered)
    if len(monthly) == 0:
        st.write("No spending in this range.")
    else:
        fig = px.bar(monthly, x="month", y="spend", color="category", barmode="stack")
        st.plotly_chart(fig, width="stretch")

chart_type = st.radio("Chart type", ["Bar", "Pie"], horizontal=True)
st.subheader("Category breakdown")
breakdown = category_breakdown(filtered)
if len(breakdown) == 0:
    st.write("No spending in this range.")
elif chart_type == "Bar":
    fig2 = px.bar(breakdown, x="category", y="spend")
    st.plotly_chart(fig2, width="stretch")
else:
    fig2 = px.pie(breakdown, names="category", values="spend")
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
