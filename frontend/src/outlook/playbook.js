/**
 * 長期偏多操作劇本：把走法翻成「現在什麼情勢／要不要抱／哪裡加減」。
 * 點位是參考帶，不是保證進出場價。
 */

import { classifyOutlook } from './regime'

function num(v) {
  if (v == null || Number.isNaN(Number(v))) return null
  return Number(v)
}

function roundPx(v) {
  if (v == null || !Number.isFinite(v)) return null
  return Math.round(v)
}

function recentRange(series, index, lookback = 20) {
  if (!series?.high || !series?.low || index < 0) return { high: null, low: null }
  const from = Math.max(0, index - lookback + 1)
  let high = null
  let low = null
  for (let i = from; i <= index; i += 1) {
    const h = num(series.high[i])
    const l = num(series.low[i])
    if (h != null) high = high == null ? h : Math.max(high, h)
    if (l != null) low = low == null ? l : Math.min(low, l)
  }
  return { high, low }
}

function phaseFromOutlook(outlook, row) {
  const code = outlook?.path?.code || 'unclear'
  const close = num(row.close)
  const ma20 = num(row.ma20)
  const ma60 = num(row.ma60)
  const dd = num(row.dd_from_high20)
  const b = num(row.score_B) ?? 0
  const risk = num(row.risk_score) ?? 0

  if (code === 'bull_extend') {
    if (b >= 16 || (dd != null && dd < 0.03 && risk >= 35)) {
      return {
        id: 'extend_hot',
        label: '上升段（過熱）',
        tone: 'bull',
        plain: '長短線仍多，但乖離／Risk 偏高，比較像追價區，不是理想加碼點。',
      }
    }
    return {
      id: 'uptrend',
      label: '上升段',
      tone: 'bull',
      plain: '長短線同向偏多，主升／續漲機率較高。',
    }
  }
  if (code === 'bull_digest' || code === 'chop') {
    return {
      id: 'digest',
      label: '盤整／消化',
      tone: 'range',
      plain: '方向不清或漲後整理。長期偏多時，重點是等回測再加，不是追高或翻空。',
    }
  }
  if (code === 'bull_pullback') {
    return {
      id: 'pullback',
      label: '多頭回檔',
      tone: 'range',
      plain: '長線仍多、短線轉弱。這常是整理／回測均線，不是立刻變空頭。',
    }
  }
  if (code === 'repair_rally') {
    return {
      id: 'repair',
      label: '反彈修復',
      tone: 'neutral',
      plain: '短線轉強但長線未定，先當修復，看能否站穩 MA60。',
    }
  }
  if (code === 'weakening') {
    return {
      id: 'weakening',
      label: '轉弱觀察',
      tone: 'bear',
      plain: '長線中性、短線偏空，有轉空疑慮，先降曝險。',
    }
  }
  if (code === 'bear_bounce') {
    return {
      id: 'bear_bounce',
      label: '空頭反彈',
      tone: 'bear',
      plain: '長線仍空下的反彈，偏技術性，不適合當新多單起漲點。',
    }
  }
  if (code === 'bear_base') {
    return {
      id: 'bear_base',
      label: '空方震盪',
      tone: 'bear',
      plain: '下跌後震盪，可能築底也可能續跌，等長線改善再談續抱。',
    }
  }
  if (code === 'bear_extend') {
    return {
      id: 'downtrend',
      label: '下降段',
      tone: 'bear',
      plain: '長短線同向偏空，長期偏多者也應先降碼／空手，等結構修復。',
    }
  }

  // fallback by price vs MAs
  if (close != null && ma20 != null && ma60 != null) {
    if (close > ma20 && ma20 > ma60) {
      return { id: 'uptrend', label: '偏上升', tone: 'bull', plain: '價格仍在短中線上方。' }
    }
    if (close < ma60) {
      return { id: 'weakening', label: '偏轉弱', tone: 'bear', plain: '已在 MA60 下方。' }
    }
  }
  return {
    id: 'digest',
    label: '盤整／不明',
    tone: 'range',
    plain: '結構不夠清楚，先用均線帶與 Risk 控管。',
  }
}

/**
 * @param {object} row series 當日列
 * @param {object|null} series 完整 series（算近高／近低）
 * @param {number} index
 */
export function buildPlaybook(row, series = null, index = -1) {
  if (!row) return null
  const outlook = classifyOutlook(row)
  const phase = phaseFromOutlook(outlook, row)

  const close = num(row.close)
  const ma20 = num(row.ma20)
  const ma60 = num(row.ma60)
  const ma120 = num(row.ma120)
  const risk = num(row.risk_score) ?? 0
  const exp = num(row.exposure)
  const b = num(row.score_B) ?? 0
  const dd = num(row.dd_from_high20)
  const { high: rangeHigh, low: rangeLow } = recentRange(series, index, 20)

  const addZoneLow = roundPx(ma20 != null && ma60 != null ? Math.min(ma20, ma60) : ma20 ?? ma60)
  const addZoneHigh = roundPx(ma20 != null && ma60 != null ? Math.max(ma20, ma60) * 1.005 : ma20 ?? ma60)
  const holdFloor = roundPx(ma60)
  const invalidation = roundPx(ma60 != null && ma120 != null ? Math.min(ma60, ma120) : ma60)
  const reduceNear = roundPx(rangeHigh)
  const support = roundPx(rangeLow)

  let stance = {
    code: 'hold',
    label: '續抱多單',
    detail: '長期偏多架構下，先續抱、用均線帶管理加減碼。',
  }
  let entry = '—'
  let exit = '—'
  let doNow = []

  if (phase.id === 'uptrend') {
    stance = {
      code: 'hold',
      label: '續抱多單',
      detail: '上升段：核心部位續抱；不要因為盤中震盪就翻空。',
    }
    entry = addZoneLow != null && addZoneHigh != null
      ? `回測 MA20～MA60（約 ${addZoneLow}～${addZoneHigh}）再考慮加碼`
      : '等回測短中線再加'
    exit = invalidation != null
      ? `日收跌破 MA60（約 ${invalidation}）且短線轉弱 → 先降碼`
      : '日收跌破 MA60 → 先降碼'
    doNow = ['核心多單續抱', '不追高加碼', '用回測均線帶當加碼區']
  } else if (phase.id === 'extend_hot') {
    stance = {
      code: 'hold_trim',
      label: '續抱但減碼',
      detail: '仍偏多，但過熱／Risk 偏高：抱核心、砍追價單。',
    }
    entry = reduceNear != null
      ? `接近近高（約 ${reduceNear}）不加碼；要加等回到均線帶`
      : '不加碼，等回到 MA20／MA60'
    exit = `Exposure 跟系統走；若日收破 MA20 且 Risk 仍高，先降到系統建議曝險`
    doNow = ['不追價', '減掉槓桿／衛星倉', '等回檔再談加碼']
  } else if (phase.id === 'digest' || phase.id === 'pullback') {
    stance = {
      code: 'wait_add',
      label: '續抱／等回加碼',
      detail:
        phase.id === 'pullback'
          ? '多頭回檔：這正是長期多單最常猶豫的時候；先分清「整理」與「翻空」。'
          : '盤整期：進出最難抓。長期偏多 → 降操作頻率，等回測帶。',
    }
    entry =
      addZoneLow != null && addZoneHigh != null
        ? `理想加碼帶：${addZoneLow}～${addZoneHigh}（MA20／MA60 區），收盤仍站穩再加`
        : '回測 MA20／MA60 附近，收盤站穩再加'
    exit =
      holdFloor != null
        ? `整理失敗線：日收有效跌破 MA60（約 ${holdFloor}）→ 降碼，先不要加`
        : '日收有效跌破 MA60 → 降碼'
    doNow = [
      '核心多單可續抱',
      '盤整中減少來回',
      '不到加碼帶不追',
      '不要因為整理就翻成空單',
    ]
  } else if (phase.id === 'repair') {
    stance = {
      code: 'probe',
      label: '輕倉觀察',
      detail: '反彈修復尚未等於趨勢翻多，倉位宜輕。',
    }
    entry = holdFloor != null ? `站穩 MA60（約 ${holdFloor}）上方再加到正常曝險` : '站穩 MA60 再加'
    exit = '再度跌回 MA60 下 → 減回輕倉'
    doNow = ['先確認站回 MA60', '不滿倉追反彈']
  } else if (phase.id === 'weakening' || phase.id === 'bear_bounce' || phase.id === 'bear_base') {
    stance = {
      code: 'reduce',
      label: '降碼／觀望',
      detail: '偏轉弱或空方結構：長期偏多者也先降曝險，等長線改善。',
    }
    entry = holdFloor != null ? `重新站上 MA60（約 ${holdFloor}）並短線轉多，才考慮回補` : '等站回 MA60'
    exit = '依系統 Exposure；反彈不加碼'
    doNow = ['降到系統建議曝險', '反彈當減碼／觀望', '不空手翻空當主策略']
  } else if (phase.id === 'downtrend') {
    stance = {
      code: 'cash',
      label: '空手／極低曝險',
      detail: '下降段：長期偏多也先保護本金，等結構翻多。',
    }
    entry = ma20 != null && ma60 != null
      ? `至少收復 MA20 且朝向站回 MA60（約 ${roundPx(ma60)}）再分批回補`
      : '等均線結構翻多再回補'
    exit = '已空手則等回補條件；有殘倉跟系統降碼'
    doNow = ['優先降碼', '不抄底猜底', '回補看結構不是看感覺']
  }

  if (exp != null && exp <= 0.5 && stance.code === 'hold') {
    stance = {
      ...stance,
      detail: `${stance.detail}（系統建議曝險已≤50%，以系統為準。）`,
    }
  }
  if (b >= 16 && (stance.code === 'hold' || stance.code === 'wait_add')) {
    doNow = ['B 過熱早減已觸發', ...doNow.filter((x) => x !== '不追高加碼')]
  }

  const levels = [
    { key: 'price', label: '參考現價', value: roundPx(close) },
    { key: 'add', label: '加碼帶（MA20～MA60）', value: addZoneLow != null && addZoneHigh != null ? `${addZoneLow}～${addZoneHigh}` : '—' },
    { key: 'hold', label: '續抱防守（MA60）', value: holdFloor ?? '—' },
    { key: 'invalid', label: '整理失敗／降碼', value: invalidation ?? '—' },
    { key: 'high20', label: '近20日高', value: reduceNear ?? '—' },
    { key: 'low20', label: '近20日低', value: support ?? '—' },
  ]

  return {
    outlook,
    phase,
    stance,
    entry,
    exit,
    doNow,
    levels,
    risk,
    exposure: exp,
    dd,
  }
}
