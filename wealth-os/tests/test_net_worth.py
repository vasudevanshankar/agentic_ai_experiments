"""Tests for manual asset/liability tracking and net worth calculation."""
from wealth_os.db import init_db
from wealth_os.net_worth import (
    add_item,
    delete_item,
    get_current_net_worth,
    get_items,
    get_latest_balances,
    get_net_worth_history,
    record_balance,
)


def test_add_and_get_items(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    add_item("Checking", "asset", db_path)
    add_item("Mortgage", "liability", db_path)

    items = get_items(db_path)
    assert set(items["name"]) == {"Checking", "Mortgage"}
    assert dict(zip(items["name"], items["type"])) == {
        "Checking": "asset",
        "Mortgage": "liability",
    }


def test_delete_item_cascades_snapshots(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    add_item("Checking", "asset", db_path)
    item_id = int(get_items(db_path).iloc[0]["id"])
    record_balance(item_id, "2026-01-01", 1000, db_path)

    delete_item(item_id, db_path)

    assert len(get_items(db_path)) == 0
    assert len(get_latest_balances(db_path=db_path)) == 0


def test_record_balance_upserts_same_day(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    add_item("Checking", "asset", db_path)
    item_id = int(get_items(db_path).iloc[0]["id"])

    record_balance(item_id, "2026-01-01", 1000, db_path)
    record_balance(item_id, "2026-01-01", 1200, db_path)

    balances = get_latest_balances(as_of="2026-01-01", db_path=db_path)
    assert balances.iloc[0]["value"] == 1200


def test_get_latest_balances_forward_fills_as_of_date(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    add_item("Checking", "asset", db_path)
    item_id = int(get_items(db_path).iloc[0]["id"])

    record_balance(item_id, "2026-01-01", 1000, db_path)
    record_balance(item_id, "2026-02-01", 1500, db_path)

    mid_month = get_latest_balances(as_of="2026-01-15", db_path=db_path)
    assert mid_month.iloc[0]["value"] == 1000

    after_both = get_latest_balances(as_of="2026-03-01", db_path=db_path)
    assert after_both.iloc[0]["value"] == 1500


def test_get_current_net_worth_sums_assets_minus_liabilities(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    add_item("Checking", "asset", db_path)
    add_item("Mortgage", "liability", db_path)
    items = get_items(db_path)
    checking_id = int(items[items["name"] == "Checking"]["id"].iloc[0])
    mortgage_id = int(items[items["name"] == "Mortgage"]["id"].iloc[0])

    record_balance(checking_id, "2026-01-01", 5000, db_path)
    record_balance(mortgage_id, "2026-01-01", 300000, db_path)

    result = get_current_net_worth(db_path)
    assert result["assets"] == 5000
    assert result["liabilities"] == 300000
    assert result["net_worth"] == 5000 - 300000


def test_net_worth_history_forward_fills_across_staggered_dates(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    add_item("Checking", "asset", db_path)
    add_item("Mortgage", "liability", db_path)
    items = get_items(db_path)
    checking_id = int(items[items["name"] == "Checking"]["id"].iloc[0])
    mortgage_id = int(items[items["name"] == "Mortgage"]["id"].iloc[0])

    # Checking updated Jan 1 and Feb 1; Mortgage only updated Jan 15.
    record_balance(checking_id, "2026-01-01", 1000, db_path)
    record_balance(mortgage_id, "2026-01-15", 300000, db_path)
    record_balance(checking_id, "2026-02-01", 2000, db_path)

    history = get_net_worth_history(db_path).set_index("date")["net_worth"]

    # Jan 1: only Checking recorded (1000); Mortgage not yet -> contributes 0.
    assert history["2026-01-01"] == 1000
    # Jan 15: Checking forward-filled at 1000, Mortgage newly 300000.
    assert history["2026-01-15"] == 1000 - 300000
    # Feb 1: Checking updated to 2000, Mortgage forward-filled at 300000.
    assert history["2026-02-01"] == 2000 - 300000
