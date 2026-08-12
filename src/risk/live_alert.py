"""盤中試算與前一日前瞻警戒（不必等收盤）。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .constants import (
    BASE_DENOMINATOR,
    DRAWDOWN_FROM_HIGH_PCT,
    EXTENSION_EARLY_CUT_B,
    GROUP_CAPS,
    REBOUND_RET1,
    WASHOUT_DD_PCT,
    WASHOUT_RISK,
)
from .groups import (
    score_breadth,
    score_chip,
    score_extension,
    score_external,
    score_momentum,
    score_price_volume,
    score_trend,
    score_volatility,
)
from .position import compute_exposure_step
from .score import risk_level


def _safe_float(v, default=None):
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return default
    return float(v)


def build_early_alerts(row: pd.Series) -> list[dict[str, str]]:
    """用「上一根已收盤」列產生前瞻警戒（給隔日／開盤前看）。"""
    alerts: list[dict[str, str]] = []
    close = _safe_float(row.get("close"))
    ma20 = _safe_float(row.get("ma20"))
    ma60 = _safe_float(row.get("ma60"))
    dd = _safe_float(row.get("dd_from_high20"))
    risk = _safe_float(row.get("risk_score"), 0.0) or 0.0
    a = _safe_float(row.get("score_A"), 0.0) or 0.0
    b = _safe_float(row.get("score_B"), 0.0) or 0.0
    e = _safe_float(row.get("score_E"), 0.0) or 0.0
    ret1 = _safe_float(row.get("ret1"))
    rebound_stage = int(_safe_float(row.get("rebound_stage"), 0) or 0)
    washout = bool(row.get("washout_recent")) if "washout_recent" in row.index else False
    s20 = _safe_float(row.get("ma20_slope"))

    if close is not None and ma20 is not None and close < ma20:
        alerts.append(
            {
                "level": "watch",
                "title": "已跌破 MA20",
                "detail": "結構轉弱中；隔日若續弱或跳空，Risk／A 組可能快速上升。",
            }
        )
    if dd is not None and dd >= 0.05 and dd < DRAWDOWN_FROM_HIGH_PCT:
        remain = (DRAWDOWN_FROM_HIGH_PCT - dd) * 100
        alerts.append(
            {
                "level": "watch",
                "title": f"距回撤減碼門檻還約 {remain:.1f}%",
                "detail": f"相對 20 日最高已回撤 {dd*100:.1f}%；再跌一截就會觸發 Exposure 上限 70%。",
            }
        )
    if dd is not None and dd >= 0.18:
        alerts.append(
            {
                "level": "warn",
                "title": "深回撤減碼（≥18%）",
                "detail": f"距 20 日最高回撤 {dd*100:.1f}%，建議曝險上限約 25%。",
            }
        )
    elif dd is not None and dd >= 0.12:
        alerts.append(
            {
                "level": "warn",
                "title": "中度回撤減碼（≥12%）",
                "detail": f"距 20 日最高回撤 {dd*100:.1f}%，建議曝險上限約 50%。",
            }
        )
    elif dd is not None and dd >= DRAWDOWN_FROM_HIGH_PCT:
        alerts.append(
            {
                "level": "warn",
                "title": "回撤減碼已觸發（≥8%）",
                "detail": f"距 20 日最高回撤 {dd*100:.1f}%，建議曝險上限 70%。",
            }
        )
    if b >= EXTENSION_EARLY_CUT_B:
        alerts.append(
            {
                "level": "warn",
                "title": "B 過熱早減啟動",
                "detail": f"Extension={b:.0f}≥16，高檔應先降曝險（上限 70%）。",
            }
        )
    if risk >= 35:
        alerts.append(
            {
                "level": "watch",
                "title": "Risk 已接近／進入警戒帶",
                "detail": f"收盤 Risk={risk:.1f}；隔日不需等「突然變 40」才開始留意。",
            }
        )
    if a >= 10 and close is not None and ma60 is not None and close > ma60:
        alerts.append(
            {
                "level": "watch",
                "title": "短線轉弱、中線未破",
                "detail": "若跌破 MA60，A 組會再明顯跳升（類似 7/17 型態）。",
            }
        )
    if e >= 8:
        alerts.append(
            {
                "level": "watch",
                "title": "廣度偏弱",
                "detail": "指數可能還撐著，但多數個股已弱；隔日下殺時總分容易跟著上去。",
            }
        )

    # --- 籌碼：現貨／期選 ---
    f_spot = _safe_float(row.get("spot_foreign_net"))
    f_oi_chg = _safe_float(row.get("fut_foreign_oi_chg"))
    h = _safe_float(row.get("score_H"), 0.0) or 0.0
    label = str(row.get("chip_label") or "")
    if h >= 5:
        alerts.append(
            {
                "level": "warn",
                "title": f"籌碼偏空（H={h:.0f}）",
                "detail": label or "外資現貨／期貨留倉同向偏空，多單宜降曝險。",
            }
        )
    elif label and ("偏空" in label or "避險" in label):
        alerts.append(
            {
                "level": "watch",
                "title": "籌碼需留意",
                "detail": label,
            }
        )
    elif label and "偏多" in label:
        alerts.append(
            {
                "level": "info",
                "title": "籌碼偏多",
                "detail": label,
            }
        )
    if f_spot is not None and f_oi_chg is not None and f_spot > 20 and f_oi_chg < -1000:
        alerts.append(
            {
                "level": "watch",
                "title": "現貨買、期貨淨空增",
                "detail": "常見於避險：現貨力道可能被期貨空單打折，不宜解讀成單邊多頭。",
            }
        )

    # --- 跌深後轉折提示 ---
    if washout and rebound_stage >= 1:
        stage_msg = {
            1: "出現強反彈／收復近高，轉折觀察啟動；可小幅加回，勿一次滿倉。",
            2: "已站回 MA20，反彈結構成形；可把曝險往約 55～70% 規劃。",
            3: "MA20 斜率轉正，短線轉折偏多；可往約 70～85% 加回。",
            4: "站回 MA60 且均線轉多，恢復條件較完整；可考慮回到高曝險。",
        }
        alerts.insert(
            0,
            {
                "level": "info" if rebound_stage >= 2 else "watch",
                "title": f"跌深轉折提示（階段 {rebound_stage}/4）",
                "detail": stage_msg.get(rebound_stage, "washout 後反彈觀察中。"),
            },
        )
    elif washout and rebound_stage == 0 and dd is not None and dd >= WASHOUT_DD_PCT:
        alerts.append(
            {
                "level": "watch",
                "title": "洗盤區：等待轉折確認",
                "detail": (
                    f"近高回撤仍深（{dd*100:.1f}%）。"
                    f"若單日反彈≥{REBOUND_RET1*100:.0f}%或收過近三日高，系統會給轉折提示。"
                ),
            }
        )
    elif risk >= WASHOUT_RISK and (ret1 is None or ret1 < REBOUND_RET1):
        alerts.append(
            {
                "level": "watch",
                "title": "高風險洗盤中",
                "detail": "Risk 已達 HIGH；轉折需等強反彈或結構站回，不要只因單日反彈就滿倉。",
            }
        )

    if (
        close is not None
        and ma20 is not None
        and close > ma20
        and s20 is not None
        and s20 >= 0
        and risk < 40
    ):
        # 一般恢復（非 washout）也可提示
        if not (washout and rebound_stage >= 1):
            alerts.append(
                {
                    "level": "info",
                    "title": "結構恢復 Level1",
                    "detail": "收盤站上 MA20 且斜率≥0；若先前已減碼，符合加回條件之一。",
                }
            )

    return alerts


def provisional_live_risk(
    last_row: pd.Series,
    *,
    live_price: float,
    live_high: float | None = None,
    live_low: float | None = None,
    live_open: float | None = None,
    include_external: bool = True,
) -> dict[str, Any]:
    """
    以「上一交易日指標為底」+ 目前報價當暫定收盤，試算盤中 Risk／Exposure。
    均線／百分位不重算（用昨收列），故為近似值，但足以盤中提早警戒。
    """
    row = last_row.copy()
    prev_close = _safe_float(last_row.get("close"))
    ma20 = _safe_float(last_row.get("ma20"))
    ma60 = _safe_float(last_row.get("ma60"))
    ma120 = _safe_float(last_row.get("ma120"))
    high_20 = _safe_float(last_row.get("high_20"))

    px = float(live_price)
    hi = float(live_high) if live_high else px
    lo = float(live_low) if live_low else px
    if high_20 is not None:
        high_20_live = max(high_20, hi)
    else:
        high_20_live = hi

    row["close"] = px
    row["high"] = hi
    row["low"] = lo
    if live_open is not None:
        row["open"] = float(live_open)
    if prev_close and prev_close > 0:
        row["ret1"] = px / prev_close - 1.0
    if ma20 and ma20 > 0:
        row["dev20"] = (px / ma20 - 1.0) * 100
    if ma60 and ma60 > 0:
        row["dev60"] = (px / ma60 - 1.0) * 100
    if ma120 and ma120 > 0:
        row["dev120"] = (px / ma120 - 1.0) * 100
    row["high_20"] = high_20_live

    # 動能／廣度／波動／外部／籌碼：盤中無完整更新，沿用昨收（籌碼本就 T 日收盤後才齊）
    score_a = score_trend(row)
    score_b = score_extension(row)  # 百分位沿用昨收，略保守
    score_c = score_momentum(row)
    score_d = score_price_volume(row)
    score_e = score_breadth(row)
    score_f = score_volatility(row)
    score_g = score_external(row) if include_external else 0
    score_h = score_chip(row)

    denom = BASE_DENOMINATOR + GROUP_CAPS["H"] + (GROUP_CAPS["G"] if include_external else 0)
    raw = min(score_a, 30) + min(score_b, 20) + min(score_c, 15) + min(score_d, 15)
    raw += min(score_e, 30) + min(score_f, 15) + min(score_g, 10) + min(score_h, 10)
    risk = raw / denom * 100
    level = risk_level(risk)

    dd = (high_20_live - px) / high_20_live if high_20_live and high_20_live > 0 else None
    prev_exp = _safe_float(last_row.get("exposure"), 1.0) or 1.0
    prev_risk = _safe_float(last_row.get("risk_score"), 0.0) or 0.0
    washout = bool(last_row.get("washout_recent")) if "washout_recent" in last_row.index else False
    # 若昨收已非滿倉，盤中加回仍需過恢復／轉折閘門（不可只看分數映射）
    need_gate = prev_exp < 0.999
    if "recovery_tier" in last_row.index:
        prev_tier = int(_safe_float(last_row.get("recovery_tier"), 0) or 0)
        if prev_tier >= 3 and prev_risk < 35 and prev_exp >= 0.999:
            need_gate = False

    s20 = _safe_float(last_row.get("ma20_slope"))
    breadth20 = last_row.get("breadth20")
    ret1 = (px / prev_close - 1.0) if prev_close and prev_close > 0 else None
    step = compute_exposure_step(
        risk=risk,
        score_b=score_b,
        close=px,
        high_20=high_20_live,
        ma20=ma20,
        ma60=ma60,
        s20=s20,
        breadth20=breadth20,
        ret1=ret1,
        prev_exp=prev_exp,
        prev_risk=prev_risk,
        washout_recent=washout or (dd is not None and dd >= WASHOUT_DD_PCT),
        cooldown_left=int(_safe_float(last_row.get("cooldown_left"), 0) or 0),
        need_recovery_gate=need_gate,
        reclaim_swing=False,
        chip_bias=last_row.get("chip_bias"),
        opt_foreign_pcr=last_row.get("opt_foreign_pcr"),
    )
    target = step["exposure_target"]
    exposure = step["exposure"]
    early = step["early_cut_B"]
    dd_cut = step["drawdown_cut"]

    gap_pct = None
    if prev_close and prev_close > 0 and live_open is not None:
        gap_pct = float(live_open) / prev_close - 1.0
    day_chg = (px / prev_close - 1.0) if prev_close and prev_close > 0 else None

    # 壓力情境：再跌到觸發回撤各檔、或跌破 MA60
    scenarios = []
    if high_20_live and high_20_live > 0:
        for thr, label in ((0.08, "回撤減碼 8%→70%"), (0.12, "回撤減碼 12%→50%"), (0.18, "回撤減碼 18%→25%")):
            trigger_px = high_20_live * (1.0 - thr)
            if px > trigger_px:
                scenarios.append(
                    {
                        "name": f"觸發{label}",
                        "price": round(trigger_px),
                        "need_drop_pct": round((px - trigger_px) / px * 100, 2),
                    }
                )
                break  # 只顯示下一檔
    if ma60 and px > ma60:
        scenarios.append(
            {
                "name": "跌破 MA60（A 組易跳升）",
                "price": round(ma60),
                "need_drop_pct": round((px - ma60) / px * 100, 2),
            }
        )

    note = (
        "盤中近似值：均線／廣度／外部沿用最近收盤列，價格用即時報價；"
        "Exposure 已套用與收盤相同的加倉閘門／轉折規則（不會只因分數映射就跳回 90%）。"
    )
    if abs(exposure - target) > 1e-6:
        note += f" 分數目標約 {round(target*100)}%，狀態機後為 {round(exposure*100)}%。"

    return {
        "price": px,
        "as_of_basis": str(pd.Timestamp(last_row["date"]).date()) if "date" in last_row else None,
        "risk_score": round(risk, 1),
        "risk_level": level,
        "exposure": exposure,
        "exposure_pct": round(exposure * 100),
        "exposure_target": target,
        "exposure_target_pct": round(target * 100),
        "raw_score": float(raw),
        "groups": {
            "A": score_a,
            "B": score_b,
            "C": score_c,
            "D": score_d,
            "E": score_e,
            "F": score_f,
            "G": score_g,
            "H": score_h,
        },
        "dd_from_high20": None if dd is None else round(dd, 4),
        "drawdown_cut": dd_cut,
        "early_cut_B": early,
        "rebound_stage": step["rebound_stage"],
        "day_change_pct": None if day_chg is None else round(day_chg * 100, 2),
        "gap_pct": None if gap_pct is None else round(gap_pct * 100, 2),
        "below_ma20": bool(ma20 is not None and px < ma20),
        "below_ma60": bool(ma60 is not None and px < ma60),
        "scenarios": scenarios,
        "note": note,
    }
