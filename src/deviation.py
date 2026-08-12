"""當天最高（含夜盤）對 MA20（月線）的乖離率。"""

import pandas as pd

from .config import DEVIATION_THRESHOLD

MA20_WINDOW = 20


def compute_deviation(high_price: float, ma20: float) -> float:
    """
    乖離率（%）= (當天最高含夜盤 - MA20) / MA20 × 100
    """
    if ma20 == 0:
        raise ValueError("MA20 不可為零")
    return (high_price - ma20) / ma20 * 100


def add_ma20(daily: pd.DataFrame) -> pd.Series:
    """含夜盤日K收盤的 20 日簡單均線（與券商「月線」同一算法）。"""
    close = pd.to_numeric(daily["close"], errors="coerce")
    return close.rolling(MA20_WINDOW, min_periods=MA20_WINDOW).mean()


def compute_deviation_series(daily: pd.DataFrame, monthly: pd.DataFrame | None = None) -> pd.DataFrame:
    """每個交易日：當天最高（含夜盤）vs 當日 MA20。"""
    empty_cols = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "daily_high",
        "ma20",
        "monthly_close",
        "deviation_pct",
        "abs_deviation_pct",
    ]
    if daily.empty:
        return pd.DataFrame(columns=empty_cols)

    ma20 = add_ma20(daily)
    records = []
    for idx, row in daily.iterrows():
        ma_val = ma20.loc[idx]
        if pd.isna(ma_val) or pd.isna(row.get("high")):
            continue
        high = float(row["high"])
        ma_close = float(ma_val)
        dev = compute_deviation(high, ma_close)
        records.append(
            {
                "date": row["date"],
                "open": float(row["open"]) if pd.notna(row.get("open")) else None,
                "high": high,
                "low": float(row["low"]) if pd.notna(row.get("low")) else None,
                "close": float(row["close"]) if pd.notna(row.get("close")) else None,
                "daily_high": high,
                "ma20": ma_close,
                "monthly_close": ma_close,
                "deviation_pct": dev,
                "abs_deviation_pct": abs(dev),
            }
        )
    return pd.DataFrame(records)


def latest_ma20(daily: pd.DataFrame, last_price: float | None = None) -> float | None:
    """最新 MA20；盤中可把最後一根收盤換成即時價。"""
    if daily.empty:
        return None
    closes = pd.to_numeric(daily["close"], errors="coerce").dropna()
    if len(closes) < MA20_WINDOW:
        return None
    values = closes.iloc[-MA20_WINDOW:].astype(float).tolist()
    if last_price is not None:
        values[-1] = float(last_price)
    return float(sum(values) / MA20_WINDOW)


def latest_month_close(daily: pd.DataFrame) -> float | None:
    """相容舊名稱：回傳最新 MA20。"""
    return latest_ma20(daily)


def latest_high_including_realtime(daily_high: float, quote) -> float:
    """歷史日K最高，再與即時價／即時最高取 max（涵蓋尚未寫入日K的夜盤）。"""
    candidates = [daily_high]
    if quote is None:
        return daily_high
    for value in (getattr(quote, "high", None), getattr(quote, "price", None)):
        if value is not None:
            candidates.append(float(value))
    return max(candidates)


def is_alert_triggered(deviation_pct: float, threshold: float = DEVIATION_THRESHOLD) -> bool:
    return abs(deviation_pct) > threshold


def alert_message(
    high_price: float,
    ma20: float,
    deviation_pct: float,
    threshold: float = DEVIATION_THRESHOLD,
) -> str:
    direction = "高於" if deviation_pct > 0 else "低於"
    return (
        f"⚠️ 乖離率警示：當日最高（含夜盤）{high_price:,.0f} {direction}MA20 {ma20:,.0f}，"
        f"乖離率 {deviation_pct:+.2f}%（門檻 ±{threshold}%）"
    )
