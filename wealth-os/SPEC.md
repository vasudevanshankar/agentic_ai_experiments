# Wealth OS — Specification

## How to use this document

This file is the source of truth for what Wealth OS currently does. It is written to
be precise enough that implementing everything described here, in the stack specified,
reproduces this application's behavior — the same spec should always produce the same
app.

To add new functionality: append a new feature section following the template in
[§11](#11-how-to-add-a-new-feature-to-this-spec) with `Status: Proposed`, hand this file
to your engineering copilot, and flip the status to `Implemented` once it's built and
tested.

Do not record personal data (real account names, real category lists, real balances)
in this file — it describes mechanics only, so it stays safe to eventually open source.

---

## 1. Vision & scope

A local-first personal finance and wealth planning app. Import bank transactions,
categorize spending, understand it visually, and (eventually) track net worth and
project long-term wealth — entirely on the user's machine, no cloud, no accounts.

## 2. Tech stack & environment

| Concern | Choice |
|---|---|
| Language | Python, pinned to **3.10** via `.python-version` |
| UI | Streamlit (multipage app) |
| Storage | SQLite, single file at `data/wealth_os.db` |
| Data wrangling | pandas |
| Charts | Plotly (`plotly.express`) |
| Tests | pytest |

**Why Python is pinned to 3.10, not the newest available:** `pyarrow` (used internally
by both `pandas.read_sql_query` and Streamlit's `st.data_editor`) segfaults
intermittently on Python 3.14 when both code paths hit its native allocator across
Streamlit reruns — confirmed via `faulthandler` C-stack traces, reproduced 8/8 times on
3.14, 0/many on 3.10. This is a load-bearing environment constraint, not a style
preference — do not upgrade the Python version without re-verifying this class of crash
is gone (see §9 testing policy for how to check).

Dependencies are unpinned in `requirements.txt` (acceptable for a single-developer
local app at this stage; revisit if this becomes multi-contributor).

## 3. Project structure

```
wealth-os/
├── app.py                        # Home page: connection status, transaction count
├── pages/
│   ├── 1_Import_Transactions.py  # CSV import + sign-convention fix
│   ├── 2_Categorize.py           # Category management, rules, transaction editing
│   └── 3_Analytics.py            # Spending dashboard
├── wealth_os/                    # Application package — all logic, no UI code
│   ├── config.py                 # Paths and constants
│   ├── db.py                     # Schema, connection handling, init/migration
│   ├── transactions.py           # Insert, query, dedup, sign correction
│   ├── categorization.py         # Rule engine
│   ├── categories.py             # Category taxonomy CRUD
│   └── analytics.py              # Pure aggregation functions
├── tests/                        # One test file per wealth_os module
├── data/                         # SQLite db lives here — git-ignored, never committed
├── .python-version                # Pins 3.10 (see §2)
├── requirements.txt
└── SPEC.md                       # This file
```

## 4. Data model

```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,              -- ISO format YYYY-MM-DD
    description TEXT NOT NULL,
    amount REAL NOT NULL,            -- negative = expense/outflow, positive = income/inflow
    account TEXT NOT NULL,
    category TEXT,                   -- NULL = uncategorized. Never store "Uncategorized" literally.
    dedup_hash TEXT NOT NULL UNIQUE, -- sha256(f"{date}|{description}|{amount:.2f}|{account}")
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,           -- case-insensitive substring matched against description
    category TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,  -- lower number = checked first
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
```

## 5. Conventions & invariants

These rules are enforced by convention in application code, not by database
constraints (except where noted) — any new feature must respect them:

1. **Sign convention:** `amount < 0` is an expense/outflow, `amount > 0` is
   income/inflow. Respected everywhere spend/income is computed or displayed.
2. **`category IS NULL` means uncategorized.** UI layers translate `NULL` to the
   display string `"Uncategorized"`, but must convert it back to `NULL` before writing
   — the literal string `"Uncategorized"` must never be persisted to the `category`
   column.
3. **Dedup hash** is `sha256(f"{date}|{description}|{amount:.2f}|{account}")`, enforced
   via a `UNIQUE` constraint and `INSERT OR IGNORE`. Any code that mutates a
   transaction's `amount`, `description`, `date`, or `account` **must** recompute and
   update `dedup_hash`, or future duplicate detection silently breaks. Reference
   implementation: `flip_account_sign()`.
4. **All DB access goes through `wealth_os/db.py::get_connection()`**, a context
   manager that commits on success and always closes. Every data-layer function takes
   an optional `db_path: Optional[Path] = None` — defaults to the real app database,
   but tests pass a `tmp_path` to run against an isolated, throwaway database.
5. **`init_db()` is idempotent** (`CREATE TABLE IF NOT EXISTS`) and is called at the
   top of every page. It also runs a one-time-per-call backfill that seeds `categories`
   from any category strings already present in `transactions`/`rules` — this must be
   preserved so schema changes never silently drop in-use categories from the managed
   list.
6. **Rule matching:** case-insensitive substring (`pattern.lower() in
   description.lower()`), first match wins, evaluated in ascending `priority` order
   (ties broken by `id` ascending, i.e. insertion order).
7. **`apply_rules()` only ever writes rows where `category IS NULL`.** It must never
   overwrite an existing category — this is what makes manual edits and rule
   application safe to run in any order, any number of times.
8. **`rename_category(old, new)`:** if `new` already exists, `old` is merged into it
   (old row deleted, all references repointed) rather than raising a uniqueness error.
9. **`delete_category(name)`:** deletes the category row and sets `category = NULL` on
   every transaction using it. Rules referencing the deleted name are left untouched
   (not cascaded) — they simply won't point at a currently-managed category until
   edited.

## 6. Module reference

**`wealth_os/config.py`**
- `PROJECT_ROOT`, `DATA_DIR`, `DB_PATH`, `APP_TITLE` — path and constant definitions.

**`wealth_os/db.py`**
- `get_connection(db_path=None)` → context manager yielding a `sqlite3.Connection`.
- `init_db(db_path=None) -> None` — creates tables if missing, backfills categories.

**`wealth_os/transactions.py`**
- `compute_dedup_hash(date, description, amount, account) -> str`
- `insert_transactions(df, account, db_path=None) -> tuple[inserted: int, skipped: int]`
- `get_all_transactions(db_path=None) -> DataFrame[id, date, description, amount, account, category]`
- `count_transactions(db_path=None) -> int`
- `get_distinct_accounts(db_path=None) -> list[str]`
- `flip_account_sign(account, db_path=None) -> int` — rows updated

**`wealth_os/categorization.py`**
- `add_rule(pattern, category, priority=100, db_path=None) -> None` — also registers `category`
- `get_rules(db_path=None) -> DataFrame[id, pattern, category, priority]`
- `delete_rule(rule_id, db_path=None) -> None`
- `apply_rules(db_path=None) -> int` — count of transactions newly categorized
- `set_category(transaction_id, category: Optional[str], db_path=None) -> None`

**`wealth_os/categories.py`**
- `add_category(name, db_path=None) -> None`
- `get_categories(db_path=None) -> list[str]`
- `get_category_usage(db_path=None) -> DataFrame[category, transaction_count]`
- `rename_category(old_name, new_name, db_path=None) -> None`
- `delete_category(name, db_path=None) -> None`

**`wealth_os/analytics.py`**
- `monthly_category_totals(df) -> DataFrame[month, category, spend]` — expenses only, `spend` positive
- `category_breakdown(df) -> DataFrame[category, spend]` — expenses only, sorted descending

## 7. Features

| ID | Feature | Status | Page |
|---|---|---|---|
| F1 | CSV Import | Implemented | `pages/1_Import_Transactions.py` |
| F2 | Sign Convention Correction | Implemented | `pages/1_Import_Transactions.py` |
| F3 | Rule-Based Categorization | Implemented | `pages/2_Categorize.py` |
| F4 | Category Management | Implemented | `pages/2_Categorize.py` |
| F5 | Spending Analytics Dashboard | Implemented | `pages/3_Analytics.py` |
| F6 | Manual Asset/Liability Tracking & Net Worth | Implemented | `pages/4_Net_Worth.py` |

### F1: CSV Import
**Status:** Implemented
**Page:** `pages/1_Import_Transactions.py` ("Import Transactions")
**Purpose:** Bring bank/card CSV exports into the `transactions` table without
maintaining bank-specific parsers.
**Behavior:**
- User uploads a CSV; the first 10 rows are previewed.
- User maps which uploaded column is Date / Description / Amount via three
  selectboxes.
- User enters a free-text account name (required before previewing).
- Optional "Flip amount sign" checkbox negates every parsed amount, for exports where
  expenses come through positive.
- On preview: date parsed via `pd.to_datetime(errors="coerce")`, amount via
  `pd.to_numeric(errors="coerce")`; rows where either fails are dropped and counted in
  a warning; the first 20 valid rows are shown.
- On save: `insert_transactions(df, account)` then `apply_rules()` run automatically;
  the result reports inserted count, skipped-duplicate count, and auto-categorized
  count.
**Files:** `pages/1_Import_Transactions.py`, `wealth_os/transactions.py::insert_transactions`,
`wealth_os/categorization.py::apply_rules`

### F2: Sign Convention Correction
**Status:** Implemented
**Page:** `pages/1_Import_Transactions.py`, "Fix sign convention" section
**Purpose:** Correct an account imported with the wrong sign convention without
re-importing or losing existing categorization.
**Behavior:**
- Account selectbox populated from `get_distinct_accounts()`.
- Button flips the sign of every transaction for that account via
  `flip_account_sign()`, which recomputes each row's `dedup_hash` to match its new
  sign (see invariant §5.3).
- Idempotent by design: clicking twice restores the original sign.
**Files:** `pages/1_Import_Transactions.py`, `wealth_os/transactions.py::flip_account_sign`

### F3: Rule-Based Categorization
**Status:** Implemented
**Page:** `pages/2_Categorize.py`, "Rules" section
**Purpose:** Automatically assign categories to transactions by description text,
without per-transaction manual work.
**Behavior:**
- Rules table shown sorted by `priority` ascending, then `id` ascending.
- Add rule: pattern (text), category (text — auto-registers as a category if new),
  priority (int, default 100, step 10).
- Delete rule via a selectbox of existing rule IDs.
- "Apply rules to uncategorized transactions" runs `apply_rules()` (see invariant §5.6–5.7).
- Also invoked automatically after every successful CSV import (F1).
**Files:** `pages/2_Categorize.py`, `wealth_os/categorization.py`

### F4: Category Management
**Status:** Implemented
**Page:** `pages/2_Categorize.py`, "Categories" and "Transactions" sections
**Purpose:** Maintain a first-class, editable list of category names, and allow any
transaction's category to be corrected — not just uncategorized ones.
**Behavior:**
- Categories table shown with live usage counts (`LEFT JOIN`, so zero-usage categories
  still appear with count 0).
- Add: free-text name, no-op if it already exists.
- Rename: cascades to every transaction and rule using the old name; merges into the
  target if the new name already exists (invariant §5.8).
- Delete: removes the category and reverts affected transactions to `NULL`; existing
  rules referencing it are left as-is (invariant §5.9).
- Transaction editor: "Show only uncategorized" toggle (default on) switches between
  just `NULL`-category rows and the full transaction list. Category is edited via a
  constrained dropdown (`SelectboxColumn`, options = `["Uncategorized"] +
  get_categories()`) — free text is not accepted, so every transaction's category is
  guaranteed to exist in the `categories` table. "Save categories" diffs edited rows
  against the original and writes only changed rows.
**Files:** `pages/2_Categorize.py`, `wealth_os/categories.py`,
`wealth_os/categorization.py::set_category`

### F5: Spending Analytics Dashboard
**Status:** Implemented
**Page:** `pages/3_Analytics.py` ("Spending Analytics")
**Purpose:** See categorized spending by period, sliced by account/category/description,
with a choice of chart type.
**Behavior:**
- Period selector (radio): **Month** | **Year to date** | **All time**.
  - Month: second selectbox lists every distinct month present in the data (most
    recent first, formatted "June 2026"); period = that calendar month.
  - Year to date: Jan 1 of the latest transaction's year through the latest
    transaction's date.
  - All time: full range of data present.
- Filters on top of the period: Account (multiselect), Category (multiselect, `NULL`
  shown as "Uncategorized"), Description contains (case-insensitive substring). Empty
  selection = no filtering on that dimension.
- KPI row: Spend, Income, Net, Transaction count — computed over the filtered,
  period-scoped set.
- Monthly spend-by-category stacked bar chart: shown only when period is "Year to
  date" or "All time" (a single month would render one meaningless bar).
- Category breakdown chart: chart-type radio (**Bar** | **Pie**) toggles between
  `px.bar` and `px.pie`, both driven by `analytics.category_breakdown()` (expenses
  only).
- Transaction table: filtered rows, sorted by date descending, sortable by any column
  via the native Streamlit dataframe UI.
**Files:** `pages/3_Analytics.py`, `wealth_os/analytics.py`

### F6: Manual Asset/Liability Tracking & Net Worth
**Status:** Implemented
**Page:** `pages/4_Net_Worth.py` ("Net Worth")
**Purpose:** Track what the user owns and owes, entered manually (no bank/broker API,
per §9), and show current net worth plus how it's trended over time.

**Data model:**
```sql
CREATE TABLE net_worth_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL CHECK (type IN ('asset', 'liability')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE net_worth_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES net_worth_items(id) ON DELETE CASCADE,
    date TEXT NOT NULL,   -- ISO format YYYY-MM-DD
    value REAL NOT NULL,  -- always stored positive; type determines +/- effect on net worth
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(item_id, date)
);
```

**Behavior:**
- **Sign convention is different from `transactions` and scoped only to this feature:**
  `value` is always entered and stored as a positive number (e.g. a mortgage balance
  of $310,000 is stored as `310000`, not `-310000`). Whether it adds to or subtracts
  from net worth is determined entirely by the item's `type`.
- Manage items: add a new item (name + type: Asset/Liability). Deleting an item
  cascades (`ON DELETE CASCADE`) to delete all of its snapshots — net worth *history*
  before the deletion will recompute without that item's past contribution. This is a
  deliberate simplification (no soft-delete/archiving in v1); call this out if it ever
  needs to change.
- No rename in this version — delete and re-add if a name needs to change. (Small
  scope decision to keep this step focused; can be added later like category rename.)
- Record a balance: pick an existing item, enter a value and a date (default today),
  save. This is an **upsert** keyed on `(item_id, date)` — recording again for the same
  item on the same day updates that day's value rather than creating a duplicate row,
  but recording on a new day always adds a new history point.
- Current net worth: for each item, use its most recent snapshot with
  `date <= today` (items with no snapshot yet contribute nothing). Total assets = sum
  of asset items' latest values; total liabilities = sum of liability items' latest
  values; net worth = assets − liabilities. Shown as KPI tiles plus a per-item
  breakdown table/chart.
- Net worth over time (history chart): take every distinct snapshot date across all
  items, sorted ascending. At each such date, forward-fill each item's value using its
  most recent snapshot at or before that date (0 before an item's first snapshot), then
  compute net worth the same way as "current net worth." Plot as a line chart. This is
  the precise algorithm — any reimplementation must forward-fill per item, not just
  plot raw snapshot values, or the trend line will show artificial drops whenever only
  one item happens to get updated on a given date.

**Files:** `pages/4_Net_Worth.py` (new), `wealth_os/net_worth.py` (new), `wealth_os/db.py`
(schema addition)

**Tests:**
- `add_item` / `get_items` round-trip
- `delete_item` cascades and removes its snapshots
- `record_balance` upserts on `(item_id, date)` — same-day re-entry updates, not duplicates
- `get_latest_balances` correctly forward-fills as of a given date
- `get_current_net_worth` sums assets minus liabilities using latest values only
- `get_net_worth_history` forward-fills correctly across items with staggered,
  non-overlapping snapshot dates (the case most likely to be implemented wrong)

## 8. Planned, not yet implemented

Carried over from the original v1 roadmap — these are in scope for this project, just
not built yet:

- Investment exposure summary
- Income assumptions input
- 10/15/20-year wealth projection with simple scenarios

## 9. Non-goals (deliberately out of scope for v1)

- Bank API / broker integrations
- Multi-user support
- Mobile app
- Cloud sync
- AI-generated financial advice
- Complex tax optimization
- Monte Carlo simulation
- Production deployment

## 10. Testing policy

- Every data-mutating function in `wealth_os/*.py` accepts an optional `db_path` so
  tests run against an isolated `tmp_path` database, never the real one.
- New behavior ships with tests colocated in `tests/`, one file per `wealth_os` module.
- Minimum invariants that must stay covered: dedup hash stability/uniqueness,
  duplicate-skip on re-import, `apply_rules` never overwrites an existing category,
  first-matching-rule priority ordering, sign-flip recomputes the dedup hash, category
  rename cascade + merge, category delete reverts transactions to `NULL`, categories
  backfill on `init_db()`.
- Run: `python -m pytest tests/ -v` from `wealth-os/` with the venv active.
- **Before treating a Streamlit page as verified, run it through
  `streamlit.testing.v1.AppTest`** — it actually executes the script, unlike `curl`,
  which only fetches the static shell and will not catch runtime exceptions. Run at
  least 3 reruns plus any relevant widget interactions (forms, `data_editor` edits,
  radios) before considering a page change safe — this project hit a real intermittent
  native crash (§2) that only reproduced this way.

## 11. How to add a new feature to this spec

Copy this template, fill it in, set `Status: Proposed`, and add a row to the feature
table in §7:

```
### F<N>: <Feature Name>
**Status:** Proposed
**Page:** <file path> ("<page title>")
**Purpose:** <why this exists, one or two sentences>
**Behavior:**
- <precise, unambiguous rule — avoid "smart", "automatically figures out", etc.>
- <precise, unambiguous rule>
**Files:** <files expected to change>
**Tests:** <new invariants that must be covered>
```

Once implemented and its tests pass, flip `Status` to `Implemented` in both the
section header and the §7 table.
