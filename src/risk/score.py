"""聚合 RiskScore 0～100。"""

from __future__ import annotations

import pandas as pd

from .constants import BASE_DENOMINATOR, GROUP_CAPS, RISK_LEVELS


def risk_level(score: float) -> str:
    for upper, name in RISK_LEVELS:
        if score < upper:
            return name
    return "EXTREME"


def aggregate_risk(
    df: pd.DataFrame,
    include_external: bool = True,
    include_chip: bool = True,
) -> pd.DataFrame:
    out = df.copy()
    denom = BASE_DENOMINATOR
    if include_external:
        denom += GROUP_CAPS["G"]
    if include_chip:
        denom += GROUP_CAPS["H"]
    raw = (
        out["score_A"].clip(upper=GROUP_CAPS["A"])
        + out["score_B"].clip(upper=GROUP_CAPS["B"])
        + out["score_C"].clip(upper=GROUP_CAPS["C"])
        + out["score_D"].clip(upper=GROUP_CAPS["D"])
        + out["score_E"].clip(upper=GROUP_CAPS["E"])
        + out["score_F"].clip(upper=GROUP_CAPS["F"])
    )
    if include_external:
        raw = raw + out["score_G"].clip(upper=GROUP_CAPS["G"])
    if include_chip and "score_H" in out.columns:
        raw = raw + out["score_H"].clip(upper=GROUP_CAPS["H"])
    elif include_chip:
        raw = raw + 0
    out["raw_score"] = raw
    out["risk_score"] = (raw / denom * 100).clip(0, 100)
    out["risk_level"] = out["risk_score"].map(risk_level)
    out["score_denom"] = denom
    return out
