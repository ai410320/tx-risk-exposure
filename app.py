"""台指期大波段反轉預警系統 — 總覽（Streamlit，Baseline）。"""

import pandas as pd
import streamlit as st

from src.realtime_price import session_label
from src.service import _action_from_exposure, _heat_label, _level_color, _trend_label
from src.ui_common import load_quote, load_reversal_bundle, sidebar_settings

st.set_page_config(page_title="台指轉折點系統", page_icon="🚨", layout="wide")
st.title("台指轉折點 × 動態部位（Baseline）")
st.caption("Risk Score 0～100 → Recommended Exposure。TX 主序列；未做 Walk-Forward 優化。")

settings = sidebar_settings()

try:
    daily, monthly, breadth, external, frame, *_ = load_reversal_bundle(
        settings["lookback"], settings["percentile"]
    )
    quote = load_quote()
except Exception as e:
    st.error(f"資料載入失敗：{e}")
    st.stop()

last = frame.iloc[-1]
last_date = pd.Timestamp(last["date"]).strftime("%Y-%m-%d")
risk = float(last["risk_score"])
exp = float(last["exposure"])
level = str(last["risk_level"])
color = _level_color(level)
action = _action_from_exposure(exp)

session_text = session_label(quote.session)
quote_time = quote.quote_time.strftime("%Y-%m-%d %H:%M") if quote.quote_time else "—"

banner = f"{color} {level}：Risk {risk:.1f}/100 → Exposure {exp*100:.0f}%｜{action}"
if risk >= 70:
    st.error(banner)
elif risk >= 55:
    st.warning(banner)
elif risk >= 40:
    st.info(banner)
else:
    st.success(banner)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Risk Score", f"{risk:.1f} / 100")
c2.metric("Exposure", f"{exp*100:.0f}%")
c3.metric("趨勢結構", _trend_label(last))
c4.metric("20/60 乖離", _heat_label(last.get("dev20"), last.get("dev60")))
c5.metric("台指即時", f"{quote.price:,.0f}", help=f"{quote.source}｜{session_text}｜{quote_time}")

st.caption(f"評分基準日：{last_date}｜即時：{quote_time} {session_text}｜標的：TX")

g1, g2, g3, g4, g5, g6, g7 = st.columns(7)
g1.metric("A Trend", f"{last['score_A']:.0f}/30")
g2.metric("B Ext", f"{last['score_B']:.0f}/20")
g3.metric("C Mom", f"{last['score_C']:.0f}/15")
g4.metric("D PV", f"{last['score_D']:.0f}/15")
g5.metric("E Breadth", f"{last['score_E']:.0f}/30")
g6.metric("F Vol", f"{last['score_F']:.0f}/15")
g7.metric("G Extnl", f"{last['score_G']:.0f}/10")

st.line_chart(frame.set_index("date")[["risk_score", "exposure"]].rename(columns={"risk_score": "Risk", "exposure": "Exposure"}))
st.caption("Risk Score 是機率式風險管理模型，不保證預測最高點或未來績效。")
