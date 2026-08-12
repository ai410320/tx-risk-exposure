"""Streamlit 共用載入與側邊欄。"""

from __future__ import annotations

import streamlit as st

from .config import DEV_PERCENTILE_ALERT, REVERSAL_LOOKBACK_DAYS
from .service import load_quote, load_reversal_bundle  # noqa: F401  (Streamlit pages 仍從此匯入)


def sidebar_settings() -> dict:
    with st.sidebar:
        st.header("設定")
        lookback = st.slider("歷史資料天數", 400, 1200, REVERSAL_LOOKBACK_DAYS, step=50)
        percentile = st.slider("乖離歷史百分位門檻", 80, 99, int(DEV_PERCENTILE_ALERT))
        refresh_seconds = st.selectbox("自動刷新間隔（秒）", [30, 60, 120, 0], index=1)
        if refresh_seconds:
            st.markdown(f'<meta http-equiv="refresh" content="{refresh_seconds}">', unsafe_allow_html=True)
        st.button("🔄 立即刷新", use_container_width=True)
        st.caption("廣度資料第一次會向證交所補齊快取，之後會比較快。")
    return {"lookback": lookback, "percentile": percentile}
