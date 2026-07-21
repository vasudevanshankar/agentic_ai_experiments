"""Manage the category list, categorization rules, and transaction categories."""
import streamlit as st

from wealth_os.categories import (
    add_category,
    delete_category,
    get_categories,
    get_category_usage,
    rename_category,
)
from wealth_os.categorization import add_rule, apply_rules, delete_rule, get_rules, set_category
from wealth_os.config import APP_TITLE
from wealth_os.db import init_db
from wealth_os.transactions import get_all_transactions

st.set_page_config(page_title=f"Categorize — {APP_TITLE}", layout="wide")
init_db()

st.title("Categorize Transactions")

# --- Categories ---
st.subheader("Categories")
usage = get_category_usage()
if len(usage) > 0:
    st.dataframe(usage, width="stretch", hide_index=True)
else:
    st.write("No categories yet — add one below.")

cat_col1, cat_col2, cat_col3 = st.columns(3)
with cat_col1:
    with st.form("add_category_form", clear_on_submit=True):
        new_category = st.text_input("New category name")
        if st.form_submit_button("Add") and new_category:
            add_category(new_category)
            st.rerun()

categories = get_categories()
with cat_col2:
    with st.form("rename_category_form", clear_on_submit=True):
        rename_target = st.selectbox("Rename", [""] + categories)
        rename_to = st.text_input("New name")
        if st.form_submit_button("Rename") and rename_target and rename_to:
            rename_category(rename_target, rename_to)
            st.rerun()

with cat_col3:
    with st.form("delete_category_form", clear_on_submit=True):
        delete_target = st.selectbox("Delete", [""] + categories)
        st.caption("Transactions using it revert to uncategorized.")
        if st.form_submit_button("Delete") and delete_target:
            delete_category(delete_target)
            st.rerun()

st.divider()

# --- Rules ---
st.subheader("Rules")
st.caption(
    "A rule matches a case-insensitive substring against the transaction description. "
    "The first matching rule (lowest priority number first) wins. Rules only fill in "
    "transactions without a category yet — they never overwrite a manual edit."
)

rules_df = get_rules()
if len(rules_df) > 0:
    st.dataframe(rules_df, width="stretch", hide_index=True)
    delete_id = st.selectbox(
        "Delete a rule",
        options=[None] + rules_df["id"].tolist(),
        format_func=lambda x: "—" if x is None else f"#{x}",
    )
    if delete_id is not None and st.button("Delete selected rule"):
        delete_rule(delete_id)
        st.rerun()
else:
    st.write("No rules yet — add one below.")

with st.form("add_rule_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        pattern = st.text_input("Pattern (e.g. STARBUCKS)")
    with col2:
        rule_category = st.text_input("Category (e.g. Dining)")
    with col3:
        priority = st.number_input("Priority", value=100, step=10)
    if st.form_submit_button("Add rule") and pattern and rule_category:
        add_rule(pattern, rule_category, priority)
        st.rerun()

st.divider()

if st.button("Apply rules to uncategorized transactions"):
    updated = apply_rules()
    st.success(f"Categorized {updated} transactions.")
    st.rerun()

# --- Transactions ---
st.subheader("Transactions")
show_all = not st.checkbox("Show only uncategorized", value=True)
all_transactions = get_all_transactions()
visible = all_transactions if show_all else all_transactions[all_transactions["category"].isna()]

if len(visible) == 0:
    st.write("Nothing to show.")
else:
    st.caption("Edit the category column directly, then save.")
    category_options = ["Uncategorized"] + get_categories()
    display_df = visible[["id", "date", "description", "amount", "category"]].copy()
    display_df["category"] = display_df["category"].fillna("Uncategorized")

    edited = st.data_editor(
        display_df,
        width="stretch",
        hide_index=True,
        disabled=["id", "date", "description", "amount"],
        column_config={
            "category": st.column_config.SelectboxColumn("category", options=category_options)
        },
        key="transactions_editor",
    )
    if st.button("Save categories"):
        changes = edited[edited["category"] != display_df["category"]]
        for row in changes.itertuples(index=False):
            new_category = None if row.category == "Uncategorized" else row.category
            set_category(row.id, new_category)
        st.success(f"Updated {len(changes)} transactions.")
        st.rerun()
