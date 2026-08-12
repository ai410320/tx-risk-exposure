"""第三、四層：價量、MACD 柱、KD 頂背離（確認用，不是預測）。"""

import pandas as pd
import streamlit as st

from src.charts_reversal import volume_macd_kd_chart
from src.ui_common import load_reversal_bundle, sidebar_settings

st.set_page_config(page_title="價量與動能", page_icon="📊", layout="wide")
st.title("📊 價量 × MACD × KD")
st.caption("MACD／KD 放在「確認」而不是「預測」。單獨死叉不要當成出場訊號。")

settings = sidebar_settings()
try:
    _, _, _, _, frame, *_ = load_reversal_bundle(settings["lookback"], settings["percentile"])
except Exception as e:
    st.error(f"資料載入失敗：{e}")
    st.stop()

row = frame.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("量比（/20日均量）", f"{row['vol_ratio']:.2f}x" if pd.notna(row.get("vol_ratio")) else "—")
c2.metric("MACD 柱", f"{row['macd_hist']:.1f}" if pd.notna(row.get("macd_hist")) else "—")
c3.metric("K / D", f"{row['k']:.1f} / {row['d']:.1f}" if pd.notna(row.get("k")) else "—")
c4.metric(
    "動能訊號",
    ("KD頂背離 " if row.get("sig_kd_div") else "")
    + ("MACD縮柱 " if row.get("sig_macd_shrink") else "")
    + ("爆量未創高" if row.get("sig_vol_climax") else "")
    or "未觸發",
)

st.plotly_chart(volume_macd_kd_chart(frame), use_container_width=True)

st.markdown(
    """
    **健康多頭**：價格 ↑ 且成交量 ↑  

    **危險組合**：高檔爆量換手 → 再出現爆量長黑  

    **KD 頂背離**：價格創新高、KD 沒創新高 → 開始警戒，不必立刻空  

    **MACD 柱**：即使指數還在創新高，柱狀體連續縮小 = 上漲動能衰退  
    """
)
