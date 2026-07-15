"""Tests for rule-based categorization."""
import pandas as pd

from wealth_os.categorization import add_rule, apply_rules, set_category
from wealth_os.db import init_db
from wealth_os.transactions import get_all_transactions, insert_transactions


def _seed_transactions(db_path):
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "description": ["STARBUCKS #123", "WHOLE FOODS MARKET", "Unknown Merchant"],
            "amount": [-4.50, -62.10, -10.00],
        }
    )
    insert_transactions(df, "Checking", db_path)


def test_apply_rules_categorizes_matching_transactions(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_transactions(db_path)

    add_rule("STARBUCKS", "Dining", priority=100, db_path=db_path)
    add_rule("WHOLE FOODS", "Groceries", priority=100, db_path=db_path)

    updated = apply_rules(db_path)
    assert updated == 2

    tx = get_all_transactions(db_path)
    categories = dict(zip(tx["description"], tx["category"]))
    assert categories["STARBUCKS #123"] == "Dining"
    assert categories["WHOLE FOODS MARKET"] == "Groceries"
    assert pd.isna(categories["Unknown Merchant"])


def test_apply_rules_does_not_overwrite_manual_category(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_transactions(db_path)

    tx = get_all_transactions(db_path)
    starbucks_id = int(tx[tx["description"] == "STARBUCKS #123"]["id"].iloc[0])
    set_category(starbucks_id, "Manual Category", db_path)

    add_rule("STARBUCKS", "Dining", priority=100, db_path=db_path)
    apply_rules(db_path)

    tx = get_all_transactions(db_path)
    result = tx[tx["description"] == "STARBUCKS #123"]["category"].iloc[0]
    assert result == "Manual Category"


def test_first_matching_rule_wins_by_priority(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed_transactions(db_path)

    add_rule("STAR", "Generic", priority=200, db_path=db_path)
    add_rule("STARBUCKS", "Dining", priority=10, db_path=db_path)

    apply_rules(db_path)

    tx = get_all_transactions(db_path)
    result = tx[tx["description"] == "STARBUCKS #123"]["category"].iloc[0]
    assert result == "Dining"
