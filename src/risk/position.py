"""部位曝險：§30 + 滯後 + 恢復閘門 + 冷卻 + B 早減 + 累進回撤 + 跌深反彈。"""

from __future__ import annotations

import pandas as pd

from .constants import (
    COOLDOWN_DAYS,
    DRAWDOWN_CAPS,
    EXTENSION_EARLY_CUT_B,
    EXTENSION_EARLY_CUT_CAP,
    EXPOSURE_BANDS,
    HYSTERESIS_RISK_DROP,
    PCR_EXTREME,
    PCR_HIGH,
    REBOUND_LOOKBACK,
    REBOUND_RET1,
    WASHOUT_DD_PCT,
    WASHOUT_RISK,
)


def exposure_from_score(risk: float) -> float:
    for upper, exp in EXPOSURE_BANDS:
        if risk < upper:
            return exp
    return 0.05


def chip_exposure_cap(chip_bias=None, pcr=None) -> float | None:
    """
    籌碼對 Exposure 的硬上限（與 Risk 策略取嚴整合）。
    回測（約 2024-06～2026-08）：min(Risk,Chip) 夏普更高、MDD 更浅。
    None = 不額外限制。
    """
    cap = None
    if chip_bias is not None and pd.notna(chip_bias):
        b = float(chip_bias)
        if b <= -1.5:
            cap = 0.50 if cap is None else min(cap, 0.50)
        elif b <= -0.5:
            cap = 0.70 if cap is None else min(cap, 0.70)
    if pcr is not None and pd.notna(pcr):
        p = float(pcr)
        if p >= PCR_EXTREME:
            cap = 0.35 if cap is None else min(cap, 0.35)
        elif p >= PCR_HIGH:
            cap = 0.70 if cap is None else min(cap, 0.70)
    return cap


def drawdown_hard_cap(dd_pct: float | None) -> float | None:
    """依回撤深度回傳硬上限；無觸發則 None。"""
    if dd_pct is None or pd.isna(dd_pct):
        return None
    cap = None
    for thr, c in DRAWDOWN_CAPS:
        if dd_pct >= thr:
            cap = c
    return cap


def _recovery_tier(
    close,
    ma20,
    ma60,
    s20,
    risk: float,
    breadth20,
    *,
    structure_ok_for_full: bool,
) -> int:
    """
    恢復階梯（0＝無）：
      1: close>MA20 且 MA20 slope≥0 → 可加到 ≥50%
      2: close>MA60 且 MA20>MA60 → 可加到 ≥75%
      3: Risk<40 且 breadth20>50 且結構未壞 → 可加到 100%
    """
    tier = 0
    if pd.notna(close) and pd.notna(ma20) and pd.notna(s20) and close > ma20 and s20 >= 0:
        tier = max(tier, 1)
    if (
        pd.notna(close)
        and pd.notna(ma20)
        and pd.notna(ma60)
        and close > ma60
        and ma20 > ma60
    ):
        tier = max(tier, 2)
    if structure_ok_for_full and risk < 40 and pd.notna(breadth20) and breadth20 > 50:
        tier = max(tier, 3)
    return tier


def _tier_allows_exposure(tier: int, desired: float) -> bool:
    """加倉時：目標曝險需有對應恢復階梯（文件 §31–32 本意）。"""
    if desired <= 0.50 + 1e-9:
        return True  # 加回到 ≤50%：允許（仍受滯後／冷卻約束）
    if desired <= 0.75 + 1e-9:
        return tier >= 2
    return tier >= 3


def _rebound_stage_from_flags(
    *,
    washout_recent: bool,
    close,
    ma20,
    ma60,
    s20,
    ret1,
    reclaim_swing: bool = False,
) -> int:
    if not washout_recent:
        return 0
    strong_bounce = pd.notna(ret1) and float(ret1) >= REBOUND_RET1
    above_ma20 = pd.notna(close) and pd.notna(ma20) and float(close) > float(ma20)
    slope_up = pd.notna(s20) and float(s20) >= 0
    above_ma60 = (
        pd.notna(close)
        and pd.notna(ma20)
        and pd.notna(ma60)
        and float(close) > float(ma60)
        and float(ma20) > float(ma60)
    )
    if above_ma60:
        return 4
    if above_ma20 and slope_up:
        return 3
    if above_ma20:
        return 2
    if strong_bounce or reclaim_swing:
        return 1
    return 0


def compute_exposure_step(
    *,
    risk: float,
    score_b: float,
    close,
    high_20,
    ma20,
    ma60,
    s20,
    breadth20,
    ret1,
    prev_exp: float,
    prev_risk: float,
    washout_recent: bool,
    cooldown_left: int = 0,
    need_recovery_gate: bool = False,
    reclaim_swing: bool = False,
    chip_bias=None,
    opt_foreign_pcr=None,
) -> dict:
    """
    單日部位狀態機一步（收盤序列與盤中試算共用）。
    回傳 desired / target / hard_cap / rebound_stage / recovery_tier / flags。
    """
    target = exposure_from_score(risk)
    b = float(score_b) if score_b is not None and pd.notna(score_b) else 0.0

    dd_pct = float("nan")
    if pd.notna(close) and pd.notna(high_20) and float(high_20) > 0:
        dd_pct = (float(high_20) - float(close)) / float(high_20)

    used_early = b >= EXTENSION_EARLY_CUT_B
    dd_cap = drawdown_hard_cap(None if pd.isna(dd_pct) else float(dd_pct))
    used_dd = dd_cap is not None

    below_ma20 = pd.notna(close) and pd.notna(ma20) and float(close) < float(ma20)
    deepish_dd = (not pd.isna(dd_pct)) and float(dd_pct) >= 0.05
    structure_ok_for_full = not below_ma20 and not deepish_dd and not used_early

    tier = _recovery_tier(
        close,
        ma20,
        ma60,
        s20,
        risk,
        breadth20,
        structure_ok_for_full=structure_ok_for_full,
    )
    rebound_stage = _rebound_stage_from_flags(
        washout_recent=washout_recent,
        close=close,
        ma20=ma20,
        ma60=ma60,
        s20=s20,
        ret1=ret1,
        reclaim_swing=reclaim_swing,
    )
    rebound_cap_relax = {0: None, 1: 0.50, 2: 0.70, 3: 0.85, 4: 1.00}[rebound_stage]
    rebound_floor = {0: 0.0, 1: 0.40, 2: 0.55, 3: 0.70, 4: 0.85}[rebound_stage]

    hard_cap = 1.0
    if used_early:
        hard_cap = min(hard_cap, EXTENSION_EARLY_CUT_CAP)
    if dd_cap is not None:
        hard_cap = min(hard_cap, dd_cap)
    if rebound_cap_relax is not None and washout_recent:
        relaxed = rebound_cap_relax
        if used_early:
            relaxed = min(relaxed, EXTENSION_EARLY_CUT_CAP)
        hard_cap = max(hard_cap, relaxed) if dd_cap is not None else hard_cap
        hard_cap = min(hard_cap, 1.0)
    chip_cap = chip_exposure_cap(chip_bias, opt_foreign_pcr)
    if chip_cap is not None:
        hard_cap = min(hard_cap, chip_cap)

    target = min(target, hard_cap)

    floor = 0.0
    if not used_early:
        if tier >= 1:
            floor = max(floor, 0.50)
        if tier >= 2:
            floor = max(floor, 0.75)
        if tier >= 3:
            floor = max(floor, 1.00)
    if rebound_floor > 0 and washout_recent and not used_early:
        floor = max(floor, rebound_floor)
    if hard_cap < 1.0 - 1e-9:
        floor = min(floor, hard_cap)

    if target < 0.25:
        desired = target
    else:
        desired = max(target, floor) if floor else target
    desired = min(desired, hard_cap)

    gate = bool(need_recovery_gate)
    if desired < prev_exp - 1e-9 and desired <= 0.90:
        gate = True
    if tier >= 3 and risk < 35:
        gate = False

    cd = int(cooldown_left or 0)
    if cd > 0:
        if rebound_stage >= 1 and rebound_floor > prev_exp + 1e-9 and not used_early:
            desired = min(desired, max(prev_exp, min(rebound_floor, hard_cap)))
        else:
            desired = min(desired, prev_exp)
        cd -= 1

    if desired > prev_exp + 1e-9:
        risk_ok = prev_risk - risk >= HYSTERESIS_RISK_DROP
        if gate:
            gate_ok = _tier_allows_exposure(tier, desired)
            if rebound_stage >= 1 and desired <= rebound_floor + 1e-9:
                gate_ok = True
            if rebound_stage >= 2 and desired <= 0.70 + 1e-9:
                gate_ok = True
            if rebound_stage >= 3 and desired <= 0.85 + 1e-9:
                gate_ok = True
            if rebound_stage >= 4:
                gate_ok = True
            if not (risk_ok and gate_ok):
                desired = prev_exp
        elif not risk_ok:
            desired = prev_exp

    if risk >= 90:
        desired = min(desired, 0.10)

    if desired < prev_exp - 1e-9 and desired <= 0.50:
        cd = COOLDOWN_DAYS

    return {
        "exposure": float(desired),
        "exposure_target": float(target),
        "hard_cap": float(hard_cap),
        "rebound_stage": int(rebound_stage),
        "recovery_tier": int(tier),
        "early_cut_B": bool(used_early),
        "drawdown_cut": bool(used_dd),
        "dd_from_high20": None if pd.isna(dd_pct) else float(dd_pct),
        "cooldown_left": int(cd),
        "need_recovery_gate": bool(gate),
        "washout_recent": bool(washout_recent),
        "chip_cap": None if chip_cap is None else float(chip_cap),
    }


def apply_exposure(df: pd.DataFrame) -> pd.DataFrame:
    """
    逐日狀態機（僅用當日與過去資料）：
    1) §30 由 risk_score 映射目標曝險
    2) 硬上限（優先於恢復地板）：
       - B≥16 → 曝險上限 70%
       - 距 20 日最高回撤累進上限（8%/12%/18% → 70%/50%/25%）
    3) 跌深 washout 後若出現強反彈，可放寬回撤上限並給地板（轉折加回）
    4) 恢復條件：地板 +「加倉閘門」（砍倉後不可只因 Risk 微降就加回）
    5) 高風險砍倉後冷卻 COOLDOWN_DAYS，期間不得加倉
    6) 滯後：加倉需 risk 至少下降 HYSTERESIS_RISK_DROP 分
    """
    out = df.copy()
    n = len(out)
    exposure = [1.0] * n
    cooldown = [0] * n
    target_col = []
    early_cut = []
    dd_cut = []
    dd_pct_col = []
    rebound_stage_col = []
    washout_col = []
    recovery_tier_col = []
    chip_cap_col = []

    prev_exp = 1.0
    prev_risk = 0.0
    cd = 0
    # washout 記憶：最近 REBOUND_LOOKBACK 日內曾達門檻
    recent_dd: list[float] = []
    recent_risk: list[float] = []
    # 砍倉後進入「需結構確認才能加回」模式
    need_recovery_gate = False

    for i in range(n):
        row = out.iloc[i]
        risk = float(row["risk_score"]) if pd.notna(row["risk_score"]) else 0.0
        b = float(row["score_B"]) if pd.notna(row["score_B"]) else 0.0
        target = exposure_from_score(risk)

        close = row.get("close")
        high_20 = row.get("high_20")
        dd_pct = float("nan")
        if pd.notna(close) and pd.notna(high_20) and float(high_20) > 0:
            dd_pct = (float(high_20) - float(close)) / float(high_20)

        used_early = b >= EXTENSION_EARLY_CUT_B
        dd_cap = drawdown_hard_cap(None if pd.isna(dd_pct) else float(dd_pct))
        used_dd = dd_cap is not None

        recent_dd.append(0.0 if pd.isna(dd_pct) else float(dd_pct))
        recent_risk.append(risk)
        if len(recent_dd) > REBOUND_LOOKBACK:
            recent_dd.pop(0)
            recent_risk.pop(0)
        washout_recent = max(recent_dd) >= WASHOUT_DD_PCT or max(recent_risk) >= WASHOUT_RISK

        ma20 = row.get("ma20")
        ma60 = row.get("ma60")
        s20 = row.get("ma20_slope")
        breadth20 = row.get("breadth20")
        ret1 = row.get("ret1")

        # 結構仍弱時不給 Level3 滿倉地板（修：3 月初 breadth 還好就強制 100%）
        below_ma20 = pd.notna(close) and pd.notna(ma20) and float(close) < float(ma20)
        deepish_dd = (not pd.isna(dd_pct)) and float(dd_pct) >= 0.05
        structure_ok_for_full = not below_ma20 and not deepish_dd and not used_early

        tier = _recovery_tier(
            close,
            ma20,
            ma60,
            s20,
            risk,
            breadth20,
            structure_ok_for_full=structure_ok_for_full,
        )

        # --- 跌深轉折：強反彈階梯 ---
        # stage 0 無；1 強反彈日；2 站回 MA20；3 MA20 斜率轉正；4 站回 MA60 結構
        rebound_stage = 0
        if washout_recent:
            strong_bounce = pd.notna(ret1) and float(ret1) >= REBOUND_RET1
            # 收過近 3 日最高（不含當日）：用 high 欄若有
            reclaim_swing = False
            if i >= 3 and pd.notna(close):
                prev_highs = out["high"].iloc[i - 3 : i]
                if prev_highs.notna().any() and float(close) > float(prev_highs.max()):
                    reclaim_swing = True
            above_ma20 = pd.notna(close) and pd.notna(ma20) and float(close) > float(ma20)
            slope_up = pd.notna(s20) and float(s20) >= 0
            above_ma60 = (
                pd.notna(close)
                and pd.notna(ma20)
                and pd.notna(ma60)
                and float(close) > float(ma60)
                and float(ma20) > float(ma60)
            )
            if above_ma60:
                rebound_stage = 4
            elif above_ma20 and slope_up:
                rebound_stage = 3
            elif above_ma20:
                rebound_stage = 2
            elif strong_bounce or reclaim_swing:
                rebound_stage = 1

        # 反彈時放寬回撤硬上限（否則永遠卡在 25～50%，轉折提示無意義）
        rebound_cap_relax = {
            0: None,
            1: 0.50,
            2: 0.70,
            3: 0.85,
            4: 1.00,
        }[rebound_stage]
        rebound_floor = {
            0: 0.0,
            1: 0.40,
            2: 0.55,
            3: 0.70,
            4: 0.85,
        }[rebound_stage]

        hard_cap = 1.0
        if used_early:
            hard_cap = min(hard_cap, EXTENSION_EARLY_CUT_CAP)
        if dd_cap is not None:
            hard_cap = min(hard_cap, dd_cap)
        if rebound_cap_relax is not None and washout_recent:
            # 反彈放寬：取較高者（但不能突破 B 早減）
            relaxed = rebound_cap_relax
            if used_early:
                relaxed = min(relaxed, EXTENSION_EARLY_CUT_CAP)
            hard_cap = max(hard_cap, relaxed) if dd_cap is not None else hard_cap
            hard_cap = min(hard_cap, 1.0)
        chip_cap = chip_exposure_cap(row.get("chip_bias"), row.get("opt_foreign_pcr"))
        if chip_cap is not None:
            hard_cap = min(hard_cap, chip_cap)

        target = min(target, hard_cap)

        # recovery floors
        floor = 0.0
        if not used_early:
            if tier >= 1:
                floor = max(floor, 0.50)
            if tier >= 2:
                floor = max(floor, 0.75)
            if tier >= 3:
                floor = max(floor, 1.00)
        if rebound_floor > 0 and washout_recent and not used_early:
            floor = max(floor, rebound_floor)

        # 有硬上限時地板不可突破硬上限
        if hard_cap < 1.0 - 1e-9:
            floor = min(floor, hard_cap)

        if target < 0.25:
            desired = target
        else:
            desired = max(target, floor) if floor else target

        desired = min(desired, hard_cap)

        # 標記「曾砍倉」→ 之後加倉要過恢復閘門
        if desired < prev_exp - 1e-9 and desired <= 0.90:
            need_recovery_gate = True
        if tier >= 3 and risk < 35:
            need_recovery_gate = False

        # cooldown：原則鎖加倉；跌深轉折地板可小幅突破（否則 4/10 強反彈仍卡死）
        if cd > 0:
            if rebound_stage >= 1 and rebound_floor > prev_exp + 1e-9 and not used_early:
                desired = min(desired, max(prev_exp, min(rebound_floor, hard_cap)))
            else:
                desired = min(desired, prev_exp)
            cd -= 1

        # 加倉：滯後 + 恢復閘門（修：4/2 Risk 從 42→38 就加回 90%）
        if desired > prev_exp + 1e-9:
            risk_ok = prev_risk - risk >= HYSTERESIS_RISK_DROP
            if need_recovery_gate:
                # washout 反彈階梯可視為過閘（對應目標檔位）
                gate_ok = _tier_allows_exposure(tier, desired)
                if rebound_stage >= 1 and desired <= rebound_floor + 1e-9:
                    gate_ok = True
                if rebound_stage >= 2 and desired <= 0.70 + 1e-9:
                    gate_ok = True
                if rebound_stage >= 3 and desired <= 0.85 + 1e-9:
                    gate_ok = True
                if rebound_stage >= 4:
                    gate_ok = True
                if not (risk_ok and gate_ok):
                    desired = prev_exp
            elif not risk_ok:
                desired = prev_exp

        if risk >= 90:
            desired = min(desired, 0.10)

        if desired < prev_exp - 1e-9 and desired <= 0.50:
            cd = COOLDOWN_DAYS

        exposure[i] = float(desired)
        cooldown[i] = cd
        target_col.append(float(target))
        early_cut.append(bool(used_early))
        dd_cut.append(bool(used_dd))
        dd_pct_col.append(None if pd.isna(dd_pct) else float(dd_pct))
        rebound_stage_col.append(int(rebound_stage))
        washout_col.append(bool(washout_recent))
        recovery_tier_col.append(int(tier))
        chip_cap_col.append(None if chip_cap is None else float(chip_cap))
        prev_exp = desired
        prev_risk = risk

    out["exposure_target"] = target_col
    out["exposure"] = exposure
    out["cooldown_left"] = cooldown
    out["early_cut_B"] = early_cut
    out["drawdown_cut"] = dd_cut
    out["dd_from_high20"] = dd_pct_col
    out["rebound_stage"] = rebound_stage_col
    out["washout_recent"] = washout_col
    out["recovery_tier"] = recovery_tier_col
    out["chip_cap"] = chip_cap_col
    return out
