"""Manage categorization rules and review whatever rules don't catch."""
import streamlit as st

from wealth_os.categorization import add_rule, apply_rules, delete_rule, get_rules, set_category
from wealth_os.config import APP_TITLE
from wealth_os.db import init_db
from wealth_os.transactions import get_all_transactions

st.set_page_config(page_title=f"Categorize — {APP_TITLE}", layout="wide")
init_db()

st.title("Categorize Transactions")

st.subheader("Rules")
st.caption(
    "A rule matches a case-insensitive substring against the transaction description. "
    "The first matching rule (lowest priority number first) wins. Rules only fill in "
    "transactions without a category yet — they never overwrite a manual edit."
)

rules_df = get_rules()
if len(rules_df) > 0:
    st.dataframe(rules_df, use_container_width=True, hide_index=True)
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
        category = st.text_input("Category (e.g. Dining)")
    with col3:
        priority = st.number_input("Priority", value=100, step=10)
    if st.form_submit_button("Add rule") and pattern and category:
        add_rule(pattern, category, priority)
        st.rerun()

st.divider()

if st.button("Apply rules to uncategorized transactions"):
    updated = apply_rules()
    st.success(f"Categorized {updated} transactions.")
    st.rerun()

st.subheader("Uncategorized transactions")
all_transactions = get_all_transactions()
uncategorized = all_transactions[all_transactions["category"].isna()]

if len(uncategorized) == 0:
    st.write("Nothing uncategorized.")
else:
    st.caption("Edit the category column directly, then save.")
    edited = st.data_editor(
        uncategorized[["id", "date", "description", "amount", "category"]],
        use_container_width=True,
        hide_index=True,
        disabled=["id", "date", "description", "amount"],
        key="uncategorized_editor",
    )
    if st.button("Save categories"):
        changed = edited[edited["category"].notna() & (edited["category"] != "")]
        for row in changed.itertuples(index=False):
            set_category(row.id, row.category)
        st.success(f"Updated {len(changed)} transactions.")
        st.rerun()
