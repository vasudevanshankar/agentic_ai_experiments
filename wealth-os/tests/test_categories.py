"""Tests for category taxonomy management."""
import pandas as pd

from wealth_os.categories import (
    add_category,
    delete_category,
    get_categories,
    rename_category,
)
from wealth_os.categorization import add_rule, get_rules
from wealth_os.db import init_db
from wealth_os.transactions import get_all_transactions, insert_transactions


def _seed(db_path):
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "description": ["Coffee Shop", "Grocery Store"],
            "amount": [-4.50, -60.0],
        }
    )
    insert_transactions(df, "Checking", db_path)


def test_add_category_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    add_category("Dining", db_path)
    add_category("Dining", db_path)
    assert get_categories(db_path) == ["Dining"]


def test_rename_category_cascades_to_transactions_and_rules(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed(db_path)

    add_rule("COFFEE", "Dining", db_path=db_path)
    tx = get_all_transactions(db_path)
    coffee_id = int(tx[tx["description"] == "Coffee Shop"]["id"].iloc[0])
    from wealth_os.categorization import set_category

    set_category(coffee_id, "Dining", db_path)

    rename_category("Dining", "Food & Dining", db_path)

    assert "Food & Dining" in get_categories(db_path)
    assert "Dining" not in get_categories(db_path)

    tx = get_all_transactions(db_path)
    assert tx[tx["id"] == coffee_id]["category"].iloc[0] == "Food & Dining"

    rules = get_rules(db_path)
    assert rules[rules["pattern"] == "COFFEE"]["category"].iloc[0] == "Food & Dining"


def test_rename_category_merges_into_existing_target(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    add_category("Dining", db_path)
    add_category("Food", db_path)

    rename_category("Dining", "Food", db_path)

    assert get_categories(db_path) == ["Food"]


def test_delete_category_reverts_transactions_to_uncategorized(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed(db_path)

    from wealth_os.categorization import set_category

    tx = get_all_transactions(db_path)
    coffee_id = int(tx[tx["description"] == "Coffee Shop"]["id"].iloc[0])
    add_category("Dining", db_path)
    set_category(coffee_id, "Dining", db_path)

    delete_category("Dining", db_path)

    assert "Dining" not in get_categories(db_path)
    tx = get_all_transactions(db_path)
    assert pd.isna(tx[tx["id"] == coffee_id]["category"].iloc[0])


def test_init_db_backfills_categories_from_existing_data(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    _seed(db_path)

    from wealth_os.categorization import set_category

    tx = get_all_transactions(db_path)
    coffee_id = int(tx[tx["description"] == "Coffee Shop"]["id"].iloc[0])
    # Set a category directly, bypassing add_category, to simulate pre-existing
    # data from before the categories table existed.
    set_category(coffee_id, "Legacy Category", db_path)

    init_db(db_path)  # re-run init_db, as happens on every app startup

    assert "Legacy Category" in get_categories(db_path)
