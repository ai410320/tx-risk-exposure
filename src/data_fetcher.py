"""從 FinMind 抓取台指期近月日K資料（可含夜盤）。"""

from datetime import datetime, timedelta

import pandas as pd
import requests

from .config import FINMIND_API_URL, FINMIND_TOKEN, FUTURES_ID

_RAW_TTL = 300
_raw_cache: dict[tuple[str, str, str], tuple[float, pd.DataFrame]] = {}


def _fetch_raw(futures_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    import time

    key = (futures_id, start_date, end_date)
    now = time.time()
    hit = _raw_cache.get(key)
    if hit and now - hit[0] < _RAW_TTL:
        return hit[1].copy()

    params = {
        "dataset": "TaiwanFuturesDaily",
        "data_id": futures_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    if FINMIND_TOKEN:
        params["token"] = FINMIND_TOKEN

    resp = requests.get(FINMIND_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind API 錯誤: {payload.get('msg', payload)}")

    data = payload.get("data", [])
    df = pd.DataFrame(data) if data else pd.DataFrame()
    _raw_cache[key] = (now, df)
    return df.copy()


def _near_month_rows(df: pd.DataFrame) -> pd.DataFrame:
    """每個交易日只留近月合約（日盤＋夜盤都保留）。"""
    if df.empty:
        return df

    out = df.copy()
    out["contract_date"] = out["contract_date"].astype(str)
    day = out[out["trading_session"] == "position"]
    if not day.empty:
        near_by_date = day.groupby("date")["contract_date"].min()
        out["_near"] = out["date"].map(near_by_date)
        missing = out["_near"].isna()
        if missing.any():
            out.loc[missing, "_near"] = (
                out.loc[missing].groupby("date")["contract_date"].transform("min")
            )
    else:
        out["_near"] = out.groupby("date")["contract_date"].transform("min")

    out = out[out["contract_date"] == out["_near"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    return out.drop(columns=["_near"])


def _session_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "settlement"])
    renamed = df.rename(columns={"max": "high", "min": "low", "settlement_price": "settlement"})
    return (
        renamed.groupby("date", as_index=False)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            settlement=("settlement", "last") if "settlement" in renamed.columns else ("close", "last"),
        )
        .sort_values("date")
    )


def _combine_day_night(near: pd.DataFrame) -> pd.DataFrame:
    """
    含夜盤日K：
    - 開盤：夜盤開盤（無夜盤則用日盤開盤）
    - 最高／最低：日盤與夜盤取極值
    - 收盤：日盤收盤（無日盤則用夜盤收盤）
    """
    day = _session_ohlc(near[near["trading_session"] == "position"])
    night = _session_ohlc(near[near["trading_session"] == "after_market"])
    if day.empty and night.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "settlement"])

    merged = pd.merge(day, night, on="date", how="outer", suffixes=("_day", "_night")).sort_values("date")

    def _first_valid(day_val, night_val, night_first: bool):
        if night_first:
            return night_val if pd.notna(night_val) else day_val
        return day_val if pd.notna(day_val) else night_val

    rows = []
    for _, row in merged.iterrows():
        high_candidates = [v for v in (row.get("high_day"), row.get("high_night")) if pd.notna(v)]
        low_candidates = [v for v in (row.get("low_day"), row.get("low_night")) if pd.notna(v)]
        vol_day = row.get("volume_day") or 0
        vol_night = row.get("volume_night") or 0
        if pd.isna(vol_day):
            vol_day = 0
        if pd.isna(vol_night):
            vol_night = 0
        rows.append(
            {
                "date": row["date"],
                "open": _first_valid(row.get("open_day"), row.get("open_night"), night_first=True),
                "high": max(high_candidates) if high_candidates else None,
                "low": min(low_candidates) if low_candidates else None,
                "close": _first_valid(row.get("close_day"), row.get("close_night"), night_first=False),
                "volume": float(vol_day) + float(vol_night),
                "settlement": row.get("settlement_day") if pd.notna(row.get("settlement_day")) else row.get("settlement_night"),
                "day_high": row.get("high_day"),
                "night_high": row.get("high_night"),
                "day_close": row.get("close_day"),
            }
        )
    out = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    if "day_close" in out.columns:
        out["day_close"] = pd.to_numeric(out["day_close"], errors="coerce").ffill()
    return out


def _date_range(start_date: str | None, end_date: str | None, lookback_days: int) -> tuple[str, str]:
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if start_date is None:
        start = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=lookback_days)
        start_date = start.strftime("%Y-%m-%d")
    return start_date, end_date


def fetch_daily_bars(
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 400,
    include_night: bool = False,
) -> pd.DataFrame:
    """
    取得台指期近月日K。

    include_night=False：僅日盤（給轉折評分用）
    include_night=True：日盤＋夜盤合成一根日K（給月K乖離用）
    """
    start_date, end_date = _date_range(start_date, end_date, lookback_days)
    raw = _fetch_raw(FUTURES_ID, start_date, end_date)
    near = _near_month_rows(raw)
    if near.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "settlement"])

    if include_night:
        return _combine_day_night(near)

    day = near[near["trading_session"] == "position"].copy()
    day = day[day["settlement_price"] > 0] if "settlement_price" in day.columns else day
    ohlc = _session_ohlc(day)
    return ohlc[["date", "open", "high", "low", "close", "volume", "settlement"]]


def get_latest_close(daily: pd.DataFrame) -> float:
    """取得最新日K收盤價（歷史資料用）。"""
    if daily.empty:
        raise ValueError("無日K資料")
    return float(daily.iloc[-1]["close"])
