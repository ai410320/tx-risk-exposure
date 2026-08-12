"""大波段反轉評分：5 層訊號 → 0～11 分。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import DEV_PERCENTILE_ALERT
from .indicators import enrich_indicators, heat_label, trend_state

SIGNAL_LABELS = {
    "sig_dev20_hot": "20MA 乖離進入歷史高位",
    "sig_dev60_hot": "60MA 乖離進入歷史高位",
    "sig_kd_div": "KD 頂背離",
    "sig_macd_shrink": "MACD 柱狀體縮短",
    "sig_vol_climax": "價格爆量但無法創高",
    "sig_break_ma20": "跌破 20MA",
    "sig_ma20_flat": "20MA 開始走平",
    "sig_breadth_weak": "市場廣度惡化",
    "sig_new_high_fade": "新高／強勢家數下降",
    "sig_us_tech_weak": "Nasdaq / SOX 同步轉弱",
    "sig_kr_semi_weak": "韓國半導體同步轉弱",
}


@dataclass
class ScoreSnapshot:
    score: int
    max_score: int
    level: str
    color: str
    action: str
    trend: str
    heat: str
    signals: list[tuple[str, bool]]


def _level_from_score(score: int) -> tuple[str, str, str]:
    if score >= 7:
        return "大波段反轉風險", "🔴", "大幅減碼／出場（曝險降至 0～20%）"
    if score >= 5:
        return "明顯轉弱", "🟠", "多單減碼 50～70%"
    if score >= 3:
        return "開始過熱", "🟡", "多單減碼 20～30%"
    return "正常多頭", "🟢", "繼續持有"


def build_signal_frame(
    daily: pd.DataFrame,
    breadth: pd.DataFrame,
    external: pd.DataFrame,
    percentile_alert: float = DEV_PERCENTILE_ALERT,
) -> pd.DataFrame:
    """依交易日計算全部訊號與轉折分數。"""
    df = enrich_indicators(daily)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()

    if not breadth.empty:
        b = breadth.copy()
        b["date"] = pd.to_datetime(b["date"]).dt.tz_localize(None).dt.normalize()
        df["_day"] = df["date"].dt.date
        b["_day"] = b["date"].dt.date
        df = df.merge(b.drop(columns=["date"]), on="_day", how="left").drop(columns=["_day"])
    else:
        for col in ["up", "down", "unchanged", "limit_up", "limit_down", "ad_ratio", "breadth_pct"]:
            df[col] = pd.NA

    if not external.empty:
        ext = external.copy()
        ext["date"] = pd.to_datetime(ext["date"]).dt.tz_localize(None).dt.normalize()
        df["_day"] = df["date"].dt.date
        ext["_day"] = ext["date"].dt.date
        df = df.merge(ext.drop(columns=["date"]), on="_day", how="left").drop(columns=["_day"])

    for col in ["nasdaq", "sox", "spx", "kospi", "samsung", "hynix", "nikkei", "tsm_adr"]:
        if col not in df.columns:
            df[col] = pd.NA
        else:
            df[f"{col}_ma20"] = df[col].rolling(20, min_periods=20).mean()
            df[f"{col}_ret5"] = df[col].pct_change(5) * 100

    df["tx_ret"] = df["close"].pct_change() * 100
    df["tx_ret5"] = df["close"].pct_change(5) * 100

    # 1) 乖離歷史高位
    df["sig_dev20_hot"] = (df["dev20_pctile"] >= percentile_alert) | (df["dev20"] >= 8)
    df["sig_dev60_hot"] = (df["dev60_pctile"] >= percentile_alert) | (df["dev60"] >= 15)

    # 2) KD 頂背離：近 20 日價格創新高，但 K 值未同步創新高，且收盤仍在高檔
    price_high_20 = df["high"].rolling(20, min_periods=20).max()
    price_high_prev = df["high"].shift(20).rolling(20, min_periods=20).max()
    kd_high_20 = df["k"].rolling(20, min_periods=20).max()
    kd_high_prev = df["k"].shift(20).rolling(20, min_periods=20).max()
    df["sig_kd_div"] = (
        (price_high_20 > price_high_prev)
        & (kd_high_20 <= kd_high_prev * 0.98)
        & (df["close"] >= price_high_20 * 0.97)
    )

    # 3) MACD 柱縮短：今日柱 < 昨日，近期仍有正柱，且收盤仍在高檔
    # 含「開始縮短的第一天」（例如 2026-06-24：柱 100→33），不必等連縮兩天
    hist = df["macd_hist"]
    day_shrink = hist < hist.shift(1)
    recent_positive = (hist > 0) | (hist.shift(1) > 0) | (hist.shift(2) > 0)
    near_high = df["close"] >= df["high_20"] * 0.95
    df["sig_macd_shrink"] = day_shrink & recent_positive & near_high

    # 4) 爆量但無法創高／高檔爆量長黑
    # 台指期量比很少到 1.8（歷史約僅 1%），改以 ≈90 分位 1.35 為爆量門檻
    vol_spike = df["vol_ratio"] >= 1.35
    close_high_20 = df["close"].rolling(20, min_periods=20).max()
    failed_new_close_high = df["close"] < close_high_20.shift(1)
    at_highs = df["close"] >= df["high_20"] * 0.97
    climax_fail = vol_spike & at_highs & failed_new_close_high

    body = (df["open"] - df["close"]).abs()
    range_ = (df["high"] - df["low"]).replace(0, pd.NA)
    long_black = (df["close"] < df["open"]) & (body / range_ >= 0.5) & vol_spike

    # 近 5 日曾在高檔，之後出現爆量收黑＝高檔換手／出貨
    recently_high = df["close"].shift(1).rolling(5, min_periods=3).max() >= df["high_20"].shift(1) * 0.97
    distribution = vol_spike & (df["close"] < df["open"]) & recently_high.fillna(False)

    df["sig_vol_climax"] = (
        climax_fail.fillna(False) | long_black.fillna(False) | distribution.fillna(False)
    )

    # 5) 跌破 20MA、20MA 走平
    df["sig_break_ma20"] = df["close"] < df["ma20"]
    prev_rising = df["ma20"].pct_change(5).shift(5) * 100 > 0.3
    now_flat_or_down = df["ma20_slope_5"] <= 0.15
    df["sig_ma20_flat"] = prev_rising & now_flat_or_down

    # 6) 市場廣度惡化：上漲比偏低，或指數漲、多數股票跌
    ad = df["ad_ratio"]
    index_up_stocks_down = (df["tx_ret"] > 0) & (df["up"] < df["down"])
    ad_weak = ad < 0.4
    ad_fading = (ad < ad.shift(5)) & (df["close"] >= df["high_20"] * 0.98)
    df["sig_breadth_weak"] = ad_weak.fillna(False) | index_up_stocks_down.fillna(False) | ad_fading.fillna(False)

    # 7) 新高／強勢家數下降：指數接近新高，但漲停或上漲家數下滑
    limit_up_fade = (df["limit_up"] < df["limit_up"].shift(5)) & (df["limit_up"].shift(5) > 0)
    up_fade = df["up"] < df["up"].shift(5)
    near_high = df["close"] >= df["high_20"] * 0.98
    df["sig_new_high_fade"] = near_high & (limit_up_fade.fillna(False) | up_fade.fillna(False))

    # 8) Nasdaq + SOX 同步轉弱
    us_down = (df["nasdaq_ret5"] < 0) & (df["sox_ret5"] < 0)
    us_below_ma = (df["nasdaq"] < df["nasdaq_ma20"]) & (df["sox"] < df["sox_ma20"])
    sox_hard = df["sox_ret5"] <= -4
    df["sig_us_tech_weak"] = us_down.fillna(False) | us_below_ma.fillna(False) | sox_hard.fillna(False)

    # 9) 韓國半導體同步轉弱
    kr_index_weak = df["kospi_ret5"] < 0
    kr_names_weak = (df["samsung_ret5"] < 0) & (df["hynix_ret5"] < 0)
    kr_below_ma = (df["samsung"] < df["samsung_ma20"]) & (df["hynix"] < df["hynix_ma20"])
    df["sig_kr_semi_weak"] = (kr_index_weak & kr_names_weak).fillna(False) | kr_below_ma.fillna(False)

    signal_cols = list(SIGNAL_LABELS)
    for col in signal_cols:
        df[col] = df[col].fillna(False).astype(bool)

    df["score"] = df[signal_cols].sum(axis=1).astype(int)
    return df


def snapshot_from_row(row: pd.Series) -> ScoreSnapshot:
    score = int(row.get("score") or 0)
    level, color, action = _level_from_score(score)
    signals = [(SIGNAL_LABELS[key], bool(row.get(key))) for key in SIGNAL_LABELS]
    return ScoreSnapshot(
        score=score,
        max_score=len(SIGNAL_LABELS),
        level=level,
        color=color,
        action=action,
        trend=trend_state(row),
        heat=heat_label(row.get("dev20"), row.get("dev60")),
        signals=signals,
    )


def latest_snapshot(frame: pd.DataFrame) -> ScoreSnapshot:
    if frame.empty:
        raise ValueError("無評分資料")
    return snapshot_from_row(frame.iloc[-1])
