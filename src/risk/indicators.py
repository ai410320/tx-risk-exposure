"""技術指標：僅用 Data[<=t]，供 A–F 評分。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _rolling_pctile(series: pd.Series, window: int, min_periods: int = 120) -> pd.Series:
    return series.rolling(window, min_periods=min_periods).apply(
        lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100,
        raw=False,
    )


def enrich_risk_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """在日K上計算 Risk 系統所需欄位。"""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None).dt.normalize()
    out = out.sort_values("date").reset_index(drop=True)

    c = pd.to_numeric(out["close"], errors="coerce")
    h = pd.to_numeric(out["high"], errors="coerce")
    low = pd.to_numeric(out["low"], errors="coerce")
    v = pd.to_numeric(out["volume"], errors="coerce")

    out["ma20"] = c.rolling(20, min_periods=20).mean()
    out["ma60"] = c.rolling(60, min_periods=60).mean()
    out["ma120"] = c.rolling(120, min_periods=120).mean()
    out["ma240"] = c.rolling(240, min_periods=240).mean()

    out["ma20_slope"] = out["ma20"] / out["ma20"].shift(5) - 1
    out["ma60_slope"] = out["ma60"] / out["ma60"].shift(10) - 1

    out["dev20"] = (c / out["ma20"] - 1) * 100
    out["dev60"] = (c / out["ma60"] - 1) * 100
    out["dev120"] = (c / out["ma120"] - 1) * 100
    out["dev20_pctile"] = _rolling_pctile(out["dev20"], 756)
    out["dev60_pctile"] = _rolling_pctile(out["dev60"], 756)
    out["dev120_pctile"] = _rolling_pctile(out["dev120"], 756)

    # RSI14
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi14"] = 100 - (100 / (1 + rs))

    # KD(9,3,3)
    low_n = low.rolling(9, min_periods=9).min()
    high_n = h.rolling(9, min_periods=9).max()
    rsv = (c - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    out["k"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    out["d"] = out["k"].ewm(alpha=1 / 3, adjust=False).mean()
    out["kd_cross_down"] = (out["k"] < out["d"]) & (out["k"].shift(1) >= out["d"].shift(1))

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    shrink = (out["macd_hist"] < out["macd_hist"].shift(1)).astype(int)
    # consecutive down days
    days = []
    cnt = 0
    for flag in shrink.tolist():
        cnt = cnt + 1 if flag else 0
        days.append(cnt)
    out["hist_down_days"] = days

    out["high_20"] = h.rolling(20, min_periods=20).max()
    out["hist_20_max"] = out["macd_hist"].rolling(20, min_periods=20).max()
    out["k_20_max"] = out["k"].rolling(20, min_periods=20).max()
    out["price_new_high_20"] = h >= out["high_20"] - 1e-9

    out["vol_ma20"] = v.rolling(20, min_periods=20).mean()
    out["vol_ratio"] = v / out["vol_ma20"]
    out["ret1"] = c.pct_change()
    out["vol_ma20_declining"] = out["vol_ma20"] < out["vol_ma20"].shift(5)

    tr = pd.concat([(h - low), (h - c.shift()).abs(), (low - c.shift()).abs()], axis=1).max(axis=1)
    out["atr14"] = tr.rolling(14, min_periods=14).mean()
    out["atr60"] = tr.rolling(60, min_periods=60).mean()
    out["atr_ratio"] = out["atr14"] / c
    out["atr_pctile"] = _rolling_pctile(out["atr_ratio"], 756)
    out["atr_shock"] = out["atr14"] / out["atr60"]

    return out
