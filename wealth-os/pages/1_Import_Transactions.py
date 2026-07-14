"""Import bank transactions from a CSV file."""
import pandas as pd
import streamlit as st

from wealth_os.config import APP_TITLE
from wealth_os.db import init_db
from wealth_os.transactions import insert_transactions

st.set_page_config(page_title=f"Import — {APP_TITLE}", layout="wide")
init_db()

st.title("Import Transactions")
st.caption(
    "Upload a CSV export from your bank or credit card. You'll map the columns "
    "yourself since every bank formats exports differently."
)

uploaded_file = st.file_uploader("CSV file", type="csv")

if uploaded_file is not None:
    raw_df = pd.read_csv(uploaded_file)
    st.write("Preview of uploaded file:")
    st.dataframe(raw_df.head(10), use_container_width=True)

    columns = list(raw_df.columns)
    st.subheader("Map columns")
    col1, col2, col3 = st.columns(3)
    with col1:
        date_col = st.selectbox("Date column", columns)
    with col2:
        description_col = st.selectbox("Description column", columns)
    with col3:
        amount_col = st.selectbox("Amount column", columns)

    account = st.text_input("Account name", placeholder="e.g. Chase Checking")
    flip_sign = st.checkbox(
        "Flip amount sign (check this if expenses appear as positive numbers in this file)",
        value=False,
    )

    if st.button("Preview normalized transactions", disabled=not account):
        normalized = pd.DataFrame(
            {
                "date": pd.to_datetime(raw_df[date_col], errors="coerce"),
                "description": raw_df[description_col].astype(str),
                "amount": pd.to_numeric(raw_df[amount_col], errors="coerce"),
            }
        )
        if flip_sign:
            normalized["amount"] = -normalized["amount"]

        bad_row_count = normalized["date"].isna().sum() + normalized["amount"].isna().sum()
        normalized = normalized.dropna(subset=["date", "amount"])

        st.session_state["pending_import"] = normalized
        st.session_state["pending_account"] = account

        st.write(f"{len(normalized)} rows parsed successfully.")
        st.dataframe(normalized.head(20), use_container_width=True)
        if bad_row_count > 0:
            st.warning(f"{bad_row_count} rows couldn't be parsed and will be skipped.")

    if "pending_import" in st.session_state and st.button("Save to database"):
        inserted, skipped = insert_transactions(
            st.session_state["pending_import"], st.session_state["pending_account"]
        )
        st.success(f"Imported {inserted} new transactions ({skipped} duplicates skipped).")
        del st.session_state["pending_import"]
        del st.session_state["pending_account"]
