"""FastAPI：給 Vue 前端使用的 JSON API。"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from src.config import DEV_PERCENTILE_ALERT, REVERSAL_LOOKBACK_DAYS
from src.service import build_dashboard_payload, load_quote
from src.realtime_price import session_label

app = FastAPI(title="台指期大波段反轉預警 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/realtime")
def realtime():
    quote = load_quote()
    return {
        "price": quote.price,
        "source": quote.source,
        "session": quote.session,
        "session_label": session_label(quote.session),
        "quote_time": quote.quote_time.strftime("%Y-%m-%d %H:%M:%S") if quote.quote_time else None,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "volume": quote.volume,
    }


@app.get("/api/dashboard")
def dashboard(
    lookback: int = Query(REVERSAL_LOOKBACK_DAYS, ge=200, le=1500),
    percentile: float = Query(DEV_PERCENTILE_ALERT, ge=50, le=99),
):
    return build_dashboard_payload(lookback, percentile)
