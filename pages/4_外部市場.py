"""外部市場：美股科技、韓股半導體、日經、台積電 ADR。"""

import pandas as pd
import streamlit as st

from src.charts_reversal import external_compare_chart
from src.ui_common import load_reversal_bundle, sidebar_settings

st.set_page_config(page_title="外部市場", page_icon="🌏", layout="wide")
st.title("🌏 外部市場：台指期 vs 美股／韓股／日經")
st.caption("SOX + Nasdaq + 韓國半導體 對台股科技權值特別重要。外部先轉弱、台指還在高檔時要減碼。")

settings = sidebar_settings()
try:
    _, _, _, _, frame, *_ = load_reversal_bundle(settings["lookback"], settings["percentile"])
except Exception as e:
    st.error(f"資料載入失敗：{e}")
    st.stop()

row = frame.iloc[-1]

def _ret(col: str) -> str:
    val = row.get(col)
    return f"{val:+.2f}%" if pd.notna(val) else "—"

st.subheader("近 5 日漲跌")
cols = st.columns(4)
pairs = [
    ("nasdaq_ret5", "Nasdaq"),
    ("sox_ret5", "SOX 費半"),
    ("spx_ret5", "S&P 500"),
    ("kospi_ret5", "KOSPI"),
    ("samsung_ret5", "Samsung"),
    ("hynix_ret5", "SK Hynix"),
    ("nikkei_ret5", "Nikkei"),
    ("tsm_adr_ret5", "台積電 ADR"),
]
for i, (col, name) in enumerate(pairs):
    cols[i % 4].metric(name, _ret(col))

if row.get("sig_us_tech_weak"):
    st.warning("Nasdaq / SOX 同步轉弱")
if row.get("sig_kr_semi_weak"):
    st.warning("韓國半導體（KOSPI／三星／海力士）同步轉弱")
if not row.get("sig_us_tech_weak") and not row.get("sig_kr_semi_weak"):
    st.success("外部科技鏈尚未出現同步轉弱訊號")

st.plotly_chart(
    external_compare_chart(frame, ["nasdaq", "sox", "spx"], "台指期 vs 美股指數（再基期）"),
    use_container_width=True,
)
st.plotly_chart(
    external_compare_chart(frame, ["kospi", "samsung", "hynix", "tsm_adr"], "台指期 vs 韓股半導體／台積電 ADR"),
    use_container_width=True,
)
st.plotly_chart(
    external_compare_chart(frame, ["nikkei"], "台指期 vs 日經"),
    use_container_width=True,
)

st.markdown(
    """
    若出現：

    `Nasdaq ↓　SOX ↓↓　KOSPI ↓↓　SK Hynix ↓↓↓　台積電 ADR ↓`

    而 **台指期還在高檔** → 多單風險上升，應進入減碼階段。
    """
)
