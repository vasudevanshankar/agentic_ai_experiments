"""Manual asset/liability tracking and net worth calculation.

Values are always stored positive; whether an item adds to or subtracts from
net worth is determined by its type ('asset' or 'liability'). This is a
separate convention from transactions.amount — see SPEC.md F6.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from wealth_os.db import get_connection

_SIGN = {"asset": 1, "liability": -1}


def add_item(name: str, type: str, db_path: Optional[Path] = None) -> None:
    if type not in _SIGN:
        raise ValueError("type must be 'asset' or 'liability'")
    with get_connection(db_path) as conn:
        conn.execute("INSERT INTO net_worth_items (name, type) VALUES (?, ?)", (name, type))


def get_items(db_path: Optional[Path] = None) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        return pd.read_sql_query(
            "SELECT id, name, type FROM net_worth_items ORDER BY type, name", conn
        )


def delete_item(item_id: int, db_path: Optional[Path] = None) -> None:
    """Delete an item and, via ON DELETE CASCADE, all of its balance history."""
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM net_worth_items WHERE id = ?", (item_id,))


def record_balance(item_id: int, date: str, value: float, db_path: Optional[Path] = None) -> None:
    """Upsert a balance snapshot for one item on one date."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO net_worth_snapshots (item_id, date, value)
            VALUES (?, ?, ?)
            ON CONFLICT(item_id, date) DO UPDATE SET value = excluded.value
            """,
            (item_id, date, value),
        )


def get_latest_balances(as_of: Optional[str] = None, db_path: Optional[Path] = None) -> pd.DataFrame:
    """Each item's most recent snapshot with date <= as_of (default today).

    Items with no qualifying snapshot yet appear with value = NaN.
    """
    as_of = as_of or pd.Timestamp.today().strftime("%Y-%m-%d")
    with get_connection(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT i.id AS item_id, i.name, i.type, s.date, s.value
            FROM net_worth_items i
            LEFT JOIN net_worth_snapshots s
                ON s.item_id = i.id
                AND s.date = (
                    SELECT MAX(date) FROM net_worth_snapshots
                    WHERE item_id = i.id AND date <= ?
                )
            ORDER BY i.type, i.name
            """,
            conn,
            params=(as_of,),
        )


def get_current_net_worth(db_path: Optional[Path] = None) -> dict:
    balances = get_latest_balances(db_path=db_path)
    balances["value"] = pd.to_numeric(balances["value"], errors="coerce").fillna(0)
    assets = balances.loc[balances["type"] == "asset", "value"].sum()
    liabilities = balances.loc[balances["type"] == "liability", "value"].sum()
    return {"assets": assets, "liabilities": liabilities, "net_worth": assets - liabilities}


def get_net_worth_history(db_path: Optional[Path] = None) -> pd.DataFrame:
    """Net worth at every distinct snapshot date, forward-filling each item's value.

    At each date, an item contributes its most recent value at or before that
    date (0 before its first snapshot) — never just the raw value recorded on
    that exact date, or the trend would show artificial drops whenever only
    one item happens to get updated on a given day.
    """
    with get_connection(db_path) as conn:
        items = pd.read_sql_query("SELECT id, type FROM net_worth_items", conn)
        snapshots = pd.read_sql_query(
            "SELECT item_id, date, value FROM net_worth_snapshots ORDER BY date", conn
        )

    if len(items) == 0 or len(snapshots) == 0:
        return pd.DataFrame(columns=["date", "net_worth"])

    dates = sorted(snapshots["date"].unique())
    pivot = snapshots.pivot_table(index="date", columns="item_id", values="value", aggfunc="last")
    pivot = pivot.reindex(dates).ffill().fillna(0)

    sign = items.set_index("id")["type"].map(_SIGN)
    contributions = pivot.reindex(columns=sign.index, fill_value=0) * sign
    net_worth = contributions.sum(axis=1)

    return pd.DataFrame({"date": net_worth.index, "net_worth": net_worth.values})
