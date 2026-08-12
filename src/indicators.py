"""均線、乖離、MACD、KD、價量等技術指標。"""

import numpy as np
import pandas as pd

MA_WINDOWS = (20, 60, 120, 240)


def add_moving_averages(df: pd.DataFrame, windows: tuple[int, ...] = MA_WINDOWS) -> pd.DataFrame:
    out = df.copy()
    close = out["close"]
    for w in windows:
        out[f"ma{w}"] = close.rolling(w, min_periods=w).mean()
    return out


def add_ma_deviation(df: pd.DataFrame, windows: tuple[int, ...] = MA_WINDOWS) -> pd.DataFrame:
    out = df.copy()
    for w in windows:
        ma = out[f"ma{w}"]
        out[f"dev{w}"] = (out["close"] - ma) / ma * 100
        out[f"dev{w}_pctile"] = out[f"dev{w}"].expanding(min_periods=max(w, 60)).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100,
            raw=False,
        )
    return out


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    out = df.copy()
    ema_fast = out["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = out["close"].ewm(span=slow, adjust=False).mean()
    out["macd"] = ema_fast - ema_slow
    out["macd_signal"] = out["macd"].ewm(span=signal, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    return out


def add_kd(df: pd.DataFrame, n: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
    out = df.copy()
    low_n = out["low"].rolling(n, min_periods=n).min()
    high_n = out["high"].rolling(n, min_periods=n).max()
    rsv = (out["close"] - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    out["k"] = rsv.ewm(alpha=1 / k_smooth, adjust=False).mean()
    out["d"] = out["k"].ewm(alpha=1 / d_smooth, adjust=False).mean()
    return out


def add_volume_stats(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    out = df.copy()
    out["vol_ma"] = out["volume"].rolling(window, min_periods=window).mean()
    out["vol_ratio"] = out["volume"] / out["vol_ma"]
    return out


def enrich_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """一次加上均線、乖離、MACD、KD、成交量統計。"""
    out = add_moving_averages(df)
    out = add_ma_deviation(out)
    out = add_macd(out)
    out = add_kd(out)
    out = add_volume_stats(out)
    out["ma20_slope_5"] = out["ma20"].pct_change(5) * 100
    out["high_20"] = out["high"].rolling(20, min_periods=20).max()
    out["low_20"] = out["low"].rolling(20, min_periods=20).min()
    return out


def trend_state(row: pd.Series) -> str:
    """大多頭：收盤 > 20 > 60 > 120 > 240。"""
    needed = ["close", "ma20", "ma60", "ma120", "ma240"]
    if any(pd.isna(row.get(c)) for c in needed):
        return "資料不足"
    close, ma20, ma60, ma120, ma240 = (float(row[c]) for c in needed)
    if close > ma20 > ma60 > ma120 > ma240:
        return "大多頭排列"
    if close < ma20 < ma60 < ma120 < ma240:
        return "空頭排列"
    if close > ma20:
        return "短多、結構未齊"
    return "短線轉弱"


def heat_label(dev20: float | None, dev60: float | None) -> str:
    if dev20 is None or dev60 is None or pd.isna(dev20) or pd.isna(dev60):
        return "—"
    if dev20 >= 10 or dev60 >= 18:
        return "極端"
    if dev20 >= 8 or dev60 >= 15:
        return "過熱"
    if dev20 >= 5 or dev60 >= 10:
        return "強勢"
    if dev20 >= 0:
        return "正常多頭"
    return "低於均線"
