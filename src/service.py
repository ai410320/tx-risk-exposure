"""資料組裝（不依賴 Streamlit / FastAPI）。"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .backtest import run_exposure_backtest
from .breadth import load_breadth_history
from .chip import chip_snapshot, fetch_chip_history
from .config import DEV_PERCENTILE_ALERT, REVERSAL_LOOKBACK_DAYS
from .data_fetcher import fetch_daily_bars
from .deviation import (
    compute_deviation,
    compute_deviation_series,
    latest_high_including_realtime,
    latest_ma20,
)
from .external_markets import align_to_tx_dates, fetch_external_history
from .kline import aggregate_monthly, get_current_monthly_price
from .realtime_price import get_realtime_price, session_label
from .risk import build_risk_frame
from .risk.live_alert import build_early_alerts, provisional_live_risk
from .taiex import fetch_taiex_daily

_BUNDLE_TTL = 300
_QUOTE_TTL = 15
_bundle_cache: dict[tuple, tuple[float, tuple]] = {}
_quote_cache: tuple[float, object] | None = None

INCLUDE_EXTERNAL = os.getenv("INCLUDE_EXTERNAL_GROUP", "1") not in ("0", "false", "False")


def load_quote():
    global _quote_cache
    now = time.time()
    if _quote_cache and now - _quote_cache[0] < _QUOTE_TTL:
        return _quote_cache[1]
    quote = get_realtime_price()
    _quote_cache = (now, quote)
    return quote


def load_reversal_bundle(
    lookback: int = REVERSAL_LOOKBACK_DAYS,
    percentile: float = DEV_PERCENTILE_ALERT,
    include_external: bool = INCLUDE_EXTERNAL,
):
    """
    回傳:
      daily, monthly, breadth, external, frame, taiex, taiex_frame, chip
    舊呼叫若只解包前 5 項，請改為:
      daily, monthly, breadth, external, frame, *_ = load_reversal_bundle(...)
    """
    key = (int(lookback), float(percentile), bool(include_external))
    now = time.time()
    hit = _bundle_cache.get(key)
    if hit and now - hit[0] < _BUNDLE_TTL:
        return hit[1]

    daily = fetch_daily_bars(lookback_days=lookback, include_night=False)
    if daily.empty:
        raise RuntimeError("查無台指期資料")

    monthly = aggregate_monthly(daily)
    breadth_dates = daily["date"].tail(min(400, len(daily)))

    def _chip():
        try:
            return fetch_chip_history(lookback_days=lookback)
        except Exception:
            return pd.DataFrame()

    def _taiex():
        try:
            return fetch_taiex_daily(lookback_days=lookback)
        except Exception:
            return pd.DataFrame()

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_breadth = pool.submit(load_breadth_history, breadth_dates)
        f_ext = pool.submit(fetch_external_history, lookback)
        f_chip = pool.submit(_chip)
        f_taiex = pool.submit(_taiex)
        breadth = f_breadth.result()
        external_raw = f_ext.result()
        chip = f_chip.result()
        taiex = f_taiex.result()

    external = align_to_tx_dates(external_raw, daily["date"])
    frame = build_risk_frame(
        daily, breadth, external, chip=chip, include_external=include_external, include_chip=True
    )

    try:
        taiex_frame = (
            build_risk_frame(taiex, breadth, None, chip=chip, include_external=False, include_chip=True)
            if not taiex.empty
            else pd.DataFrame()
        )
    except Exception:
        taiex_frame = pd.DataFrame()

    result = (daily, monthly, breadth, external, frame, taiex, taiex_frame, chip)
    _bundle_cache[key] = (now, result)
    return result

def _series_values(series: pd.Series, kind: str = "float"):
    values = []
    for value in series.tolist():
        if value is None or pd.isna(value):
            values.append(None)
            continue
        if kind == "bool":
            values.append(bool(value))
        elif kind == "int":
            values.append(int(value))
        elif kind == "str":
            values.append(str(value))
        else:
            values.append(float(value))
    return values


def _action_from_exposure(exp: float) -> str:
    if exp >= 0.95:
        return "繼續持有（曝險約 100%）"
    if exp >= 0.85:
        return "輕微減碼（曝險約 90%）"
    if exp >= 0.65:
        return "減碼（曝險約 70%）"
    if exp >= 0.45:
        return "明顯減碼（曝險約 50%）"
    if exp >= 0.20:
        return "大幅減碼（曝險約 25%）"
    return "接近空手（曝險 0～10%）"


def build_dashboard_payload(lookback: int, percentile: float) -> dict:
    daily, monthly, _breadth, _external, frame, _taiex, taiex_frame, chip = load_reversal_bundle(
        lookback, percentile, INCLUDE_EXTERNAL
    )
    quote = load_quote()
    last = frame.iloc[-1]
    last_date = pd.Timestamp(last["date"]).strftime("%Y-%m-%d")
    month_str, _fallback = get_current_monthly_price(daily, monthly)

    night_daily = fetch_daily_bars(lookback_days=lookback, include_night=True)
    month_dev_series = compute_deviation_series(night_daily, monthly)
    last_high = float(night_daily.iloc[-1]["high"]) if not night_daily.empty else quote.price
    today_high = latest_high_including_realtime(last_high, quote)
    ma20 = latest_ma20(night_daily, last_price=quote.price) or float(last.get("ma20") or 0)
    high_ma20_dev = compute_deviation(today_high, ma20) if ma20 else 0.0

    risk = float(last["risk_score"]) if pd.notna(last.get("risk_score")) else 0.0
    exp = float(last["exposure"]) if pd.notna(last.get("exposure")) else 1.0

    early_alerts = build_early_alerts(last)
    live = provisional_live_risk(
        last,
        live_price=float(quote.price),
        live_high=float(quote.high) if quote.high else None,
        live_low=float(quote.low) if quote.low else None,
        live_open=float(quote.open) if quote.open else None,
        include_external=INCLUDE_EXTERNAL,
    )
    live["session"] = quote.session
    live["session_label"] = session_label(quote.session)
    live["quote_time"] = quote.quote_time.strftime("%Y-%m-%d %H:%M:%S") if quote.quote_time else None
    live["source"] = quote.source
    # 若盤中試算已明顯高於收盤 Risk，加一則即時警示
    if live["risk_score"] >= 35 and live["risk_score"] > risk + 3:
        early_alerts = [
            {
                "level": "warn",
                "title": f"盤中試算 Risk 已升至 {live['risk_score']}",
                "detail": f"相對最近收盤 {risk:.1f} 上升中；不必等收盤才減碼。Exposure 試算約 {live['exposure_pct']}%。",
            },
            *early_alerts,
        ]
    if live.get("gap_pct") is not None and live["gap_pct"] <= -2.5:
        early_alerts = [
            {
                "level": "warn",
                "title": f"開盤跳空約 {live['gap_pct']}%",
                "detail": "跳空下行常讓當日 Risk／回撤門檻提早觸發，開盤後就應重估曝險。",
            },
            *early_alerts,
        ]

    chart_cols = {
        "date": "date",
        "open": "float",
        "high": "float",
        "low": "float",
        "close": "float",
        "volume": "float",
        "ma20": "float",
        "ma60": "float",
        "ma120": "float",
        "ma240": "float",
        "ma20_slope": "float",
        "ma60_slope": "float",
        "dev20": "float",
        "dev60": "float",
        "dev20_pctile": "float",
        "dev60_pctile": "float",
        "vol_ma20": "float",
        "vol_ratio": "float",
        "macd": "float",
        "macd_signal": "float",
        "macd_hist": "float",
        "k": "float",
        "d": "float",
        "rsi14": "float",
        "risk_score": "float",
        "raw_score": "float",
        "exposure": "float",
        "exposure_target": "float",
        "score_A": "float",
        "score_B": "float",
        "score_C": "float",
        "score_D": "float",
        "score_E": "float",
        "score_F": "float",
        "score_G": "float",
        "score_H": "float",
        "risk_level": "str",
        "high_ma20_dev": "float",
        "early_cut_B": "bool",
        "drawdown_cut": "bool",
        "dd_from_high20": "float",
        "rebound_stage": "int",
        "washout_recent": "bool",
        "recovery_tier": "int",
        "spot_foreign_net": "float",
        "spot_trust_net": "float",
        "spot_dealer_net": "float",
        "spot_total_net": "float",
        "spot_foreign_net_5d": "float",
        "fut_foreign_deal_net": "float",
        "fut_foreign_oi_net": "float",
        "fut_foreign_oi_chg": "float",
        "opt_foreign_pcr": "float",
        "opt_foreign_call_oi_net": "float",
        "opt_foreign_put_oi_net": "float",
        "chip_bias": "float",
        "chip_label": "str",
        "chip_cap": "float",
        "up": "float",
        "down": "float",
        "unchanged": "float",
        "limit_up": "float",
        "limit_down": "float",
        "ad_ratio": "float",
        "breadth20": "float",
        "nasdaq": "float",
        "sox": "float",
        "spx": "float",
        "kospi": "float",
        "samsung": "float",
        "hynix": "float",
        "nikkei": "float",
        "tsm_adr": "float",
        "nasdaq_ret5": "float",
        "sox_ret5": "float",
        "samsung_ret5": "float",
        "hynix_ret5": "float",
    }

    # aliases for old frontend
    if "vol_ma20" in frame.columns:
        frame = frame.copy()
        frame["vol_ma"] = frame["vol_ma20"]
        frame["score"] = frame["risk_score"]

    chart_cols["vol_ma"] = "float"
    chart_cols["score"] = "float"

    series = {}
    for col, kind in chart_cols.items():
        if col == "date":
            series["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d").tolist()
            continue
        if col not in frame.columns:
            series[col] = [None] * len(frame)
            continue
        series[col] = _series_values(frame[col], kind)

    # 台指日盤尚未結算時，frame 可能停在昨天；把外部市場「當日真實列」補進 series
    series = _append_newer_external_to_series(series, chart_cols, lookback)

    month_dev_out = {
        "date": pd.to_datetime(month_dev_series["date"]).dt.strftime("%Y-%m-%d").tolist()
        if not month_dev_series.empty
        else [],
        "open": _series_values(month_dev_series["open"]) if not month_dev_series.empty else [],
        "high": _series_values(month_dev_series["high"]) if not month_dev_series.empty else [],
        "low": _series_values(month_dev_series["low"]) if not month_dev_series.empty else [],
        "close": _series_values(month_dev_series["close"]) if not month_dev_series.empty else [],
        "daily_high": _series_values(month_dev_series["daily_high"]) if not month_dev_series.empty else [],
        "ma20": _series_values(month_dev_series["ma20"]) if not month_dev_series.empty else [],
        "monthly_close": _series_values(month_dev_series["ma20"]) if not month_dev_series.empty else [],
        "deviation_pct": _series_values(month_dev_series["deviation_pct"]) if not month_dev_series.empty else [],
    }

    groups = {
        "A": {"name": "Trend", "score": float(last.get("score_A") or 0), "cap": 30},
        "B": {"name": "Extension", "score": float(last.get("score_B") or 0), "cap": 20},
        "C": {"name": "Momentum", "score": float(last.get("score_C") or 0), "cap": 15},
        "D": {"name": "PriceVolume", "score": float(last.get("score_D") or 0), "cap": 15},
        "E": {"name": "Breadth", "score": float(last.get("score_E") or 0), "cap": 30},
        "F": {"name": "Volatility", "score": float(last.get("score_F") or 0), "cap": 15},
        "G": {"name": "External", "score": float(last.get("score_G") or 0), "cap": 10},
        "H": {"name": "Chip", "score": float(last.get("score_H") or 0), "cap": 10},
    }

    # quick backtest summary on available frame window
    bt_start = pd.Timestamp(frame["date"].iloc[0]).strftime("%Y-%m-%d")
    bt_end = last_date
    try:
        _, bt_sum = run_exposure_backtest(frame, bt_start, bt_end)
        backtest = {
            "start": bt_sum.start,
            "end": bt_sum.end,
            "cagr_bh": bt_sum.cagr_bh,
            "cagr_strat": bt_sum.cagr_strat,
            "mdd_bh": bt_sum.mdd_bh,
            "mdd_strat": bt_sum.mdd_strat,
            "sharpe_bh": bt_sum.sharpe_bh,
            "sharpe_strat": bt_sum.sharpe_strat,
            "note": "Baseline（未做 Walk-Forward 優化）；報酬為收盤對收盤近似 t+1。",
        }
    except Exception as exc:
        backtest = {"error": str(exc)}

    taiex_last = None
    if taiex_frame is not None and not taiex_frame.empty:
        tr = taiex_frame.iloc[-1]
        taiex_last = {
            "date": pd.Timestamp(tr["date"]).strftime("%Y-%m-%d"),
            "close": float(tr["close"]) if pd.notna(tr.get("close")) else None,
            "risk_score": float(tr["risk_score"]) if pd.notna(tr.get("risk_score")) else None,
            "exposure": float(tr["exposure"]) if pd.notna(tr.get("exposure")) else None,
            "risk_level": str(tr.get("risk_level") or ""),
        }

    return {
        "quote": {
            "price": quote.price,
            "source": quote.source,
            "session": quote.session,
            "session_label": session_label(quote.session),
            "quote_time": quote.quote_time.strftime("%Y-%m-%d %H:%M:%S") if quote.quote_time else None,
            "open": quote.open,
            "high": quote.high,
            "low": quote.low,
            "volume": quote.volume,
        },
        "snapshot": {
            "score": risk,
            "max_score": 100,
            "raw_score": float(last.get("raw_score") or 0),
            "score_denom": float(last.get("score_denom") or 125),
            "level": str(last.get("risk_level") or ""),
            "color": _level_color(str(last.get("risk_level") or "")),
            "action": _action_from_exposure(exp),
            "exposure": exp,
            "exposure_pct": round(exp * 100),
            "early_cut_B": bool(last.get("early_cut_B")),
            "drawdown_cut": bool(last.get("drawdown_cut")),
            "dd_from_high20": float(last["dd_from_high20"])
            if pd.notna(last.get("dd_from_high20"))
            else None,
            "trend": _trend_label(last),
            "heat": _heat_label(last.get("dev20"), last.get("dev60")),
            "signals": [
                {"name": f"{g['name']} {k}", "on": g["score"] > 0, "score": g["score"], "cap": g["cap"]}
                for k, g in groups.items()
            ],
            "groups": groups,
            "last_date": last_date,
            "instrument": "TX",
            "include_external": INCLUDE_EXTERNAL,
            "baseline": True,
        },
        "monthly": {
            "month": month_str,
            "close": ma20,
            "ma20": ma20,
            "today_high": today_high,
            "deviation_pct": high_ma20_dev,
        },
        "taiex": taiex_last,
        "live_risk": live,
        "early_alerts": early_alerts,
        "backtest": backtest,
        "chip": chip_snapshot(last),
        "series": series,
        "monthly_k": {
            "month": monthly["month"].astype(str).tolist() if not monthly.empty else [],
            "open": _series_values(monthly["open"]) if not monthly.empty else [],
            "high": _series_values(monthly["high"]) if not monthly.empty else [],
            "low": _series_values(monthly["low"]) if not monthly.empty else [],
            "close": _series_values(monthly["close"]) if not monthly.empty else [],
        },
        "month_dev_series": month_dev_out,
    }


def _append_newer_external_to_series(series: dict, chart_cols: dict, lookback: int) -> dict:
    """若 yfinance 已有比 series 更晚的外部日期，補上當日真實值（不做 asof 回填）。"""
    from .external_markets import fetch_external_history

    if not series.get("date"):
        return series
    raw = fetch_external_history(lookback_days=lookback)
    if raw is None or raw.empty:
        return series

    last = pd.Timestamp(series["date"][-1])
    ext = raw.copy()
    ext["date"] = pd.to_datetime(ext["date"]).dt.tz_localize(None).dt.normalize()
    newer = ext[ext["date"] > last].sort_values("date")
    if newer.empty:
        return series

    ext_keys = ("nasdaq", "sox", "spx", "kospi", "samsung", "hynix", "nikkei", "tsm_adr")
    n = len(series["date"])
    out = {k: list(v) if isinstance(v, list) else v for k, v in series.items()}
    for _, row in newer.iterrows():
        out["date"].append(pd.Timestamp(row["date"]).strftime("%Y-%m-%d"))
        for col, kind in chart_cols.items():
            if col == "date":
                continue
            if col not in out:
                out[col] = [None] * n
            if col in ext_keys and col in row.index and pd.notna(row[col]):
                out[col].append(float(row[col]))
            else:
                out[col].append(None)
        for key, src in (
            ("nasdaq_ret5", "nasdaq"),
            ("sox_ret5", "sox"),
            ("samsung_ret5", "samsung"),
            ("hynix_ret5", "hynix"),
        ):
            if key not in out:
                continue
            vals = out.get(src, [])
            # 取含 None 的序列中最後 6 個非空
            nonempty = [v for v in vals if v is not None]
            if len(nonempty) >= 6 and nonempty[-6]:
                out[key][-1] = (nonempty[-1] / nonempty[-6] - 1.0) * 100
            else:
                out[key][-1] = None
        n += 1
    return out


def _level_color(level: str) -> str:
    return {
        "LOW": "🟢",
        "NORMAL": "🟢",
        "WARNING": "🟡",
        "HIGH": "🟠",
        "VERY_HIGH": "🔴",
        "EXTREME": "🔴",
    }.get(level, "🟢")


def _trend_label(row: pd.Series) -> str:
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


def _heat_label(dev20, dev60) -> str:
    if dev20 is None or dev60 is None or pd.isna(dev20) or pd.isna(dev60):
        return "—"
    dev20, dev60 = float(dev20), float(dev60)
    if dev20 >= 10 or dev60 >= 18:
        return "極端"
    if dev20 >= 8 or dev60 >= 15:
        return "過熱"
    if dev20 >= 5 or dev60 >= 10:
        return "強勢"
    if dev20 >= 0:
        return "正常多頭"
    return "低於均線"
