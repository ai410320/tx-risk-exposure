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

/** 底部日期軸設定（玩股網風格：圖下先看得到日期） */
export function timeAxisLabel(dates) {
  return {
    show: true,
    hideOverlap: true,
    showMinLabel: true,
    showMaxLabel: true,
    // 與下方 dataZoom 滑桿留距，避免刻度被蓋住
    margin: 10,
    color: '#475569',
    fontSize: 11,
    formatter: (value, idx) => formatAxisTickLabel(value, idx, dates),
  }
}

/** ECharts 連動縮放（玩股網：下方導航軸可拖） */
export function linkedDataZoom(
  axisCount,
  { bottom = 8, height = 26, dates = null, left = 56, right = 56 } = {},
) {
  const xAxisIndex = Array.from({ length: axisCount }, (_, i) => i)
  return [
    {
      type: 'inside',
      xAxisIndex,
      filterMode: 'none',
      zoomOnMouseWheel: 'ctrl',
      moveOnMouseWheel: false,
      moveOnMouseMove: false,
      preventDefaultMouseMove: false,
    },
    {
      type: 'slider',
      xAxisIndex,
      left,
      right,
      height,
      bottom,
      filterMode: 'none',
      brushSelect: false,
      // 關閉把手即時日期：拖動時會蓋住軸刻度與圖下時間列；區間改看 chart-timebar
      showDetail: false,
      showDataShadow: true,
      backgroundColor: '#e2e8f0',
      dataBackground: {
        lineStyle: { color: '#64748b', width: 1 },
        areaStyle: { color: '#94a3b8' },
      },
      selectedDataBackground: {
        lineStyle: { color: '#1d4ed8', width: 1.5 },
        areaStyle: { color: 'rgba(37, 99, 235, 0.35)' },
      },
      handleIcon:
        'path://M-5,-12 L5,-12 L5,12 L-5,12 Z M-1,-8 L1,-8 L1,8 L-1,8 Z',
      handleSize: 22,
      moveHandleSize: 0,
      borderColor: '#475569',
      borderWidth: 1,
      fillerColor: 'rgba(37, 99, 235, 0.28)',
      handleStyle: {
        color: '#2563eb',
        borderColor: '#1e3a8a',
        borderWidth: 1,
        shadowBlur: 3,
        shadowColor: 'rgba(30, 64, 175, 0.4)',
      },
      emphasis: {
        handleStyle: { color: '#1d4ed8', borderColor: '#1e3a8a' },
      },
      textStyle: {
        color: '#0f172a',
        fontSize: 11,
        fontWeight: 600,
      },
      labelFormatter: (value, valueStr) => formatChartDateLabel(value, valueStr, dates),
    },
  ]
}

/** 價格軸上下縮放／拖動（僅綁定日K的 yAxis） */
export function priceAxisZoom(yAxisIndex = 0, { top = '8%', height = '30%', right = 10, width = 18 } = {}) {
  return [
    {
      type: 'inside',
      yAxisIndex: [yAxisIndex],
      filterMode: 'none',
      // 在 K 線區按住拖曳可上下平移；Shift + 滾輪縮放振幅
      zoomOnMouseWheel: 'shift',
      moveOnMouseMove: true,
      moveOnMouseWheel: false,
      preventDefaultMouseMove: true,
    },
    {
      type: 'slider',
      yAxisIndex: [yAxisIndex],
      right,
      top,
      height,
      width,
      showDetail: false,
      brushSelect: false,
      filterMode: 'none',
      backgroundColor: '#e2e8f0',
      fillerColor: 'rgba(37, 99, 235, 0.28)',
      borderColor: '#475569',
      handleSize: 14,
      handleStyle: {
        color: '#2563eb',
        borderColor: '#1e3a8a',
      },
      moveHandleSize: 0,
      labelPrecision: 0,
    },
  ]
}
