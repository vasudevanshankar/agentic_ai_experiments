"""Category taxonomy: the canonical list of category names used by rules
and transactions.

Kept as a first-class table (rather than just free text on transactions) so
renaming or deleting a category is one action instead of a manual find-and-replace.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from wealth_os.db import get_connection


def add_category(name: str, db_path: Optional[Path] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))


def get_categories(db_path: Optional[Path] = None) -> list[str]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
    return [row[0] for row in rows]


def get_category_usage(db_path: Optional[Path] = None) -> pd.DataFrame:
    """Each category alongside how many transactions currently use it."""
    with get_connection(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT c.name AS category, COUNT(t.id) AS transaction_count
            FROM categories c
            LEFT JOIN transactions t ON t.category = c.name
            GROUP BY c.name
            ORDER BY c.name
            """,
            conn,
        )


def rename_category(old_name: str, new_name: str, db_path: Optional[Path] = None) -> None:
    """Rename a category, cascading to every transaction and rule using it.

    If new_name already exists, old_name is merged into it instead of
    raising a uniqueness error.
    """
    if old_name == new_name or not new_name:
        return
    with get_connection(db_path) as conn:
        target_exists = conn.execute(
            "SELECT 1 FROM categories WHERE name = ?", (new_name,)
        ).fetchone()
        if target_exists:
            conn.execute("DELETE FROM categories WHERE name = ?", (old_name,))
        else:
            conn.execute("UPDATE categories SET name = ? WHERE name = ?", (new_name, old_name))
        conn.execute("UPDATE transactions SET category = ? WHERE category = ?", (new_name, old_name))
        conn.execute("UPDATE rules SET category = ? WHERE category = ?", (new_name, old_name))


def delete_category(name: str, db_path: Optional[Path] = None) -> None:
    """Delete a category. Transactions using it revert to uncategorized.

    Rules referencing this category are left alone; they simply won't match
    to a currently-managed category until edited or re-pointed.
    """
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM categories WHERE name = ?", (name,))
        conn.execute("UPDATE transactions SET category = NULL WHERE category = ?", (name,))
