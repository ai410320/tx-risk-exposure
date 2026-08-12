import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
FUTURES_ID = "TX"
DEVIATION_THRESHOLD = float(os.getenv("DEVIATION_THRESHOLD", "0.8"))

# 轉折評分：乖離歷史百分位門檻
DEV_PERCENTILE_ALERT = float(os.getenv("DEV_PERCENTILE_ALERT", "90"))
REVERSAL_LOOKBACK_DAYS = int(os.getenv("REVERSAL_LOOKBACK_DAYS", "800"))

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
