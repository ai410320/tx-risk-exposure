"""A–F（+G）分組得分。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import GROUP_CAPS, PCR_EXTREME, PCR_HIGH


def _ext_ladder_b12(pctile: float) -> int:
    if pd.isna(pctile) or pctile < 70:
        return 0
    if pctile < 80:
        return 2
    if pctile < 90:
        return 4
    if pctile < 95:
        return 6
    if pctile < 97.5:
        return 8
    return 10


def _ext_ladder_b3(pctile: float) -> int:
    if pd.isna(pctile) or pctile < 80:
        return 0
    if pctile < 90:
        return 2
    if pctile < 95:
        return 4
    if pctile < 97.5:
        return 6
    return 8


def score_trend(row: pd.Series) -> int:
    a = 0
    close, ma20, ma60 = row.get("close"), row.get("ma20"), row.get("ma60")
    if pd.notna(ma20) and close < ma20:
        a += 8
    if pd.notna(ma60) and close < ma60:
        a += 12
    s20 = row.get("ma20_slope")
    if pd.notna(s20):
        if s20 > 0.01:
            pass
        elif s20 >= 0:
            a += 2
        elif s20 >= -0.01:
            a += 6
        else:
            a += 10
    s60 = row.get("ma60_slope")
    if pd.notna(s60):
        if s60 > 0.01:
            pass
        elif s60 >= 0:
            a += 3
        elif s60 >= -0.01:
            a += 7
        else:
            a += 12
    if pd.notna(ma20) and pd.notna(ma60) and ma20 < ma60:
        a += 8
    return min(a, GROUP_CAPS["A"])


def score_extension(row: pd.Series) -> int:
    b = _ext_ladder_b12(row.get("dev20_pctile"))
    b += _ext_ladder_b12(row.get("dev60_pctile"))
    b += _ext_ladder_b3(row.get("dev120_pctile"))
    return min(b, GROUP_CAPS["B"])


def score_momentum(row: pd.Series) -> int:
    c = 0
    rsi = row.get("rsi14")
    if pd.notna(rsi):
        if rsi < 65:
            pass
        elif rsi < 70:
            c += 1
        elif rsi < 75:
            c += 3
        elif rsi < 80:
            c += 5
        else:
            c += 7
    k, d = row.get("k"), row.get("d")
    if pd.notna(k) and k > 80:
        if bool(row.get("kd_cross_down")):
            c += 4
        else:
            c += 1
    dd = int(row.get("hist_down_days") or 0)
    if dd >= 6:
        c += 5
    elif dd >= 4:
        c += 4
    elif dd >= 2:
        c += 2
    if pd.notna(row.get("macd")) and row["macd"] < 0:
        c += 7
    div = 0
    if bool(row.get("price_new_high_20")):
        hist, hmax = row.get("macd_hist"), row.get("hist_20_max")
        if pd.notna(hist) and pd.notna(hmax) and hist < hmax * 0.98:
            div += 5
        kk, kmax = row.get("k"), row.get("k_20_max")
        if pd.notna(kk) and pd.notna(kmax) and kk < kmax * 0.98:
            div += 3
    c += min(div, 8)
    return min(c, GROUP_CAPS["C"])


def score_price_volume(row: pd.Series) -> int:
    d = 0
    ret1, vr = row.get("ret1"), row.get("vol_ratio")
    if pd.notna(ret1) and pd.notna(vr) and ret1 < 0:
        if vr > 2:
            d += 8
        elif vr > 1.5:
            d += 5
    if bool(row.get("price_new_high_20")) and bool(row.get("vol_ma20_declining")):
        d += 3
    if pd.notna(ret1):
        if ret1 < -0.04:
            d += 10
        elif ret1 < -0.03:
            d += 7
        elif ret1 < -0.02:
            d += 4
    return min(d, GROUP_CAPS["D"])


def score_breadth(row: pd.Series) -> int:
    """Phase1：僅 E1 AD ratio、E2 breadth20%。E3–E6 待個股宇宙。"""
    e = 0
    ad = row.get("ad_ratio")
    # MD: adv/decliners；既有快取 ad_ratio = up/(up+down) ∈ [0,1]
    # 轉成 MD 的 AD = up/down
    up, down = row.get("up"), row.get("down")
    if pd.notna(up) and pd.notna(down):
        ad_md = float(up) / max(float(down), 1.0)
        if ad_md > 1.2:
            pass
        elif ad_md >= 0.8:
            e += 1
        elif ad_md >= 0.6:
            e += 3
        else:
            e += 5
    elif pd.notna(ad):
        # fallback: treat as breadth fraction
        if ad > 0.55:
            pass
        elif ad >= 0.45:
            e += 1
        elif ad >= 0.35:
            e += 3
        else:
            e += 5

    b20 = row.get("breadth20")
    if pd.notna(b20):
        # breadth20 as percent 0–100
        if b20 > 60:
            pass
        elif b20 >= 50:
            e += 1
        elif b20 >= 40:
            e += 3
        elif b20 >= 30:
            e += 5
        else:
            e += 8
    return min(e, GROUP_CAPS["E"])


def score_volatility(row: pd.Series) -> int:
    f = 0
    p = row.get("atr_pctile")
    if pd.notna(p):
        if p < 50:
            pass
        elif p < 70:
            f += 1
        elif p < 85:
            f += 3
        elif p < 95:
            f += 5
        else:
            f += 7
    sh = row.get("atr_shock")
    if pd.notna(sh):
        if sh > 1.5:
            f += 8
        elif sh > 1.3:
            f += 5
    return min(f, GROUP_CAPS["F"])


def score_external(row: pd.Series) -> int:
    """選配 G：Nasdaq/SOX 與韓股轉弱（cap 10）。"""
    g = 0
    n5, s5 = row.get("nasdaq_ret5"), row.get("sox_ret5")
    if pd.notna(n5) and pd.notna(s5) and n5 < 0 and s5 < 0:
        g += 5
    if pd.notna(s5) and s5 <= -4:
        g += 3
    k5, h5 = row.get("samsung_ret5"), row.get("hynix_ret5")
    if pd.notna(k5) and pd.notna(h5) and k5 < 0 and h5 < 0:
        g += 4
    return min(g, GROUP_CAPS["G"])


def score_chip(row: pd.Series) -> int:
    """
    Group H：籌碼偏空加分（多單風險）。
    現貨大賣、期貨淨空增、現貨／期貨同向偏空、PCR 偏高。
    """
    h = 0
    f_spot = row.get("spot_foreign_net")
    f_5d = row.get("spot_foreign_net_5d")
    f_oi_chg = row.get("fut_foreign_oi_chg")
    f_deal = row.get("fut_foreign_deal_net")
    pcr = row.get("opt_foreign_pcr")
    bias = row.get("chip_bias")

    if pd.notna(f_spot) and f_spot <= -80:
        h += 3
    elif pd.notna(f_spot) and f_spot <= -40:
        h += 2
    if pd.notna(f_5d) and f_5d <= -200:
        h += 2
    if pd.notna(f_oi_chg) and f_oi_chg <= -2000:
        h += 3
    elif pd.notna(f_oi_chg) and f_oi_chg <= -1000:
        h += 2
    if pd.notna(f_deal) and f_deal <= -3000:
        h += 1
    # 現貨賣 + 期貨淨空同步 → 偏空確認
    if pd.notna(f_spot) and pd.notna(f_oi_chg) and f_spot < 0 and f_oi_chg < -500:
        h += 2
    if pd.notna(pcr) and pcr >= PCR_EXTREME:
        h += 2
    elif pd.notna(pcr) and pcr >= PCR_HIGH:
        h += 1
    if pd.notna(bias) and float(bias) <= -1.5:
        h += 1
    return min(h, GROUP_CAPS["H"])


def apply_group_scores(
    df: pd.DataFrame,
    include_external: bool = True,
    include_chip: bool = True,
) -> pd.DataFrame:
    out = df.copy()
    scores = out.apply(
        lambda r: pd.Series(
            {
                "score_A": score_trend(r),
                "score_B": score_extension(r),
                "score_C": score_momentum(r),
                "score_D": score_price_volume(r),
                "score_E": score_breadth(r),
                "score_F": score_volatility(r),
                "score_G": score_external(r) if include_external else 0,
                "score_H": score_chip(r) if include_chip else 0,
            }
        ),
        axis=1,
    )
    return pd.concat([out, scores], axis=1)
