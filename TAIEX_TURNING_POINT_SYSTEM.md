# TAIEX Turning Point & Dynamic Position Sizing System

## 1. Project Overview

建立一套用於「台股大波段多單減碼」的量化系統。

系統的主要目的不是預測最高點，也不是預測明天漲跌。

真正目標：

> 當台股由強勢多頭逐漸進入高風險區域時，提前降低台指期多單曝險；當趨勢重新恢復時，再逐步增加曝險。

核心概念：

```text
Market Data
    ↓
Indicator Calculation
    ↓
Signal Detection
    ↓
Risk Score 0~100
    ↓
Position Exposure
    ↓
Backtest
    ↓
Walk-Forward Optimization
    ↓
Production Parameters
```

---

# 2. Backtest Period

主要回測區間：

```text
START_DATE = 2018-01-01
END_DATE   = 2026-08-10
```

因為部分指標需要 240 個交易日以上的歷史資料，所以實際資料下載範圍必須提前至少 300 個交易日。

---

# 3. IMPORTANT: Backtest Integrity

禁止：

* Look-ahead bias
* Future data leakage
* 使用未來資料計算當日訊號
* 使用未來成分股名單回填歷史
* 使用未來修正後資料直接判斷當時訊號
* 使用整個 2018~2026 資料集直接最佳化後再宣稱策略有效

所有訊號必須遵守：

```text
Signal[t]
只能使用
Data[<= t]
```

交易執行：

```text
Signal generated at day t close
→ position change at day t+1 open
```

如果沒有日內資料，禁止假設可以在當日收盤價成交。

---

# 4. Data Source Priority

## Primary

Taiwan Stock Exchange (TWSE)

需要：

1. TAIEX daily OHLC / close
2. Individual stock daily OHLC
3. Individual stock volume
4. Individual stock trading value
5. Number of advancing stocks
6. Number of declining stocks
7. New highs
8. New lows

---

# 5. Market Instrument

主要市場指標：

```text
TAIEX
```

注意：

TAIEX 指數本身不是台指期。

第一階段使用：

```text
TAIEX as market regime proxy
```

第二階段如果取得完整 TAIFEX futures historical data，再加入：

```text
TX Futures
```

並比較：

```text
TAIEX signal
vs
TX signal
```

---

# 6. System Architecture

```text
src/
├── data/
│   ├── twse/
│   ├── taifex/
│   └── cache/
│
├── indicators/
│   ├── trend.ts
│   ├── momentum.ts
│   ├── volatility.ts
│   ├── volume.ts
│   └── breadth.ts
│
├── signals/
│   ├── trendSignals.ts
│   ├── momentumSignals.ts
│   ├── breadthSignals.ts
│   └── riskScore.ts
│
├── backtest/
│   ├── engine.ts
│   ├── metrics.ts
│   ├── walkForward.ts
│   └── optimizer.ts
│
└── strategy/
    └── positionSizing.ts
```

---

# 7. Indicator Groups

系統分成六個主要群組：

```text
A. Trend
B. Valuation / Extension
C. Momentum
D. Price & Volume
E. Market Breadth
F. Volatility
```

---

# 8. A. Trend Indicators

## A1. Price vs MA20

```text
close < MA20
```

Signal:

```text
false = 0
true  = +8
```

Interpretation:

短期趨勢開始轉弱。

---

## A2. Price vs MA60

```text
close < MA60
```

Signal:

```text
false = 0
true  = +12
```

Interpretation:

中期趨勢開始轉弱。

---

## A3. MA20 Slope

計算：

```text
MA20_slope =
(MA20[t] / MA20[t-5]) - 1
```

Signal：

```text
slope > +1%      = 0
0 ~ +1%          = +2
-1% ~ 0%         = +6
< -1%            = +10
```

---

## A4. MA60 Slope

```text
MA60_slope =
(MA60[t] / MA60[t-10]) - 1
```

Signal：

```text
slope > +1%      = 0
0 ~ +1%          = +3
-1% ~ 0%         = +7
< -1%            = +12
```

---

## A5. MA20 vs MA60

正常多頭：

```text
MA20 > MA60
```

轉弱：

```text
MA20 < MA60
```

Signal:

```text
MA20 >= MA60 = 0
MA20 < MA60  = +8
```

---

# 9. B. Price Extension / Moving Average Deviation

不要直接使用固定：

```text
+8% = overbought
```

而要使用 historical percentile。

---

## B1. MA20 Deviation

```text
deviation20 =
(close / MA20 - 1) * 100
```

計算 rolling percentile：

```text
lookback = 756 trading days
```

約 3 年。

Risk:

```text
percentile < 70   = 0
70 ~ 80           = 2
80 ~ 90           = 4
90 ~ 95           = 6
95 ~ 97.5         = 8
> 97.5            = 10
```

注意：

這個指標是「過熱風險」。

它不能單獨觸發清倉。

---

## B2. MA60 Deviation

```text
deviation60 =
(close / MA60 - 1) * 100
```

Rolling percentile:

```text
lookback = 756
```

Risk:

```text
percentile < 70   = 0
70 ~ 80           = 2
80 ~ 90           = 4
90 ~ 95           = 6
95 ~ 97.5         = 8
> 97.5            = 10
```

---

## B3. MA120 Deviation

同樣計算：

```text
deviation120 =
(close / MA120 - 1) * 100
```

Risk:

```text
percentile < 80   = 0
80 ~ 90           = 2
90 ~ 95           = 4
95 ~ 97.5         = 6
> 97.5            = 8
```

---

# 10. C. Momentum

## C1. RSI14

```text
RSI(14)
```

Risk:

```text
RSI < 65       = 0
65 ~ 70        = 1
70 ~ 75        = 3
75 ~ 80        = 5
> 80           = 7
```

Important:

RSI high does NOT mean immediate sell.

It represents extension risk.

---

# 11. C2. KD

Use:

```text
K = stochastic K
D = stochastic D
```

High-risk conditions:

```text
K > 80
AND
K crosses below D
```

Score:

```text
No condition = 0
K > 80        = +1
K > 80 + K<D  = +4
```

Do NOT assign large weight to KD.

Reason:

Strong bull markets can remain overbought for extended periods.

---

# 12. C3. MACD

Parameters:

```text
fast = 12
slow = 26
signal = 9
```

Calculate:

```text
MACD
Signal
Histogram
```

Risk conditions:

### Histogram declining

```text
hist[t] < hist[t-1]
```

Score:

```text
1 day = 0
2-3 days = +2
4-5 days = +4
>5 days = +5
```

---

## MACD Zero Line

```text
MACD < 0
```

Score:

```text
false = 0
true  = +7
```

---

# 13. C4. Momentum Divergence

Detect:

```text
Price makes new 20-day high
BUT
MACD histogram does not make new 20-day high
```

Score:

```text
No divergence = 0
Divergence = +5
```

For KD:

```text
Price new high
AND
KD fails to make new high
```

Score:

```text
+3
```

Maximum divergence score:

```text
+8
```

---

# 14. D. Price & Volume

## D1. Volume Ratio

```text
volume_ratio =
volume / SMA(volume, 20)
```

---

## D2. Down Day + High Volume

Condition:

```text
close < previous_close
AND
volume_ratio > 1.5
```

Score:

```text
+5
```

If:

```text
volume_ratio > 2
```

Score:

```text
+8
```

---

# 15. D3. Uptrend With Declining Volume

Condition:

```text
price makes new 20-day high
AND
20-day average volume is declining
```

Score:

```text
+3
```

This is a warning signal only.

---

# 16. D4. Large Bearish Candle

Define:

```text
daily_return =
(close / previous_close - 1)
```

Condition:

```text
daily_return < -2%
```

Score:

```text
-2% ~ -3% = +4
-3% ~ -4% = +7
< -4%     = +10
```

This represents actual trend damage.

---

# 17. E. Market Breadth

Market breadth is extremely important.

Calculate daily:

```text
advancers
decliners
unchanged
```

---

# 18. E1. Advance / Decline Ratio

```text
AD_ratio =
advancers / max(decliners, 1)
```

Risk:

```text
AD_ratio > 1.2 = 0
0.8 ~ 1.2      = +1
0.6 ~ 0.8      = +3
< 0.6          = +5
```

---

# 19. E2. Breadth Percentage

```text
breadth =
advancers / (advancers + decliners)
```

20-day average:

```text
breadth20 =
SMA(breadth, 20)
```

Risk:

```text
> 60%       = 0
50~60%      = +1
40~50%      = +3
30~40%      = +5
< 30%       = +8
```

---

# 20. E3. Percentage of Stocks Above MA20

For every eligible stock:

```text
stock_close > stock_MA20
```

Calculate:

```text
pct_above_MA20 =
stocks_above_MA20 / eligible_stocks
```

Risk:

```text
> 70%       = 0
60~70%      = +1
50~60%      = +3
40~50%      = +5
30~40%      = +7
< 30%       = +10
```

---

# 21. E4. Percentage Above MA60

```text
pct_above_MA60
```

Risk:

```text
> 65%       = 0
55~65%      = +1
45~55%      = +3
35~45%      = +5
25~35%      = +7
< 25%       = +10
```

---

# 22. E5. New High / New Low

Calculate:

```text
new_high_20
new_low_20
```

Ratio:

```text
NHNL =
new_high_20 / max(new_low_20, 1)
```

Risk:

```text
NHNL > 2.0 = 0
1.0~2.0    = +1
0.5~1.0    = +3
0.25~0.5   = +5
< 0.25     = +8
```

---

# 23. E6. Breadth Divergence

Condition:

```text
TAIEX makes new 60-day high
AND
pct_above_MA20 decreases by >= 10 percentage points
```

Score:

```text
+8
```

This is an important warning signal.

---

# 24. F. Volatility

## F1. ATR14

Calculate:

```text
ATR14
```

Normalize:

```text
ATR_ratio =
ATR14 / close
```

Compare with historical percentile.

Risk:

```text
< 50 percentile = 0
50~70           = +1
70~85           = +3
85~95           = +5
> 95            = +7
```

---

# 25. F2. Volatility Shock

Condition:

```text
ATR14 / ATR60 > 1.3
```

Score:

```text
+5
```

If:

```text
ATR14 / ATR60 > 1.5
```

Score:

```text
+8
```

---

# 26. Risk Score

Initial implementation:

```text
RiskScore =
TrendScore
+ ExtensionScore
+ MomentumScore
+ PriceVolumeScore
+ BreadthScore
+ VolatilityScore
```

However, do NOT allow unlimited accumulation.

Normalize to:

```text
0 ~ 100
```

Formula:

```text
RiskScore =
min(
    100,
    RawRiskScore / MaxPossibleRawScore * 100
)
```

---

# 27. Important: Avoid Double Counting

Several indicators measure essentially the same thing.

For example:

```text
Price < MA20
MA20 slope negative
MA20 < MA60
```

are correlated.

Therefore the system must use group caps.

---

## Group Caps

```text
Trend maximum = 30
Extension maximum = 20
Momentum maximum = 15
PriceVolume maximum = 15
Breadth maximum = 30
Volatility maximum = 15
```

Total:

```text
125
```

Then normalize:

```text
RiskScore =
RawScore / 125 * 100
```

---

# 28. Initial Baseline Weight

These are NOT claimed to be backtested final weights.

They are only starting parameters for the optimizer.

```text
Trend        24%
Extension    16%
Momentum     12%
PriceVolume  14%
Breadth      24%
Volatility   10%
```

Reason:

The system should prioritize:

```text
Trend
+
Market Breadth
```

rather than letting:

```text
KD
RSI
MACD
```

dominate the entire model.

---

# 29. Risk Levels

Initial baseline:

```text
0-19   = LOW
20-39  = NORMAL
40-54  = WARNING
55-69  = HIGH
70-84  = VERY_HIGH
85-100 = EXTREME
```

---

# 30. Position Sizing

The system is NOT an automatic short-selling system.

It is a long exposure management system.

Initial baseline:

```text
RiskScore 0-19:
Exposure = 100%

RiskScore 20-39:
Exposure = 90%

RiskScore 40-54:
Exposure = 70%

RiskScore 55-69:
Exposure = 50%

RiskScore 70-84:
Exposure = 25%

RiskScore 85-100:
Exposure = 0-10%
```

---

# 31. Hysteresis

Do NOT immediately increase exposure whenever RiskScore decreases by 1.

Example:

```text
High risk:
70 → 68
```

Do not immediately:

```text
25% → 50%
```

Recovery must satisfy additional conditions.

---

# 32. Recovery Conditions

To increase exposure:

### Level 1

```text
close > MA20
```

AND

```text
MA20 slope >= 0
```

Then:

```text
minimum exposure = 50%
```

---

### Level 2

```text
close > MA60
```

AND

```text
MA20 > MA60
```

Then:

```text
minimum exposure = 75%
```

---

### Level 3

```text
RiskScore < 40
```

AND

```text
breadth20 > 50%
```

Then:

```text
exposure = 100%
```

---

# 33. Cooldown

After reducing exposure due to a high-risk signal:

```text
cooldown = 3 trading days
```

During cooldown:

```text
Do not increase position
```

This prevents rapid:

```text
100%
→
50%
→
100%
→
50%
```

whipsaw behavior.

---

# 34. Backtest Targets

The system must evaluate future returns after every signal.

Calculate:

```text
ForwardReturn5
ForwardReturn10
ForwardReturn20
ForwardReturn40
```

Formula:

```text
ForwardReturnN =
Close[t+N] / Close[t] - 1
```

---

# 35. Crash Event Definition

Define a significant drawdown event:

```text
ForwardReturn20 <= -5%
```

Major drawdown:

```text
ForwardReturn20 <= -8%
```

Severe drawdown:

```text
ForwardReturn20 <= -10%
```

---

# 36. Indicator Evaluation

For every individual signal calculate:

```text
Sample Count
Average Forward Return
Median Forward Return
Probability of Forward Return < 0
Probability of <= -5%
Probability of <= -8%
Probability of <= -10%
Average Maximum Adverse Excursion
```

Example output:

```text
Signal: Price < MA20

Samples: XXXX
Average 20D Return: X.XX%
P(Return < 0): XX%
P(Return <= -5%): XX%
P(Return <= -8%): XX%
```

Do not invent these values.

They must be calculated from historical data.

---

# 37. Information Coefficient

For continuous indicators calculate:

```text
Spearman correlation(
    indicator[t],
    forward_return20[t]
)
```

Also calculate correlation with:

```text
-risk_return20
```

Higher absolute correlation = potentially more useful.

---

# 38. Signal Quality Score

For every indicator calculate:

```text
SignalQuality =
0.35 * AUC
+ 0.25 * RankCorrelation
+ 0.20 * EventPrecision
+ 0.20 * Stability
```

All components normalized to:

```text
0 ~ 100
```

---

# 39. Stability

A signal should not receive a high weight merely because it worked during one crash.

Calculate separately:

```text
2018-2020
2021-2022
2023-2024
2025-2026
```

A signal that performs consistently gets higher stability.

A signal that only works in one period gets penalized.

---

# 40. Weight Optimization

Do NOT optimize all weights freely.

That creates overfitting.

Weight constraints:

```text
Each indicator:
0 ~ 15 points

Each group:
maximum predefined group weight

Total:
100
```

Use:

```text
Grid Search
OR
Random Search
OR
Bayesian Optimization
```

Prefer Random Search first because the number of parameters may become large.

---

# 41. Optimization Objective

Do NOT optimize only total return.

Primary objective:

```text
Minimize Maximum Drawdown
```

Secondary objectives:

```text
Maximize CAGR
Maximize Sharpe
Maximize downside protection
Minimize turnover
Minimize false positives
```

Recommended composite objective:

```text
Objective =
0.35 * NormalizedCAGR
+ 0.25 * NormalizedSharpe
+ 0.25 * DrawdownProtection
+ 0.15 * SignalStability
```

---

# 42. Walk-Forward Validation

Use:

```text
Training:
2018-01-01 ~ 2022-12-31

Validation:
2023-01-01 ~ 2024-12-31

Out-of-Sample:
2025-01-01 ~ 2026-08-10
```

Then perform rolling walk-forward tests.

Example:

```text
Train 2018-2021
Validate 2022
Test 2023

Train 2019-2022
Validate 2023
Test 2024

Train 2020-2023
Validate 2024
Test 2025

Train 2021-2024
Validate 2025
Test 2026
```

Final production weights must be based on parameters that repeatedly perform well.

---

# 43. Final Production Weight Selection

Do NOT select:

```text
Best single backtest
```

Instead:

```text
ProductionWeight =
Median of stable walk-forward weights
```

For example:

```text
Trend:
[22, 25, 23, 24]
→ 23.5

Breadth:
[25, 21, 26, 24]
→ 24.5
```

Use median / trimmed mean rather than maximum-performance parameter set.

---

# 44. 2026 June-July Event Test

This is a mandatory validation case.

The system must specifically evaluate:

```text
2026-06-01
~
2026-07-31
```

Questions:

1. When did RiskScore first exceed 40?
2. When did RiskScore first exceed 55?
3. When did RiskScore first exceed 70?
4. What exposure would the system have had?
5. What was TAIEX drawdown from the local high?
6. How much drawdown was avoided?
7. How many days earlier did the system reduce exposure?
8. Did the system produce a false signal before the decline?
9. When did the system recommend increasing exposure again?

---

# 45. Critical Evaluation

The system should NOT be judged by:

```text
"Did it sell exactly at the top?"
```

Instead evaluate:

```text
Peak-to-trough drawdown avoided
```

Example:

```text
Buy & Hold:
Maximum Drawdown = -12%

System:
Maximum Drawdown = -7%

Drawdown Reduction:
41.7%
```

This is more meaningful than trying to catch the exact top.

---

# 46. Benchmark

Always compare against:

```text
Benchmark A:
100% Buy & Hold TAIEX

Benchmark B:
MA60 strategy

Benchmark C:
MA20/MA60 strategy

Benchmark D:
Risk Score strategy
```

---

# 47. Transaction Costs

Backtest must include transaction costs.

Initial assumptions:

```text
commission = configurable
slippage = configurable
tax = configurable
```

Do not hard-code them permanently.

Config:

```typescript
interface TransactionCostConfig {
  commissionRate: number
  slippageRate: number
  transactionTaxRate: number
}
```

---

# 48. Position Transition

Avoid unrealistic instantaneous changes.

Use:

```text
100% → 75% → 50% → 25% → 0%
```

rather than:

```text
100% → 0%
```

unless:

```text
RiskScore >= 90
```

or an extreme crash signal occurs.

---

# 49. Risk Score Calculation

Production API:

```typescript
interface RiskScoreResult {
  score: number
  level:
    | 'LOW'
    | 'NORMAL'
    | 'WARNING'
    | 'HIGH'
    | 'VERY_HIGH'
    | 'EXTREME'

  exposure: number

  signals: {
    name: string
    value: number
    score: number
    group: string
    description: string
  }[]
}
```

---

# 50. Signal Definition

```typescript
interface Signal {
  id: string
  name: string
  group:
    | 'TREND'
    | 'EXTENSION'
    | 'MOMENTUM'
    | 'PRICE_VOLUME'
    | 'BREADTH'
    | 'VOLATILITY'

  value: number
  threshold: number
  score: number
  maxScore: number

  active: boolean

  description: string
}
```

---

# 51. Backtest Result

```typescript
interface BacktestResult {
  period: {
    start: string
    end: string
  }

  cagr: number
  totalReturn: number
  maxDrawdown: number
  sharpe: number
  sortino: number

  winRate: number

  turnover: number

  drawdownReduction: number

  benchmark: {
    cagr: number
    totalReturn: number
    maxDrawdown: number
    sharpe: number
  }

  signals: SignalStatistics[]

  monthlyReturns: MonthlyReturn[]
}
```

---

# 52. Signal Statistics

```typescript
interface SignalStatistics {
  signalId: string

  samples: number

  avgForwardReturn5: number
  avgForwardReturn10: number
  avgForwardReturn20: number
  avgForwardReturn40: number

  medianForwardReturn20: number

  probabilityNegative20: number
  probabilityMinus5: number
  probabilityMinus8: number
  probabilityMinus10: number

  auc: number
  spearmanIC: number

  stability: number

  recommendedWeight: number
}
```

---

# 53. Frontend Dashboard

The UI should display:

## Current Risk Score

```text
Risk Score: 63 / 100

Level:
HIGH

Recommended Exposure:
50%
```

---

# 54. Signal Breakdown

Display:

```text
Trend              21 / 30
Extension           8 / 20
Momentum            7 / 15
Price & Volume      9 / 15
Breadth            18 / 30
Volatility           5 / 15
--------------------------------
Total               68 / 100
```

---

# 55. Historical Risk Score Chart

Chart:

```text
TAIEX
Risk Score
Recommended Exposure
```

The user should be able to visually identify:

```text
2020 COVID
2022 Bear Market
2024 corrections
2025 corrections
2026 June-July decline
```

---

# 56. Historical Signal Markers

Show markers on the chart:

```text
Risk > 40
Risk > 55
Risk > 70
Risk > 85
```

---

# 57. Backtest Chart

Display:

```text
Buy & Hold Equity Curve
Risk Score Strategy Equity Curve
```

Also show:

```text
Drawdown
```

---

# 58. Important UI Warning

The application must clearly state:

```text
Risk Score is a probabilistic risk-management model.
It does not predict market tops or guarantee future performance.
```

---

# 59. Initial Baseline Parameters

These values are ONLY initialization values.

They must be replaceable by backtest optimization.

```json
{
  "trend": {
    "priceBelowMA20": 8,
    "priceBelowMA60": 12,
    "ma20SlopeNegative": 10,
    "ma60SlopeNegative": 12,
    "ma20BelowMA60": 8
  },

  "extension": {
    "ma20Deviation": 10,
    "ma60Deviation": 10,
    "ma120Deviation": 8
  },

  "momentum": {
    "rsi": 7,
    "kd": 4,
    "macdHistogram": 5,
    "macdBelowZero": 7,
    "divergence": 8
  },

  "priceVolume": {
    "downHighVolume": 8,
    "decliningVolumeAtNewHigh": 3,
    "largeBearishCandle": 10
  },

  "breadth": {
    "advanceDecline": 5,
    "breadth20": 8,
    "aboveMA20": 10,
    "aboveMA60": 10,
    "newHighNewLow": 8,
    "breadthDivergence": 8
  },

  "volatility": {
    "atrPercentile": 7,
    "volatilityShock": 8
  }
}
```

Again:

```text
DO NOT label these values as "backtested".
```

They are baseline values only.

---

# 60. Optimizer Output

After backtest, generate:

```text
backtest/
├── raw-results.json
├── signal-statistics.json
├── optimized-weights.json
├── walk-forward-results.json
└── final-production-config.json
```

---

# 61. Production Config

The final file should look like:

```json
{
  "version": "1.0",
  "generatedAt": "YYYY-MM-DD",

  "backtestPeriod": {
    "start": "2018-01-01",
    "end": "2026-08-10"
  },

  "weights": {},

  "thresholds": {},

  "riskLevels": {},

  "positionSizing": {},

  "validation": {
    "outOfSample": true,
    "walkForward": true,
    "lookAheadBiasCheck": true
  }
}
```

The empty objects must be populated by the optimizer.

---

# 62. Overfitting Protection

Reject any optimized model if:

```text
Training performance is excellent
BUT
Validation performance collapses
```

Also reject if:

```text
One indicator contributes > 40% of total predictive power
```

unless it demonstrates stable performance across all periods.

---

# 63. Minimum Acceptance Criteria

The strategy should NOT be considered successful simply because CAGR is higher.

Minimum requirements:

```text
1. Lower maximum drawdown than Buy & Hold

2. Positive out-of-sample performance

3. Performance remains useful across multiple market regimes

4. No single indicator dominates the strategy

5. Reasonable turnover

6. 2026 event test produces useful early warning

7. No look-ahead bias

8. Results remain acceptable after transaction costs
```

---

# 64. Strategy Philosophy

The system follows this hierarchy:

```text
Long-term trend
      ↓
Medium-term trend
      ↓
Market breadth
      ↓
Price extension
      ↓
Momentum
      ↓
Price / volume
      ↓
Volatility
```

Do NOT allow:

```text
KD > 80
```

to automatically mean:

```text
SELL
```

Do NOT allow:

```text
RSI > 70
```

to automatically mean:

```text
SELL
```

Do NOT allow:

```text
MA20 deviation high
```

to automatically mean:

```text
SELL
```

These are warning signals.

Trend damage and market breadth deterioration should carry greater importance.

---

# 65. Recommended Strategy Behavior

### Strong Bull Market

```text
RiskScore = 0~30

Exposure:
90~100%
```

---

### Bull Market + Overheated

```text
RiskScore = 30~50

Exposure:
70~90%
```

---

### Distribution / Early Breakdown

```text
RiskScore = 50~70

Exposure:
40~70%
```

---

### Confirmed Downtrend

```text
RiskScore = 70~85

Exposure:
10~30%
```

---

### Severe Bear Market

```text
RiskScore > 85

Exposure:
0~10%
```

---

# 66. What The System Is Trying To Detect

The ideal sequence:

```text
Stage 1
Strong trend
RiskScore 10
Exposure 100%

        ↓

Stage 2
Extreme extension
RiskScore 35
Exposure 90%

        ↓

Stage 3
Breadth deterioration
RiskScore 48
Exposure 70%

        ↓

Stage 4
MACD / momentum deterioration
RiskScore 58
Exposure 50%

        ↓

Stage 5
Break below MA20
RiskScore 72
Exposure 25%

        ↓

Stage 6
Break below MA60
RiskScore 85
Exposure 10%
```

The goal is:

```text
Do not sell the top.
Reduce risk before the major drawdown.
```

---

# 67. 2026 June-July Analysis

The system MUST produce a dedicated report:

```text
2026 June-July Turning Point Analysis
```

Required fields:

```text
Local High Date
Local High Price

First Warning Date
First Warning Score

High Risk Date
High Risk Score

Confirmed Trend Breakdown Date

Maximum Drawdown

Exposure Before Decline

Exposure After Signal

Estimated Drawdown Avoided
```

---

# 68. No-Hindsight Rule

When evaluating 2026 June-July:

Do NOT say:

```text
The market eventually crashed,
therefore this indicator was correct.
```

Instead:

At every historical date:

```text
calculate only information available on that date
```

Then simulate:

```text
next trading day execution
```

---

# 69. Final Goal

The final system should answer one question every trading day:

> "Given everything that was knowable as of today's close, how much long exposure should I carry tomorrow?"

Output:

```text
Risk Score: XX / 100

Risk Level: XXXXX

Recommended Exposure: XX%

Trend: XX / 30
Extension: XX / 20
Momentum: XX / 15
Price & Volume: XX / 15
Breadth: XX / 30
Volatility: XX / 15

Primary Warning:
XXXXXXXX

Secondary Warning:
XXXXXXXX

Trend Status:
BULL / NEUTRAL / BEAR
```

---

# 70. Most Important Development Rule

DO NOT optimize the strategy until the raw indicator statistics are displayed.

First generate:

```text
Signal
→ Historical samples
→ Forward returns
→ Crash probability
→ AUC
→ IC
→ Stability
```

Only after that:

```text
Optimize weights
```

Only after that:

```text
Out-of-sample test
```

Only after that:

```text
Production configuration
```

---

# 71. Expected Development Order

Implement in this exact order:

```text
Phase 1
TAIEX historical data

↓

Phase 2
MA / RSI / KD / MACD / ATR

↓

Phase 3
Deviation percentile

↓

Phase 4
Price & volume

↓

Phase 5
Market breadth

↓

Phase 6
Risk Score

↓

Phase 7
Backtest engine

↓

Phase 8
Signal statistics

↓

Phase 9
Walk-forward optimization

↓

Phase 10
Position sizing

↓

Phase 11
2026 June-July validation

↓

Phase 12
Dashboard
```

Do not build the polished dashboard before the backtest engine produces valid data.

---

# 72. Final Deliverable

The final system must produce three separate results:

## A. Research Result

```text
Which indicators actually have predictive value?
```

## B. Strategy Result

```text
What Risk Score and weights should be used?
```

## C. Trading Result

```text
Given today's Risk Score,
what percentage of long exposure should be held?
```

These three concepts must not be mixed together.

---

# 73. Critical Disclaimer

This is a research and risk-management system.

It does not guarantee that market tops can be predicted.

The purpose is:

```text
Improve risk-adjusted returns
Reduce large drawdowns
Reduce emotional decision-making
Provide systematic position sizing
```

The strategy should be considered successful if it can:

```text
give up some upside
in exchange for
meaningfully reducing major drawdowns.
```

That is preferable to attempting to predict every market top.
