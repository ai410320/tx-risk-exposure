"""籌碼：上市三大法人現貨買賣超 + 台指期／臺指選法人留倉。

資料來源（FinMind，免費層可用）：
- TaiwanStockTotalInstitutionalInvestors
- TaiwanFuturesInstitutionalInvestors (TX)
- TaiwanOptionInstitutionalInvestors (TXO)
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from .config import CACHE_DIR, FINMIND_API_URL, FINMIND_TOKEN
from .risk.constants import PCR_EXTREME, PCR_HIGH, PCR_LOW

CACHE_FILE = CACHE_DIR / "chip_daily.csv"
_CACHE_TTL = 300
_mem: tuple[float, pd.DataFrame] | None = None

SPOT_NAMES = {
    "Foreign_Investor": "foreign",
    "Investment_Trust": "trust",
    "Dealer_self": "dealer_self",
    "Dealer_Hedging": "dealer_hedge",
    "total": "total",
}
FUT_NAMES = {"外資": "foreign", "投信": "trust", "自營商": "dealer"}


def _finmind(dataset: str, start: str, end: str, data_id: str | None = None) -> pd.DataFrame:
    params = {
        "dataset": dataset,
        "start_date": start,
        "end_date": end,
    }
    if data_id:
        params["data_id"] = data_id
    if FINMIND_TOKEN:
        params["token"] = FINMIND_TOKEN
    resp = requests.get(FINMIND_API_URL, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind {dataset}: {payload.get('msg', payload)}")
    data = payload.get("data") or []
    return pd.DataFrame(data) if data else pd.DataFrame()


def _pivot_spot(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df["buy"] = pd.to_numeric(df["buy"], errors="coerce").fillna(0)
    df["sell"] = pd.to_numeric(df["sell"], errors="coerce").fillna(0)
    df["net"] = df["buy"] - df["sell"]
    rows = []
    for day, g in df.groupby("date"):
        item = {"date": day}
        by = {str(r["name"]): float(r["net"]) for _, r in g.iterrows()}
        for src, key in SPOT_NAMES.items():
            item[f"spot_{key}_net"] = by.get(src, 0.0)
        # 自營合計（自行買賣＋避險）
        item["spot_dealer_net"] = item.get("spot_dealer_self_net", 0.0) + item.get("spot_dealer_hedge_net", 0.0)
        rows.append(item)
    out = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    # 轉成「億元」方便閱讀
    for c in [c for c in out.columns if c.startswith("spot_") and c.endswith("_net")]:
        out[c] = out[c] / 1e8
    return out


def _pivot_futures(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    for c in (
        "long_deal_volume",
        "short_deal_volume",
        "long_open_interest_balance_volume",
        "short_open_interest_balance_volume",
    ):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    rows = []
    for day, g in df.groupby("date"):
        item = {"date": day}
        for _, r in g.iterrows():
            key = FUT_NAMES.get(str(r["institutional_investors"]))
            if not key:
                continue
            deal_net = float(r["long_deal_volume"]) - float(r["short_deal_volume"])
            oi_net = float(r["long_open_interest_balance_volume"]) - float(
                r["short_open_interest_balance_volume"]
            )
            item[f"fut_{key}_deal_net"] = deal_net
            item[f"fut_{key}_oi_net"] = oi_net
            item[f"fut_{key}_oi_long"] = float(r["long_open_interest_balance_volume"])
            item[f"fut_{key}_oi_short"] = float(r["short_open_interest_balance_volume"])
        rows.append(item)
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _pivot_options(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    for c in (
        "long_deal_volume",
        "short_deal_volume",
        "long_open_interest_balance_volume",
        "short_open_interest_balance_volume",
    ):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    rows = []
    for day, g in df.groupby("date"):
        item = {"date": day}
        for _, r in g.iterrows():
            who = FUT_NAMES.get(str(r["institutional_investors"]))
            if not who:
                continue
            cp = str(r["call_put"])
            side = "call" if "買" in cp else "put" if "賣" in cp else None
            if not side:
                continue
            # 淨買權／賣權留倉：多方 OI - 空方 OI
            oi_net = float(r["long_open_interest_balance_volume"]) - float(
                r["short_open_interest_balance_volume"]
            )
            deal_net = float(r["long_deal_volume"]) - float(r["short_deal_volume"])
            item[f"opt_{who}_{side}_oi_net"] = oi_net
            item[f"opt_{who}_{side}_deal_net"] = deal_net
            item[f"opt_{who}_{side}_oi_long"] = float(r["long_open_interest_balance_volume"])
            item[f"opt_{who}_{side}_oi_short"] = float(r["short_open_interest_balance_volume"])
        rows.append(item)
    out = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    # 外資 PCR（賣權多方 OI / 買權多方 OI），偏高＝偏避險／恐慌
    if "opt_foreign_put_oi_long" in out.columns and "opt_foreign_call_oi_long" in out.columns:
        call_l = out["opt_foreign_call_oi_long"].replace(0, pd.NA)
        out["opt_foreign_pcr"] = out["opt_foreign_put_oi_long"] / call_l
    return out


def _enrich_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out

    for col in ("spot_foreign_net", "spot_trust_net", "spot_dealer_net", "spot_total_net"):
        if col in out.columns:
            out[f"{col}_5d"] = out[col].rolling(5, min_periods=1).sum()

    if "fut_foreign_oi_net" in out.columns:
        out["fut_foreign_oi_chg"] = out["fut_foreign_oi_net"].diff()

    # 籌碼判讀標籤（給 UI，不直接等於下單）
    labels = []
    biases = []  # -2..+2
    for _, r in out.iterrows():
        f_spot = r.get("spot_foreign_net")
        f_oi_chg = r.get("fut_foreign_oi_chg")
        f_deal = r.get("fut_foreign_deal_net")
        trust = r.get("spot_trust_net")
        pcr = r.get("opt_foreign_pcr")

        score = 0
        bits = []
        if pd.notna(f_spot):
            if f_spot >= 50:
                score += 1
                bits.append("外資現貨大買")
            elif f_spot <= -50:
                score -= 1
                bits.append("外資現貨大賣")
        if pd.notna(f_oi_chg):
            if f_oi_chg >= 1500:
                score += 1
                bits.append("外資期貨淨多增")
            elif f_oi_chg <= -1500:
                score -= 1
                bits.append("外資期貨淨空增")
        if pd.notna(f_spot) and pd.notna(f_oi_chg):
            if f_spot > 0 and f_oi_chg < -1000:
                bits.append("現貨買／期貨空→偏避險")
                score -= 0.5
            elif f_spot < 0 and f_oi_chg > 1000:
                bits.append("現貨賣／期貨多→可能回補或對沖")
        if pd.notna(trust):
            if trust >= 20:
                score += 0.5
                bits.append("投信買超")
            elif trust <= -20:
                score -= 0.5
                bits.append("投信賣超")
        if pd.notna(pcr):
            if pcr >= PCR_EXTREME:
                bits.append(f"選擇權 PCR 極端≥{PCR_EXTREME:.2f}（≈P90）")
            elif pcr >= PCR_HIGH:
                bits.append(f"選擇權 PCR 偏高≥{PCR_HIGH:.2f}（≈P80）")
            elif pcr <= PCR_LOW:
                bits.append(f"選擇權 PCR 偏低≤{PCR_LOW:.2f}（≈P20）")

        if score >= 1.5:
            bias = 2
            tone = "偏多確認"
        elif score >= 0.5:
            bias = 1
            tone = "偏多"
        elif score <= -1.5:
            bias = -2
            tone = "偏空確認"
        elif score <= -0.5:
            bias = -1
            tone = "偏空"
        else:
            bias = 0
            tone = "中性／雜訊"
        label = tone if not bits else f"{tone}｜" + "；".join(bits[:3])
        labels.append(label)
        biases.append(int(bias) if bias == int(bias) else bias)
    out["chip_label"] = labels
    out["chip_bias"] = biases
    return out


def fetch_chip_history(lookback_days: int = 500) -> pd.DataFrame:
    """抓取並合併籌碼日頻表（含特徵）。有記憶體／檔案快取。"""
    global _mem
    now = time.time()
    if _mem and now - _mem[0] < _CACHE_TTL:
        return _mem[1].copy()

    end = datetime.now()
    start = end - timedelta(days=max(lookback_days, 120))
    start_s, end_s = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    try:
        spot = _pivot_spot(_finmind("TaiwanStockTotalInstitutionalInvestors", start_s, end_s))
        fut = _pivot_futures(_finmind("TaiwanFuturesInstitutionalInvestors", start_s, end_s, "TX"))
        opt = _pivot_options(_finmind("TaiwanOptionInstitutionalInvestors", start_s, end_s, "TXO"))
    except Exception:
        # 離線／失敗時退回檔案快取
        if CACHE_FILE.exists():
            cached = pd.read_csv(CACHE_FILE, parse_dates=["date"])
            _mem = (now, cached)
            return cached.copy()
        return pd.DataFrame()

    frames = [f for f in (spot, fut, opt) if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()

    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="date", how="outer")
    out = out.sort_values("date").reset_index(drop=True)
    out = _enrich_features(out)

    try:
        out.to_csv(CACHE_FILE, index=False)
    except OSError:
        pass
    _mem = (now, out.copy())
    return out


def chip_snapshot(row: pd.Series | None) -> dict:
    """單列摘要給前端卡片。"""
    if row is None or (isinstance(row, pd.Series) and row.empty):
        return {}

    def g(key, digits=1):
        v = row.get(key)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return round(float(v), digits)

    return {
        "date": str(pd.Timestamp(row["date"]).date()) if "date" in row.index else None,
        "spot_foreign_net": g("spot_foreign_net"),
        "spot_trust_net": g("spot_trust_net"),
        "spot_dealer_net": g("spot_dealer_net"),
        "spot_total_net": g("spot_total_net"),
        "spot_foreign_net_5d": g("spot_foreign_net_5d"),
        "fut_foreign_deal_net": g("fut_foreign_deal_net", 0),
        "fut_foreign_oi_net": g("fut_foreign_oi_net", 0),
        "fut_foreign_oi_chg": g("fut_foreign_oi_chg", 0),
        "opt_foreign_pcr": g("opt_foreign_pcr", 2),
        "opt_foreign_call_oi_net": g("opt_foreign_call_oi_net", 0),
        "opt_foreign_put_oi_net": g("opt_foreign_put_oi_net", 0),
        "chip_bias": float(row["chip_bias"]) if pd.notna(row.get("chip_bias")) else 0,
        "chip_label": str(row.get("chip_label") or ""),
    }
