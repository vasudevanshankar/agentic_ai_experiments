"""Transaction storage: inserting imported rows and querying them back."""
import hashlib
from pathlib import Path
from typing import Optional

import pandas as pd

from wealth_os.db import get_connection


def compute_dedup_hash(date: str, description: str, amount: float, account: str) -> str:
    """Stable fingerprint used to silently skip re-imported duplicate rows."""
    key = f"{date}|{description}|{amount:.2f}|{account}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def insert_transactions(
    df: pd.DataFrame, account: str, db_path: Optional[Path] = None
) -> tuple[int, int]:
    """Insert normalized transactions (expects date, description, amount columns).

    Returns (inserted_count, skipped_duplicate_count).
    """
    inserted = 0
    skipped = 0
    with get_connection(db_path) as conn:
        for row in df.itertuples(index=False):
            date_str = row.date.strftime("%Y-%m-%d")
            dedup_hash = compute_dedup_hash(date_str, row.description, row.amount, account)
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO transactions (date, description, amount, account, dedup_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date_str, row.description, row.amount, account, dedup_hash),
            )
            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
    return inserted, skipped


def get_all_transactions(db_path: Optional[Path] = None) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        return pd.read_sql_query(
            "SELECT id, date, description, amount, account, category "
            "FROM transactions ORDER BY date DESC",
            conn,
        )


def count_transactions(db_path: Optional[Path] = None) -> int:
    with get_connection(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]


def get_distinct_accounts(db_path: Optional[Path] = None) -> list[str]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT DISTINCT account FROM transactions ORDER BY account").fetchall()
    return [row[0] for row in rows]


def flip_account_sign(account: str, db_path: Optional[Path] = None) -> int:
    """Invert the amount sign for every transaction on one account.

    Use this to correct an account that was imported with the wrong sign
    convention (expenses positive instead of negative, or vice versa) instead
    of re-importing. Recomputes each row's dedup hash to match its new sign,
    so future imports of the same account still detect duplicates correctly.

    Returns the number of transactions updated.
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, date, description, amount FROM transactions WHERE account = ?",
            (account,),
        ).fetchall()
        for tx_id, date_str, description, amount in rows:
            new_amount = -amount
            new_hash = compute_dedup_hash(date_str, description, new_amount, account)
            conn.execute(
                "UPDATE transactions SET amount = ?, dedup_hash = ? WHERE id = ?",
                (new_amount, new_hash, tx_id),
            )
    return len(rows)
