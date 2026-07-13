"""SQLite connection handling for Wealth OS.

All database access should go through get_connection() so the data
directory and connection settings stay consistent in one place.
"""
import sqlite3
from contextlib import contextmanager

from wealth_os.config import DATA_DIR, DB_PATH


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    """Yield a SQLite connection, committing on success and always closing."""
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
