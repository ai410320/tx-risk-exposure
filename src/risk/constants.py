"""Risk Score 0～100：A–F（+ 選配 G）分組評分。"""

from __future__ import annotations

GROUP_CAPS = {
    "A": 30,  # Trend
    "B": 20,  # Extension
    "C": 15,  # Momentum
    "D": 15,  # Price & Volume
    "E": 30,  # Breadth
    "F": 15,  # Volatility
    "G": 10,  # External (optional)
    "H": 10,  # Chip：法人現貨／期選留倉
}

BASE_DENOMINATOR = 125  # A–F caps sum
# G／H 選配時加進分母（見 score.aggregate_risk）

EXTENSION_EARLY_CUT_B = 16  # B≥16 → exposure 上限 70%
EXTENSION_EARLY_CUT_CAP = 0.70

# 距近高回撤減碼（累進）：收盤相對 20 日最高
# 淺回撤先提醒，深回撤才大幅砍倉（避免 Risk 升了但 Exposure 幾乎不動）
DRAWDOWN_CAPS = (
    (0.08, 0.70),  # ≥8%  → 上限 70%
    (0.12, 0.50),  # ≥12% → 上限 50%
    (0.18, 0.25),  # ≥18% → 上限 25%
)
# 相容舊名稱（第一檔）
DRAWDOWN_FROM_HIGH_PCT = DRAWDOWN_CAPS[0][0]
DRAWDOWN_EXPOSURE_CAP = DRAWDOWN_CAPS[0][1]

# 跌深後轉折：洗盤／強反彈門檻
WASHOUT_DD_PCT = 0.12  # 近高回撤達 12% 視為 washout 候選
WASHOUT_RISK = 55.0  # 或 Risk 曾達 HIGH
REBOUND_RET1 = 0.03  # 單日反彈 ≥3%
REBOUND_LOOKBACK = 20  # washout 記憶窗

RISK_LEVELS = (
    (20, "LOW"),
    (40, "NORMAL"),
    (55, "WARNING"),
    (70, "HIGH"),
    (85, "VERY_HIGH"),
    (101, "EXTREME"),
)

# §30 exposure map（微調：WARNING 中段更早降到 50%，讓 Exposure 跟得上 Risk 提醒）
EXPOSURE_BANDS = (
    (20, 1.00),
    (40, 0.90),
    (48, 0.70),  # 40～47 → 70%
    (55, 0.50),  # 48～54 → 50%（原整段都 70%，提醒力不足）
    (70, 0.35),
    (85, 0.20),
    (101, 0.05),
)

# 外資選擇權 PCR 門檻（FinMind TXO 外資多方 OI：Put/Call）
# 回測區間：2018-12～2026-08，與 TX 日頻對齊 n≈1768
# 依據：分位數 + 後續 5/20 日報酬、20 日內最大回撤
# - 舊值 1.3 ≈ 歷史中位數／均值，樣本約一半在其上，無「偏高」意義
# - P80≈1.86 起後續報酬與勝率明顯轉弱；P90≈2.23／P95≈2.45 更差
# - P20≈0.88 以下後續偏強、回撤較淺（偏多／避險少）
PCR_HIGH = 1.85  # ≈P80：偏高避險
PCR_EXTREME = 2.25  # ≈P90：極端避險／恐慌
PCR_LOW = 0.88  # ≈P20：避險偏少／偏多配置

COOLDOWN_DAYS = 3
# 加倉滯後：Risk 至少再降這麼多分，且需通過結構恢復閘門
HYSTERESIS_RISK_DROP = 3.0
