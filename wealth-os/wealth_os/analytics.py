"""Spending analytics: aggregations over a transactions DataFrame.

Pure functions over an in-memory DataFrame (not the database), so they're
easy to unit test and reusable across pages (e.g. net worth, projections).
"""
import pandas as pd


def monthly_category_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Total spend (expenses only) by month and category.

    Returns columns: month ("YYYY-MM"), category, spend (positive dollars).
    """
    expenses = df[df["amount"] < 0].copy()
    if len(expenses) == 0:
        return pd.DataFrame(columns=["month", "category", "spend"])
    expenses["spend"] = -expenses["amount"]
    expenses["month"] = pd.to_datetime(expenses["date"]).dt.to_period("M").astype(str)
    result = expenses.groupby(["month", "category"], as_index=False)["spend"].sum()
    return result.sort_values(["month", "spend"], ascending=[True, False])


def category_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Total spend (expenses only) by category, highest first."""
    expenses = df[df["amount"] < 0].copy()
    if len(expenses) == 0:
        return pd.DataFrame(columns=["category", "spend"])
    expenses["spend"] = -expenses["amount"]
    result = expenses.groupby("category", as_index=False)["spend"].sum()
    return result.sort_values("spend", ascending=False)
