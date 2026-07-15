"""Rule-based transaction categorization.

Rules match a case-insensitive substring against a transaction's description.
The first matching rule wins, checked in ascending priority order (lower
number = checked first). apply_rules() only ever fills in transactions with
category IS NULL, so it never overwrites a manual categorization.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from wealth_os.db import get_connection


def add_rule(pattern: str, category: str, priority: int = 100, db_path: Optional[Path] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO rules (pattern, category, priority) VALUES (?, ?, ?)",
            (pattern, category, priority),
        )


def get_rules(db_path: Optional[Path] = None) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        return pd.read_sql_query(
            "SELECT id, pattern, category, priority FROM rules ORDER BY priority ASC, id ASC",
            conn,
        )


def delete_rule(rule_id: int, db_path: Optional[Path] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))


def _match_category(description: str, rules: list[tuple[str, str]]) -> Optional[str]:
    description_lower = description.lower()
    for pattern, category in rules:
        if pattern.lower() in description_lower:
            return category
    return None


def apply_rules(db_path: Optional[Path] = None) -> int:
    """Categorize every transaction with category IS NULL. Returns count updated."""
    with get_connection(db_path) as conn:
        rules = conn.execute(
            "SELECT pattern, category FROM rules ORDER BY priority ASC, id ASC"
        ).fetchall()
        if not rules:
            return 0

        uncategorized = conn.execute(
            "SELECT id, description FROM transactions WHERE category IS NULL"
        ).fetchall()

        updated = 0
        for tx_id, description in uncategorized:
            category = _match_category(description, rules)
            if category is not None:
                conn.execute("UPDATE transactions SET category = ? WHERE id = ?", (category, tx_id))
                updated += 1
    return updated


def set_category(transaction_id: int, category: str, db_path: Optional[Path] = None) -> None:
    """Manually set a single transaction's category (a one-off override)."""
    with get_connection(db_path) as conn:
        conn.execute("UPDATE transactions SET category = ? WHERE id = ?", (category, transaction_id))
