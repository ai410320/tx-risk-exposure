/**
 * 走勢判讀（非預測保證）：依均線結構／斜率／Risk 分組，拆成長線、短線、綜合走法。
 * 資料不足時回傳 unknown。
 */

function num(v) {
  if (v == null || Number.isNaN(Number(v))) return null
  return Number(v)
}

/** 長線：偏多 / 中性 / 偏空 */
export function classifyLong(row) {
  const close = num(row.close)
  const ma60 = num(row.ma60)
  const ma120 = num(row.ma120)
  const ma240 = num(row.ma240)
  if ([close, ma60, ma120].some((v) => v == null)) {
    return { bias: 'unknown', label: '資料不足', detail: '長線均線尚未齊備' }
  }

  const stackBull = ma240 != null && close > ma60 && ma60 > ma120 && ma120 > ma240
  const softBull = close > ma60 && ma60 > ma120
  const stackBear = ma240 != null && close < ma60 && ma60 < ma120 && ma120 < ma240
  const softBear = close < ma60 && ma60 < ma120

  if (stackBull) {
    return { bias: 'bull', label: '長線偏多', detail: '收盤 > MA60 > MA120 > MA240，大多頭結構仍在' }
  }
  if (softBull) {
    return { bias: 'bull', label: '長線偏多', detail: '收盤站上 MA60，且 MA60 > MA120' }
  }
  if (stackBear) {
    return { bias: 'bear', label: '長線偏空', detail: '收盤 < MA60 < MA120 < MA240，空頭結構' }
  }
  if (softBear) {
    return { bias: 'bear', label: '長線偏空', detail: '收盤跌破 MA60，且 MA60 < MA120' }
  }
  if (close > ma60) {
    return { bias: 'neutral', label: '長線中性偏多', detail: '仍在 MA60 上方，但中長期均線尚未完全多排' }
  }
  if (close < ma60) {
    return { bias: 'neutral', label: '長線中性偏空', detail: '已在 MA60 下方，但尚未形成完整空排' }
  }
  return { bias: 'neutral', label: '長線中性', detail: '長線結構混亂，先看短線與 Risk' }
}

/** 短線：偏多 / 震盪 / 偏空 */
export function classifyShort(row) {
  const close = num(row.close)
  const ma20 = num(row.ma20)
  const slope = num(row.ma20_slope)
  const a = num(row.score_A) ?? 0
  const b = num(row.score_B) ?? 0
  const d = num(row.score_D) ?? 0
  const risk = num(row.risk_score) ?? 0
  const dd = num(row.dd_from_high20)
  const dev20 = num(row.dev20)

  if (close == null || ma20 == null) {
    return { bias: 'unknown', label: '資料不足', detail: '短線均線不足' }
  }

  const below20 = close < ma20
  const above20 = close > ma20
  const flat = Math.abs(dev20 ?? 0) < 1.2 && Math.abs(slope ?? 0) < 0.005
  const deepDd = dd != null && dd >= 0.08
  const hot = b >= 16

  if (deepDd || (below20 && (a >= 12 || d >= 5 || risk >= 40))) {
    return {
      bias: 'bear',
      label: '短線偏空',
      detail: deepDd
        ? '距近高回撤已深，短線壓力大'
        : '跌破 MA20，且趨勢／價量風險升高',
    }
  }
  if (below20 && a >= 8) {
    return { bias: 'bear', label: '短線偏空', detail: '收盤在 MA20 下，短線結構轉弱' }
  }
  if (hot && above20) {
    return { bias: 'bull', label: '短線偏多（過熱）', detail: '仍在 MA20 上但乖離過熱，續漲也要防回撤' }
  }
  if (above20 && (slope == null || slope >= 0) && a <= 8 && !flat) {
    return { bias: 'bull', label: '短線偏多', detail: '站上 MA20，短線動能偏多' }
  }
  if (flat || (Math.abs(dev20 ?? 0) < 2 && a >= 6 && a < 14)) {
    return { bias: 'range', label: '短線震盪', detail: '貼近 MA20／乖離收斂，方向不明顯' }
  }
  if (above20) {
    return { bias: 'bull', label: '短線偏多', detail: '仍在 MA20 上方' }
  }
  return { bias: 'range', label: '短線震盪偏弱', detail: '短線偏弱但尚未全面轉空' }
}

/** 綜合走法標籤 */
export function classifyPath(longBias, shortBias, row = {}) {
  const b = num(row.score_B) ?? 0
  const risk = num(row.risk_score) ?? 0
  const exp = num(row.exposure)

  const key = `${longBias}|${shortBias}`
  const table = {
    'bull|bull': {
      code: 'bull_extend',
      title: '多頭延續',
      summary: '長短線同向偏多，主升段／續漲機率較高（仍受過熱與 Risk 約束）。',
    },
    'bull|bear': {
      code: 'bull_pullback',
      title: '長多短空（回檔）',
      summary: '中長期結構仍多，但短線轉弱，偏向多頭回檔或修正，不是立刻變空頭趨勢。',
    },
    'bull|range': {
      code: 'bull_digest',
      title: '高位／多頭震盪整理',
      summary: '長線仍多、短線方向不清，常見於漲後整理、等待均線跟上。',
    },
    'neutral|bull': {
      code: 'repair_rally',
      title: '反彈修復',
      summary: '長線未定、短線轉強，可能是修復反彈，需看能否重新站穩 MA60。',
    },
    'neutral|bear': {
      code: 'weakening',
      title: '轉弱觀察',
      summary: '長線中性、短線偏空，有轉空疑慮，先降曝險、等結構確認。',
    },
    'neutral|range': {
      code: 'chop',
      title: '震盪整理',
      summary: '上下都沒有清楚優勢，適合降低進出頻率、看 Risk／Exposure 控管。',
    },
    'bear|bear': {
      code: 'bear_extend',
      title: '空頭延續',
      summary: '長短線同向偏空，反彈先當空方回補，除非重新站回關鍵均線。',
    },
    'bear|bull': {
      code: 'bear_bounce',
      title: '空頭反彈',
      summary: '長線仍空、短線反彈，常見技術性反彈，尚未等於趨勢翻多。',
    },
    'bear|range': {
      code: 'bear_base',
      title: '空方震盪／築底觀察',
      summary: '下跌後震盪，可能築底也可能繼續下，需等長線結構改善。',
    },
  }

  let path = table[key] || {
    code: 'unclear',
    title: '方向不明',
    summary: '資料或結構不足以給出清楚走法。',
  }

  let note = ''
  if (b >= 16) note = '另：B 過熱早減已觸發，即使走法偏多也應限制曝險。'
  else if (risk >= 40) note = '另：Risk 已達減碼區，走法判斷需搭配降低曝險。'
  else if (exp != null && exp <= 0.7) note = '另：目前建議曝險已≤70%，操作上以防守為先。'

  return { ...path, note, key }
}

export function classifyOutlook(row) {
  const long = classifyLong(row)
  const short = classifyShort(row)
  const path = classifyPath(long.bias, short.bias, row)
  return { long, short, path }
}

/** 從 series 組出某一日的 row 物件 */
export function rowFromSeries(series, index) {
  if (!series?.date || index < 0) return null
  const keys = Object.keys(series)
  const row = {}
  for (const k of keys) {
    const arr = series[k]
    if (Array.isArray(arr)) row[k] = arr[index]
  }
  return row
}

export function biasClass(bias) {
  if (bias === 'bull') return 'bias-bull'
  if (bias === 'bear') return 'bias-bear'
  if (bias === 'range') return 'bias-range'
  if (bias === 'neutral') return 'bias-neutral'
  return 'bias-unknown'
}
