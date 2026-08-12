#!/usr/bin/env python3
"""終端機檢查：RiskScore + Exposure + 最高 vs MA20。"""

from src.config import DEVIATION_THRESHOLD, DEV_PERCENTILE_ALERT, REVERSAL_LOOKBACK_DAYS
from src.data_fetcher import fetch_daily_bars
from src.deviation import (
    alert_message,
    compute_deviation,
    is_alert_triggered,
    latest_high_including_realtime,
    latest_ma20,
)
from src.kline import aggregate_monthly, get_current_monthly_price
from src.realtime_price import get_realtime_price, session_label
from src.service import load_reversal_bundle


def main() -> int:
    daily, monthly, _b, _e, frame, _t, _tf, *_ = load_reversal_bundle(
        REVERSAL_LOOKBACK_DAYS, DEV_PERCENTILE_ALERT
    )
    last = frame.iloc[-1]
    quote = get_realtime_price()
    _, fallback = get_current_monthly_price(daily, monthly)
    night = fetch_daily_bars(lookback_days=REVERSAL_LOOKBACK_DAYS, include_night=True)
    last_high = float(night.iloc[-1]["high"]) if not night.empty else quote.price
    today_high = latest_high_including_realtime(last_high, quote)
    ma20 = latest_ma20(night, last_price=quote.price) or fallback
    month_dev = compute_deviation(today_high, ma20)

    risk = float(last["risk_score"])
    exp = float(last["exposure"])
    print("=== TAIEX/TX Turning Point (Baseline) ===")
    print(f"標的: TX 主序列｜日期: {pd_date(last['date'])}")
    print(f"Risk Score: {risk:.1f}/100  [{last['risk_level']}]")
    print(f"Recommended Exposure: {exp*100:.0f}%")
    print(
        f"Groups A–G: "
        f"A{last['score_A']:.0f}/30 B{last['score_B']:.0f}/20 C{last['score_C']:.0f}/15 "
        f"D{last['score_D']:.0f}/15 E{last['score_E']:.0f}/30 F{last['score_F']:.0f}/15 "
        f"G{last['score_G']:.0f}/10"
    )
    if last.get("early_cut_B"):
        print("※ Extension 提前減碼啟動（B≥16 → 曝險上限 70%）")
    print()
    print("=== 最高 vs MA20（獨立警示，不計入 Risk） ===")
    print(f"當日最高: {today_high:,.0f}（{quote.source}／{session_label(quote.session)}）")
    print(f"MA20: {ma20:,.0f}")
    print(f"乖離: {month_dev:+.2f}%")
    if is_alert_triggered(month_dev, DEVIATION_THRESHOLD):
        print(alert_message(today_high, ma20, month_dev, DEVIATION_THRESHOLD))

    return 1 if risk >= 55 else 0


def pd_date(v) -> str:
    import pandas as pd

    return pd.Timestamp(v).strftime("%Y-%m-%d")


if __name__ == "__main__":
    raise SystemExit(main())
