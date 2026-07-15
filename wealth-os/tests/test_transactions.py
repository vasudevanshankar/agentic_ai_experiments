"""Tests for transaction dedup and insert logic."""
import pandas as pd

from wealth_os.db import init_db
from wealth_os.transactions import (
    compute_dedup_hash,
    count_transactions,
    flip_account_sign,
    get_all_transactions,
    insert_transactions,
)


def test_compute_dedup_hash_is_stable():
    h1 = compute_dedup_hash("2026-01-01", "Coffee Shop", -4.50, "Checking")
    h2 = compute_dedup_hash("2026-01-01", "Coffee Shop", -4.50, "Checking")
    assert h1 == h2


def test_compute_dedup_hash_differs_by_amount():
    h1 = compute_dedup_hash("2026-01-01", "Coffee Shop", -4.50, "Checking")
    h2 = compute_dedup_hash("2026-01-01", "Coffee Shop", -5.00, "Checking")
    assert h1 != h2


def test_insert_transactions_skips_duplicates(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "description": ["Coffee Shop", "Grocery Store"],
            "amount": [-4.50, -62.10],
        }
    )

    inserted, skipped = insert_transactions(df, "Checking", db_path)
    assert inserted == 2
    assert skipped == 0

    inserted_again, skipped_again = insert_transactions(df, "Checking", db_path)
    assert inserted_again == 0
    assert skipped_again == 2

    assert count_transactions(db_path) == 2


def test_flip_account_sign_inverts_only_that_account(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    backwards = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "description": ["Coffee Shop", "Paycheck"],
            "amount": [20.0, -3000.0],  # wrong: expense positive, income negative
        }
    )
    insert_transactions(backwards, "Revolut", db_path)

    correct = pd.DataFrame({"date": pd.to_datetime(["2026-01-01"]), "description": ["Rent"], "amount": [-1500.0]})
    insert_transactions(correct, "Checking", db_path)

    flipped = flip_account_sign("Revolut", db_path)
    assert flipped == 2

    tx = get_all_transactions(db_path)
    revolut_amounts = dict(zip(tx[tx["account"] == "Revolut"]["description"], tx[tx["account"] == "Revolut"]["amount"]))
    assert revolut_amounts["Coffee Shop"] == -20.0
    assert revolut_amounts["Paycheck"] == 3000.0

    checking_amount = tx[tx["account"] == "Checking"]["amount"].iloc[0]
    assert checking_amount == -1500.0  # untouched


def test_flip_account_sign_recomputes_dedup_hash(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)

    backwards = pd.DataFrame({"date": pd.to_datetime(["2026-01-01"]), "description": ["Coffee Shop"], "amount": [20.0]})
    insert_transactions(backwards, "Revolut", db_path)
    flip_account_sign("Revolut", db_path)

    # Re-importing with the now-correct sign should be recognized as a duplicate.
    corrected = pd.DataFrame({"date": pd.to_datetime(["2026-01-01"]), "description": ["Coffee Shop"], "amount": [-20.0]})
    inserted, skipped = insert_transactions(corrected, "Revolut", db_path)
    assert inserted == 0
    assert skipped == 1
