"""加權指數（TAIEX / ^TWII）對照序列。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


def fetch_taiex_daily(lookback_days: int = 800, end: str | None = None) -> pd.DataFrame:
    """
    使用 Yahoo ^TWII 作為加權指數代理（對照用，非交易執行主序列）。
    """
    end_dt = datetime.strptime(end, "%Y-%m-%d") if end else datetime.now()
    start_dt = end_dt - timedelta(days=max(lookback_days, 60))
    hist = yf.download(
        "^TWII",
        start=start_dt.strftime("%Y-%m-%d"),
        end=(end_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=False,
    )
    if hist is None or hist.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = [c[0] for c in hist.columns]

    out = hist.reset_index().rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None).dt.normalize()
    cols = ["date", "open", "high", "low", "close", "volume"]
    return out[[c for c in cols if c in out.columns]].dropna(subset=["close"]).reset_index(drop=True)
