"""第五層：上市上漲／下跌家數、指數背離。"""

import pandas as pd
import streamlit as st

from src.charts_reversal import breadth_chart
from src.ui_common import load_reversal_bundle, sidebar_settings

st.set_page_config(page_title="市場廣度", page_icon="🧭", layout="wide")
st.title("🧭 市場廣度：台指期 vs 上漲／下跌家數")
st.caption("不要只看台指。指數漲、大多數股票跌 = 指數背離，大波段轉折常用訊號。")

settings = sidebar_settings()
try:
    _, _, _, _, frame, *_ = load_reversal_bundle(settings["lookback"], settings["percentile"])
except Exception as e:
    st.error(f"資料載入失敗：{e}")
    st.stop()

breadth_rows = frame.dropna(subset=["up"]).copy()
if breadth_rows.empty:
    st.warning("尚無當日上市廣度（可能尚未收盤或證交所尚未更新）。")
else:
    dates = pd.to_datetime(breadth_rows["date"]).dt.strftime("%Y-%m-%d").tolist()
    default_idx = len(dates) - 1
    selected = st.selectbox("查看日期", dates, index=default_idx)
    row = breadth_rows.iloc[dates.index(selected)]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("選定日期", selected)
    c2.metric("上漲家數", f"{int(row['up']):,}")
    c3.metric("下跌家數", f"{int(row['down']):,}")
    c4.metric("漲跌比", f"{row['ad_ratio']:.2f}" if pd.notna(row.get("ad_ratio")) else "—")
    c5.metric("漲停", f"{int(row['limit_up'])}")
    c6.metric("跌停", f"{int(row['limit_down'])}")

    if row.get("sig_breadth_weak"):
        st.error("廣度惡化：上漲家數偏弱，或出現「台指漲、個股跌」的指數背離。")
    elif row.get("ad_ratio") and row["ad_ratio"] >= 0.55:
        st.success("廣度健康：上漲家數明顯多於下跌。")
    else:
        st.info("廣度中性，持續觀察漲跌比是否與指數背離。")

st.plotly_chart(breadth_chart(frame), use_container_width=True)

st.markdown(
    """
    - **健康**：上漲 520 / 下跌 430  
    - **很差**：上漲 280 / 下跌 670  
    - 若台積電、聯發科、鴻海把指數撐住，但大部分股票下跌 → **指數背離**  
    - 「新高／強勢家數下降」此處用 **漲停家數 + 上漲家數** 在指數接近 20 日高點時是否下滑來近似  
    """
)
