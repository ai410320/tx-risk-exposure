"""外部市場：Nasdaq、SOX、S&P500、KOSPI、三星、海力士、日經、台積電 ADR。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

EXTERNAL_SYMBOLS = {
    "nasdaq": "^IXIC",
    "sox": "^SOX",
    "spx": "^GSPC",
    "kospi": "^KS11",
    "samsung": "005930.KS",
    "hynix": "000660.KS",
    "nikkei": "^N225",
    "tsm_adr": "TSM",
}

DISPLAY_NAMES = {
    "nasdaq": "Nasdaq",
    "sox": "SOX 費半",
    "spx": "S&P 500",
    "kospi": "KOSPI",
    "samsung": "Samsung",
    "hynix": "SK Hynix",
    "nikkei": "Nikkei",
    "tsm_adr": "台積電 ADR",
}

_SYMBOL_TO_KEY = {sym: key for key, sym in EXTERNAL_SYMBOLS.items()}

_FETCH_TTL = 120
_fetch_cache: dict[int, tuple[float, pd.DataFrame]] = {}


def _close_series(frame: pd.DataFrame) -> pd.Series:
    close = frame["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.astype(float)


def fetch_external_history(lookback_days: int = 500) -> pd.DataFrame:
    """下載外部指數／指標股日收，日期為交易所當地日（無時區）。

    注意：yfinance 的 end 為「不含當日」，若傳今天會拿不到亞洲盤當日列。
    因此 end 用明天，讓已收盤／盤中可得的當日 K 能進來；美股若尚未收盤則仍停在前一日。
    """
    cache_key = int(lookback_days)
    now_ts = time.time()
    hit = _fetch_cache.get(cache_key)
    if hit and now_ts - hit[0] < _FETCH_TTL:
        return hit[1].copy()

    now = datetime.now()
    start = now - timedelta(days=max(lookback_days, 60))
    # yfinance end 為 exclusive → +1 day 才含「今天」
    end = now + timedelta(days=1)
    start_s = start.strftime("%Y-%m-%d")
    end_s = end.strftime("%Y-%m-%d")
    symbols = list(EXTERNAL_SYMBOLS.values())
    frames = []

    try:
        # 一次下載多標的，雲端冷啟動比逐檔串行快很多
        raw = yf.download(
            symbols,
            start=start_s,
            end=end_s,
            progress=False,
            auto_adjust=True,
            threads=True,
            group_by="ticker",
        )
        if not raw.empty and isinstance(raw.columns, pd.MultiIndex):
            for sym in symbols:
                if sym not in raw.columns.get_level_values(0):
                    continue
                try:
                    close = raw[sym]["Close"].dropna()
                except Exception:
                    continue
                if close.empty:
                    continue
                series = close.astype(float).copy()
                series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
                series.name = _SYMBOL_TO_KEY[sym]
                frames.append(series)
    except Exception:
        frames = []

    if not frames:
        for key, symbol in EXTERNAL_SYMBOLS.items():
            try:
                hist = yf.download(
                    symbol,
                    start=start_s,
                    end=end_s,
                    progress=False,
                    auto_adjust=True,
                    threads=False,
                )
            except Exception:
                continue
            if hist.empty:
                continue
            close = _close_series(hist)
            series = close.copy()
            series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
            series.name = key
            frames.append(series)

    if not frames:
        out = pd.DataFrame()
    else:
        out = pd.concat(frames, axis=1).sort_index()
        out = out.reset_index()
        out = out.rename(columns={out.columns[0]: "date"})
        out["date"] = pd.to_datetime(out["date"]).dt.normalize()

    _fetch_cache[cache_key] = (now_ts, out.copy())
    return out

def align_to_tx_dates(external: pd.DataFrame, tx_dates: pd.Series) -> pd.DataFrame:
    """
    將外部市場對齊到台指交易日。
    美股用當日以前最近收盤（盤前／日盤看隔夜）。

    若台指日盤尚未入列（例如盤中尚未結算），但仍有亞股當日資料，
    會把「今天」一併列入，避免外部頁卡在昨天。
    """
    if external.empty:
        return pd.DataFrame({"date": pd.to_datetime(tx_dates).dt.normalize()})

    left = pd.DataFrame({"date": pd.to_datetime(tx_dates).dt.tz_localize(None).dt.normalize().unique()})
    left["date"] = pd.to_datetime(left["date"]).astype("datetime64[ns]")
    left = left.sort_values("date")

    right = external.copy()
    right["date"] = pd.to_datetime(right["date"]).dt.tz_localize(None).dt.normalize().astype("datetime64[ns]")
    right = right.sort_values("date")

    today = pd.Timestamp(datetime.now().date())
    tx_max = left["date"].max() if len(left) else today
    if today > tx_max:
        # 台指日K還沒有今天時，仍保留外部市場今天的列
        left = pd.concat([left, pd.DataFrame({"date": [today]})], ignore_index=True)
        left = left.drop_duplicates("date").sort_values("date")

    merged = pd.merge_asof(left, right, on="date", direction="backward")
    return merged
