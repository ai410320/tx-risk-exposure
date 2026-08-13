/** 圖表顯示區間（與側欄「計算用歷史天數」分開） */

export const CHART_RANGE_OPTIONS = [
  { id: '1M', label: '1個月', tradingDays: 22 },
  { id: '3M', label: '3個月', tradingDays: 66 },
  { id: '6M', label: '6個月', tradingDays: 132 },
  { id: '1Y', label: '1年', tradingDays: 252 },
  { id: 'ALL', label: '全部', tradingDays: null },
]

export function resolveWindowSize(rangeId, totalLen = 0) {
  const total = Math.max(0, Number(totalLen) || 0)
  if (!total) return 0
  const opt = CHART_RANGE_OPTIONS.find((o) => o.id === rangeId)
  if (!opt || opt.tradingDays == null) return total
  return Math.min(opt.tradingDays, total)
}

export function sliceDates(dates, rangeId) {
  const list = dates || []
  const n = resolveWindowSize(rangeId, list.length)
  return n ? list.slice(-n) : []
}

/** 把 YYYY-MM-DD 收成較好讀的時間標籤 */
export function formatChartDateLabel(value, valueStr, dates = null) {
  let raw = valueStr != null && valueStr !== '' ? String(valueStr) : ''
  if ((!raw || /^\d+$/.test(raw)) && Array.isArray(dates)) {
    const idx = Number(value)
    if (Number.isInteger(idx) && dates[idx] != null) raw = String(dates[idx])
  }
  if (!raw && value != null) raw = String(value)

  const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (m) return `${m[1]}/${m[2]}/${m[3]}`
  return raw
}

/** 軸上刻度：月/日；跨年或首筆顯示年 */
export function formatAxisTickLabel(value, idx, dates = null) {
  const raw = String(value ?? '')
  const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return raw
  const [, y, mo, d] = m
  if (idx === 0) return `${y}/${mo}/${d}`
  if (Array.isArray(dates) && idx > 0) {
    const prev = String(dates[idx - 1] ?? '')
    const pm = prev.match(/^(\d{4})/)
    if (pm && pm[1] !== y) return `${y}/${mo}/${d}`
  }
  if (mo === '01' && d === '01') return `${y}/${mo}/${d}`
  return `${mo}/${d}`
}

export function formatZoomRangeText(dates, startPct = 0, endPct = 100) {
  if (!dates?.length) return ''
  const last = dates.length - 1
  const i0 = Math.max(0, Math.min(last, Math.round((startPct / 100) * last)))
  const i1 = Math.max(0, Math.min(last, Math.round((endPct / 100) * last)))
  const a = formatChartDateLabel(i0, dates[i0], dates)
  const b = formatChartDateLabel(i1, dates[i1], dates)
  return `${a}  ～  ${b}`
}

/** 底部日期軸設定 */
export function timeAxisLabel(dates, { compact = false } = {}) {
  return {
    show: true,
    hideOverlap: true,
    showMinLabel: true,
    showMaxLabel: true,
    margin: compact ? 8 : 10,
    color: '#475569',
    fontSize: compact ? 10 : 11,
    formatter: (value, idx) => formatAxisTickLabel(value, idx, dates),
  }
}

/** 隱藏式 dataZoom：實際拖動由 BaseChart HTML 時間軸負責 */
export function linkedDataZoom(axisCount) {
  const n = Math.max(1, Number(axisCount) || 1)
  const xAxisIndex = Array.from({ length: n }, (_, i) => i)
  return [
    {
      type: 'slider',
      show: false,
      xAxisIndex,
      filterMode: 'none',
    },
  ]
}
