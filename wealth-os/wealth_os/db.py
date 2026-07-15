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
