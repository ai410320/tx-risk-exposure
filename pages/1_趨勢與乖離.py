"""第一、二層：大趨勢均線 + 20/60MA 乖離。"""

import pandas as pd
import streamlit as st

from src.charts_reversal import deviation_chart, trend_ma_chart
from src.indicators import heat_label, trend_state
from src.ui_common import load_reversal_bundle, sidebar_settings

st.set_page_config(page_title="趨勢與乖離", page_icon="📈", layout="wide")
st.title("📈 趨勢 × 均線乖離")
st.caption("大多頭：收盤 > 20MA > 60MA > 120MA > 240MA。KD 高檔本身不是出場理由。")

settings = sidebar_settings()
try:
    _, _, _, _, frame, *_ = load_reversal_bundle(settings["lookback"], settings["percentile"])
except Exception as e:
    st.error(f"資料載入失敗：{e}")
    st.stop()

row = frame.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("趨勢結構", trend_state(row))
c2.metric("20MA 乖離", f"{row['dev20']:+.2f}%" if pd.notna(row.get("dev20")) else "—")
c3.metric("60MA 乖離", f"{row['dev60']:+.2f}%" if pd.notna(row.get("dev60")) else "—")
c4.metric("乖離狀態", heat_label(row.get("dev20"), row.get("dev60")))

p1, p2 = st.columns(2)
p1.metric(
    "20MA 乖離歷史百分位",
    f"{row['dev20_pctile']:.0f}%" if pd.notna(row.get("dev20_pctile")) else "—",
    help="≥ 門檻視為「進入歷史高位」+1 分",
)
p2.metric(
    "60MA 乖離歷史百分位",
    f"{row['dev60_pctile']:.0f}%" if pd.notna(row.get("dev60_pctile")) else "—",
)

st.plotly_chart(trend_ma_chart(frame), use_container_width=True)
st.plotly_chart(deviation_chart(frame), use_container_width=True)

st.markdown(
    """
    | 狀態 | 20MA 乖離 | 60MA 乖離 | 解讀 |
    | --- | ---: | ---: | --- |
    | 正常多頭 | +2% | +5% | 🟢 |
    | 強勢 | +5% | +10% | 🟡 |
    | 過熱 | +8% | +15% | 🟠 |
    | 極端 | +10%↑ | +18%↑ | 🔴 |

    固定 8% 不一定賣；**歷史百分位**更重要。百分位過高代表「繼續持有的風險報酬比變差」，不是「一定跌」。
    """
)
