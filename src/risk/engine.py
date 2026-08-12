"""組裝完整 Risk 日頻框架（TX 主序列）。"""

from __future__ import annotations

import pandas as pd

from .groups import apply_group_scores
from .indicators import enrich_risk_indicators
from .position import apply_exposure
from .score import aggregate_risk


def _merge_on_day(left: pd.DataFrame, right: pd.DataFrame, cols: list[str] | None = None) -> pd.DataFrame:
    if right is None or right.empty:
        return left
    l = left.copy()
    r = right.copy()
    l["_day"] = pd.to_datetime(l["date"]).dt.tz_localize(None).dt.normalize().dt.date
    r["_day"] = pd.to_datetime(r["date"]).dt.tz_localize(None).dt.normalize().dt.date
    use_cols = cols or [c for c in r.columns if c not in ("date",)]
    use_cols = [c for c in use_cols if c in r.columns]
    r2 = r[["_day"] + use_cols].drop_duplicates("_day")
    overlap = [c for c in use_cols if c in l.columns]
    if overlap:
        l = l.drop(columns=overlap)
    return l.merge(r2, on="_day", how="left").drop(columns=["_day"])


def build_risk_frame(
    daily: pd.DataFrame,
    breadth: pd.DataFrame | None = None,
    external: pd.DataFrame | None = None,
    chip: pd.DataFrame | None = None,
    include_external: bool = True,
    include_chip: bool = True,
) -> pd.DataFrame:
    df = enrich_risk_indicators(daily)
    df = _merge_on_day(
        df,
        breadth,
        ["up", "down", "unchanged", "limit_up", "limit_down", "ad_ratio", "breadth_pct"],
    )

    if "up" in df.columns and "down" in df.columns:
        frac = df["up"] / (df["up"] + df["down"]).replace(0, pd.NA) * 100
        df["breadth_pct_day"] = frac
        df["breadth20"] = frac.rolling(20, min_periods=5).mean()
    else:
        df["breadth_pct_day"] = pd.NA
        df["breadth20"] = pd.NA

    ext_cols = [
        "nasdaq",
        "sox",
        "spx",
        "kospi",
        "samsung",
        "hynix",
        "nikkei",
        "tsm_adr",
    ]
    df = _merge_on_day(df, external, ext_cols)
    for col in ["nasdaq", "sox", "samsung", "hynix"]:
        if col not in df.columns:
            df[col] = pd.NA
        df[f"{col}_ret5"] = pd.to_numeric(df[col], errors="coerce").pct_change(5) * 100

    chip_cols = None
    if chip is not None and not chip.empty:
        chip_cols = [c for c in chip.columns if c != "date"]
        df = _merge_on_day(df, chip, chip_cols)

    df = apply_group_scores(df, include_external=include_external, include_chip=include_chip)
    df = aggregate_risk(df, include_external=include_external, include_chip=include_chip)
    df = apply_exposure(df)

    high = pd.to_numeric(df["high"], errors="coerce")
    ma20 = pd.to_numeric(df["ma20"], errors="coerce")
    df["high_ma20_dev"] = (high - ma20) / ma20 * 100
    return df
