"""Tests for transaction dedup and insert logic."""
import pandas as pd

from wealth_os.db import init_db
from wealth_os.transactions import compute_dedup_hash, count_transactions, insert_transactions


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
