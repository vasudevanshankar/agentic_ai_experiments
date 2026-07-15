"""Tests for spending analytics aggregations."""
import pandas as pd

from wealth_os.analytics import category_breakdown, monthly_category_totals


def _sample_df():
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-05", "2026-01-10", "2026-02-01", "2026-02-15"]),
            "description": ["Coffee", "Groceries", "Rent", "Paycheck"],
            "amount": [-4.5, -60.0, -1500.0, 3000.0],
            "account": ["Checking"] * 4,
            "category": ["Dining", "Groceries", "Housing", "Income"],
        }
    )


def test_category_breakdown_excludes_income_and_sums_expenses():
    result = category_breakdown(_sample_df())
    totals = dict(zip(result["category"], result["spend"]))
    assert totals["Housing"] == 1500.0
    assert totals["Groceries"] == 60.0
    assert totals["Dining"] == 4.5
    assert "Income" not in totals


def test_monthly_category_totals_groups_by_month_and_category():
    result = monthly_category_totals(_sample_df())
    jan_dining = result[(result["month"] == "2026-01") & (result["category"] == "Dining")]["spend"].iloc[0]
    feb_housing = result[(result["month"] == "2026-02") & (result["category"] == "Housing")]["spend"].iloc[0]
    assert jan_dining == 4.5
    assert feb_housing == 1500.0


def test_empty_dataframe_returns_empty_result():
    empty = pd.DataFrame(columns=["date", "description", "amount", "account", "category"])
    assert len(category_breakdown(empty)) == 0
    assert len(monthly_category_totals(empty)) == 0
