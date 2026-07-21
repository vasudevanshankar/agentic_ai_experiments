"""SQLite connection handling for Wealth OS.

All database access should go through get_connection() so the data
directory and connection settings stay consistent in one place.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from wealth_os.config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    category TEXT,
    dedup_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    category TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS net_worth_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL CHECK (type IN ('asset', 'liability')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS net_worth_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES net_worth_items(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    value REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(item_id, date)
);
"""


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection(db_path: Optional[Path] = None):
    """Yield a SQLite connection, committing on success and always closing.

    db_path defaults to the app's real database; tests pass a tmp_path to
    run against an isolated throwaway database instead.
    """
    path = db_path or DB_PATH
    if path == DB_PATH:
        ensure_data_dir()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Create tables if they don't already exist. Safe to call on every startup."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        _backfill_categories(conn)


def _backfill_categories(conn: sqlite3.Connection) -> None:
    """Populate the categories table from any category strings already in use.

    The categories table was added after transactions/rules already stored
    free-text category names, so this keeps existing data's categories from
    silently disappearing from the managed list on upgrade.
    """
    used_categories = set()
    for row in conn.execute("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL"):
        used_categories.add(row[0])
    for row in conn.execute("SELECT DISTINCT category FROM rules"):
        used_categories.add(row[0])
    for name in used_categories:
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
