"""簡化回測：訊號 t 收盤 → 曝險用於 t+1 報酬。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestSummary:
    start: str
    end: str
    cagr_bh: float
    cagr_strat: float
    mdd_bh: float
    mdd_strat: float
    sharpe_bh: float
    sharpe_strat: float
    end_mult_bh: float
    end_mult_strat: float


def _stats(rets: pd.Series) -> tuple[float, float, float, float]:
    rets = rets.dropna()
    if rets.empty:
        return float("nan"), float("nan"), float("nan"), float("nan")
    eq = (1 + rets).cumprod()
    dd = eq / eq.cummax() - 1
    years = max(len(rets) / 252, 1e-9)
    cagr = float(eq.iloc[-1] ** (1 / years) - 1)
    vol = float(rets.std() * np.sqrt(252))
    sharpe = float(rets.mean() * 252 / vol) if vol else float("nan")
    return cagr, float(dd.min()), sharpe, float(eq.iloc[-1])


def run_exposure_backtest(frame: pd.DataFrame, start: str, end: str) -> tuple[pd.DataFrame, BacktestSummary]:
    """
    frame 需含 date, close, exposure。
    報酬近似：close-to-close（無開盤價時的務實近似；正式應改 t+1 open）。
    """
    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df[(df["date"] >= start) & (df["date"] <= end)].sort_values("date").reset_index(drop=True)
    df["ret"] = pd.to_numeric(df["close"], errors="coerce").pct_change()
    df["strat_ret"] = df["exposure"].shift(1) * df["ret"]
    df["bh_equity"] = (1 + df["ret"].fillna(0)).cumprod()
    df["strat_equity"] = (1 + df["strat_ret"].fillna(0)).cumprod()

    cagr_bh, mdd_bh, sharpe_bh, end_bh = _stats(df["ret"])
    cagr_s, mdd_s, sharpe_s, end_s = _stats(df["strat_ret"])
    summary = BacktestSummary(
        start=start,
        end=end,
        cagr_bh=cagr_bh,
        cagr_strat=cagr_s,
        mdd_bh=mdd_bh,
        mdd_strat=mdd_s,
        sharpe_bh=sharpe_bh,
        sharpe_strat=sharpe_s,
        end_mult_bh=end_bh,
        end_mult_strat=end_s,
    )
    return df, summary
