"""Central configuration for file paths and app-wide constants."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "wealth_os.db"

APP_TITLE = "Wealth OS"
