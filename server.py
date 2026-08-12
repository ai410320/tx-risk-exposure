"""FastAPI：給 Vue 前端使用的 JSON API；正式環境一併提供前端靜態檔。"""

import logging
import os
import threading
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import DEV_PERCENTILE_ALERT, REVERSAL_LOOKBACK_DAYS
from src.service import build_dashboard_payload, load_quote, load_reversal_bundle
from src.realtime_price import session_label

logger = logging.getLogger("uvicorn.error")

DIST = Path(__file__).resolve().parent / "frontend" / "dist"

_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_cors = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app = FastAPI(title="台指期大波段反轉預警 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors if "*" not in _cors else ["*"],
    allow_credentials="*" not in _cors,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _warmup_bundle() -> None:
    """背景預熱，避免使用者第一次開頁就撞上長時間冷啟動。"""

    def run() -> None:
        try:
            logger.info("warmup: loading reversal bundle…")
            load_reversal_bundle(REVERSAL_LOOKBACK_DAYS, DEV_PERCENTILE_ALERT)
            logger.info("warmup: done")
        except Exception as exc:
            logger.warning("warmup failed: %s", exc)

    threading.Thread(target=run, daemon=True, name="bundle-warmup").start()


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


if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        """SPA fallback：API 以外路徑都回 index.html。"""
        candidate = DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
