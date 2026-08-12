"""上市上漲／下跌家數（TWSE 大盤統計）。"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime

import pandas as pd
import requests

from .config import CACHE_DIR

TWSE_MI_INDEX = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
HEADERS = {"User-Agent": "Mozilla/5.0"}
CACHE_FILE = CACHE_DIR / "twse_breadth.csv"
# 雲端冷啟動若缺整段歷史，一次補太多會超過 Render 逾時；優先補最近 N 日
BREADTH_MAX_BACKFILL = int(os.getenv("BREADTH_MAX_BACKFILL", "40"))


def _parse_count_limit(text: str) -> tuple[int, int]:
    text = str(text).replace(",", "").strip()
    match = re.match(r"(\d+)(?:\((\d+)\))?", text)
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2) or 0)


def _parse_int(text: str) -> int:
    text = str(text).replace(",", "").strip()
    return int(text) if text.isdigit() else 0


def _as_day(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.tz_localize(None).dt.normalize()


def fetch_twse_breadth(date: datetime | pd.Timestamp, retries: int = 3) -> dict | None:
    """抓取單一交易日上市漲跌家數。"""
    date_str = pd.Timestamp(date).strftime("%Y%m%d")
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(
                TWSE_MI_INDEX,
                params={"response": "json", "date": date_str, "type": "MS"},
                headers=HEADERS,
                timeout=20,
            )
            if resp.status_code != 200:
                last_error = resp.status_code
                time.sleep(0.4 * (attempt + 1))
                continue
            payload = resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
            continue

        if payload.get("stat") != "OK":
            return None

        table = None
        for item in payload.get("tables") or []:
            if item.get("title") == "漲跌證券數合計":
                table = item
                break
        if not table:
            return None

        rows = {str(r[0]): r for r in table.get("data") or [] if r}
        up_row = rows.get("上漲(漲停)")
        down_row = rows.get("下跌(跌停)")
        flat_row = rows.get("持平")
        if not up_row or not down_row:
            return None

        up, limit_up = _parse_count_limit(up_row[2])
        down, limit_down = _parse_count_limit(down_row[2])
        unchanged = _parse_int(flat_row[2]) if flat_row else 0
        total = up + down + unchanged
        return {
            "date": pd.Timestamp(date).tz_localize(None).normalize(),
            "up": up,
            "down": down,
            "unchanged": unchanged,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "ad_ratio": up / (up + down) if (up + down) else None,
            "breadth_pct": up / total * 100 if total else None,
        }

    return None if last_error is None else None


def load_breadth_history(trading_dates: pd.Series, sleep_s: float = 0.15) -> pd.DataFrame:
    """
    依台指期交易日載入上市廣度，並寫入本地快取。
    僅補齊快取中缺少的日期。
    """
    dates = _as_day(pd.Series(list(pd.Index(pd.Series(trading_dates).dropna().unique()))))
    dates = dates.sort_values().tolist()

    cached = pd.DataFrame()
    if CACHE_FILE.exists():
        cached = pd.read_csv(CACHE_FILE)
        cached["date"] = _as_day(cached["date"])

    have = set(cached["date"]) if not cached.empty else set()
    missing = [d for d in dates if d not in have]
    if len(missing) > BREADTH_MAX_BACKFILL:
        missing = missing[-BREADTH_MAX_BACKFILL:]
    rows = []
    for date in missing:
        row = fetch_twse_breadth(date)
        if row:
            rows.append(row)
        time.sleep(sleep_s)

    if rows:
        new_df = pd.DataFrame(rows)
        new_df["date"] = _as_day(new_df["date"])
        cached = pd.concat([cached, new_df], ignore_index=True) if not cached.empty else new_df
        cached = cached.drop_duplicates(subset=["date"]).sort_values("date")
        cached.to_csv(CACHE_FILE, index=False)

    empty_cols = ["date", "up", "down", "unchanged", "limit_up", "limit_down", "ad_ratio", "breadth_pct"]
    if cached.empty:
        return pd.DataFrame(columns=empty_cols)

    wanted = set(dates)
    return cached[cached["date"].isin(wanted)].sort_values("date").reset_index(drop=True)
