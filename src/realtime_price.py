"""台指期盤中即時報價（含夜盤）。"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from .config import FINMIND_TOKEN

TW_TZ = ZoneInfo("Asia/Taipei")
HISTOCK_REFERER = "https://histock.tw/index-tw/FITX"
HISTOCK_HEADERS = {
    "Referer": HISTOCK_REFERER,
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0",
}


@dataclass
class RealtimeQuote:
    price: float
    source: str
    session: str
    quote_time: datetime | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None


def _detect_session(now: datetime) -> str:
    """依台灣時間判斷交易時段。"""
    t = now.hour * 100 + now.minute
    if 845 <= t <= 1345:
        return "day"
    if t >= 1500 or t < 500:
        return "night"
    return "closed"


def _session_label(session: str) -> str:
    return {"day": "日盤", "night": "夜盤", "closed": "非交易時段"}.get(session, "未知")


def _fetch_finmind_snapshot() -> RealtimeQuote | None:
    """FinMind 期貨即時快照（需 Sponsor Token）。"""
    if not FINMIND_TOKEN:
        return None

    url = "https://api.finmindtrade.com/api/v4/taiwan_futures_snapshot"
    headers = {"Authorization": f"Bearer {FINMIND_TOKEN}"}
    resp = requests.get(
        url,
        headers=headers,
        params={"data_id": "TXFR1"},
        timeout=10,
    )
    if resp.status_code != 200:
        return None

    payload = resp.json()
    if payload.get("status") != 200 or not payload.get("data"):
        return None

    row = payload["data"][0]
    quote_time = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00"))
    if quote_time.tzinfo is None:
        quote_time = quote_time.replace(tzinfo=TW_TZ)

    now = datetime.now(TW_TZ)
    return RealtimeQuote(
        price=float(row["close"]),
        source="FinMind 即時",
        session=_detect_session(now),
        quote_time=quote_time.astimezone(TW_TZ),
        open=float(row.get("open") or 0) or None,
        high=float(row.get("high") or 0) or None,
        low=float(row.get("low") or 0) or None,
        volume=int(row.get("total_volume") or 0) or None,
    )


def _parse_histock_summary(html: str) -> dict[str, float | int | None]:
    """解析 HiStock function.aspx 回傳的摘要 HTML。"""
    fields: dict[str, float | int | None] = {
        "open": None,
        "high": None,
        "low": None,
        "volume": None,
    }
    patterns = {
        "open": r"開盤</div><div class=\"ci_value\"><span[^>]*>([\d,.]+)",
        "high": r"最高</div><div class=\"ci_value\"><span[^>]*>([\d,.]+)",
        "low": r"最低</div><div class=\"ci_value\"><span[^>]*>([\d,.]+)",
        "volume": r"成交量\(口\)</div><div class=\"ci_value\"><span>([\d,]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, html)
        if match:
            value = float(match.group(1).replace(",", ""))
            fields[key] = int(value) if key == "volume" else value
    return fields


def _fetch_histock_realtime() -> RealtimeQuote:
    """
    HiStock 台指期 FITX 即時報價（免費，含日盤與夜盤）。

    資料來源：histock.tw/stock/module/stockdata.aspx
    """
    data_resp = requests.get(
        "https://histock.tw/stock/module/stockdata.aspx",
        params={"no": "FITX"},
        headers=HISTOCK_HEADERS,
        timeout=10,
    )
    data_resp.raise_for_status()
    payload = json.loads(data_resp.text)
    raw_ticks = payload["data"]
    # HiStock 回傳的 JSON 陣列可能含尾隨逗號
    ticks = json.loads(re.sub(r",\s*]", "]", raw_ticks))
    if not ticks:
        raise RuntimeError("HiStock 即時資料為空")

    last_ts_ms, price = ticks[-1]
    quote_time = datetime.fromtimestamp(last_ts_ms / 1000, tz=TW_TZ)

    summary_resp = requests.post(
        "https://histock.tw/stock/module/function.aspx",
        data={"m": "stocktop2017", "no": "FITX"},
        headers={"Referer": HISTOCK_REFERER, "User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    summary_resp.raise_for_status()
    summary_parts = summary_resp.text.split("~", 1)
    summary = _parse_histock_summary(summary_parts[0])
    if len(summary_parts) > 1:
        try:
            quote_time = datetime.strptime(summary_parts[1].strip(), "%Y.%m.%d %H:%M").replace(
                tzinfo=TW_TZ
            )
        except ValueError:
            pass

    now = datetime.now(TW_TZ)
    return RealtimeQuote(
        price=float(price),
        source="HiStock 即時",
        session=_detect_session(now),
        quote_time=quote_time,
        open=summary.get("open"),
        high=summary.get("high"),
        low=summary.get("low"),
        volume=summary.get("volume"),
    )


def get_realtime_price() -> RealtimeQuote:
    """
    取得台指期近月即時點位。

    優先使用 FinMind Sponsor 即時 API，否則使用 HiStock FITX 即時報價。
    """
    quote = _fetch_finmind_snapshot()
    if quote is not None:
        return quote
    return _fetch_histock_realtime()


def session_label(session: str) -> str:
    return _session_label(session)
