"""日K最高（含夜盤）vs 月K 乖離率。"""

import pandas as pd
import streamlit as st

from src.chart import create_dashboard_chart
from src.config import DEVIATION_THRESHOLD
from src.data_fetcher import fetch_daily_bars
from src.deviation import (
    alert_message,
    compute_deviation,
    compute_deviation_series,
    is_alert_triggered,
    latest_high_including_realtime,
    latest_ma20,
)
from src.kline import get_current_monthly_price
from src.realtime_price import session_label
from src.ui_common import load_quote, load_reversal_bundle, sidebar_settings

st.set_page_config(page_title="日K月K乖離", page_icon="📅", layout="wide")
st.title("📅 日K 最高（含夜盤）vs MA20（月線）")
st.caption("（當天最高含夜盤 − MA20）／MA20 × 100%")

settings = sidebar_settings()
threshold = st.sidebar.number_input("月K 乖離警示門檻 (%)", 0.1, 10.0, DEVIATION_THRESHOLD, 0.1)

try:
    daily, monthly, _, _, _, *_ = load_reversal_bundle(settings["lookback"], settings["percentile"])
    quote = load_quote()
    night_daily = fetch_daily_bars(lookback_days=settings["lookback"], include_night=True)
except Exception as e:
    st.error(f"資料載入失敗：{e}")
    st.stop()

deviation_series = compute_deviation_series(night_daily, monthly)
month_str, fallback_month_close = get_current_monthly_price(daily, monthly)
ma20 = latest_ma20(night_daily, last_price=quote.price) or fallback_month_close
last_high = float(night_daily.iloc[-1]["high"]) if not night_daily.empty else quote.price
today_high = latest_high_including_realtime(last_high, quote)
deviation_pct = compute_deviation(today_high, ma20)
alert = is_alert_triggered(deviation_pct, threshold)

if alert:
    st.error(alert_message(today_high, ma20, deviation_pct, threshold))
else:
    st.success(f"✅ MA20 乖離正常：{deviation_pct:+.2f}%（門檻 ±{threshold}%）")

c1, c2, c3, c4 = st.columns(4)
c1.metric("當日最高（含夜盤）", f"{today_high:,.0f}")
c2.metric("MA20（月線）", f"{ma20:,.0f}", help=f"含夜盤日K收盤 SMA20（{month_str}）")
c3.metric("乖離率", f"{deviation_pct:+.2f}%")
c4.metric("時段", session_label(quote.session))

fig = create_dashboard_chart(night_daily, monthly, deviation_series, threshold, realtime_price=today_high)
st.plotly_chart(fig, use_container_width=True)

st.caption(f"更新：{pd.Timestamp.now(tz='Asia/Taipei').strftime('%Y-%m-%d %H:%M:%S')}")
