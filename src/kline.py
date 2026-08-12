"""月K線聚合。"""

import pandas as pd


def aggregate_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """
    將日K聚合為月K。

    Returns columns: month, open, high, low, close, volume
    """
    if daily.empty:
        return pd.DataFrame(columns=["month", "open", "high", "low", "close", "volume"])

    df = daily.copy()
    df["month"] = df["date"].dt.to_period("M")

    monthly = (
        df.groupby("month", as_index=False)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .sort_values("month")
        .reset_index(drop=True)
    )
    monthly["month"] = monthly["month"].astype(str)
    return monthly


def get_current_monthly_price(daily: pd.DataFrame, monthly: pd.DataFrame) -> tuple[str, float]:
    """取得當月（進行中）月K收盤價。"""
    if monthly.empty:
        raise ValueError("無月K資料")
    latest_month = monthly.iloc[-1]
    return str(latest_month["month"]), float(latest_month["close"])
