# Wealth OS

A local-first personal finance and wealth planning app. Import bank transactions,
track net worth, understand investment exposure, and project long-term wealth —
entirely on your own machine, with no financial data ever leaving it.

## Status

🚧 Early development (v1 in progress). Current capability: project scaffold only.

## Why local-first

Your transaction data, balances, and holdings never leave your filesystem. There is
no cloud sync, no account, no server. The SQLite database lives in `data/`, which is
git-ignored so personal financial data never enters version control.

## Setup

```bash
cd wealth-os
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501. On first run it creates `data/wealth_os.db`.

## Project layout

```
wealth-os/
├── app.py           # Streamlit entry point (UI only)
├── wealth_os/        # Application package — data access, business logic
├── data/             # Local SQLite database (git-ignored, never committed)
├── tests/
└── requirements.txt
```

## Roadmap

- [x] Project scaffold
- [ ] CSV import for bank transactions
- [ ] Rule-based categorization
- [ ] Spending dashboard with drill-down
- [ ] Manual asset/liability tracking and net worth view
- [ ] Investment exposure summary
- [ ] 10/15/20-year wealth projection

Deliberately not building (yet): bank/broker API integrations, multi-user support,
mobile app, cloud sync, AI-generated financial advice, tax optimization, Monte Carlo
simulation.
