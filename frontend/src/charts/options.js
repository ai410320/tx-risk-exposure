import { linkedDataZoom, priceAxisZoom, timeAxisLabel } from './range'

/** K 棒視覺：加粗實體，振幅較好辨識 */
const CANDLE_STYLE = {
  barWidth: '82%',
  barMinWidth: 7,
  barMaxWidth: 24,
  itemStyle: {
    color: '#ef5350',
    color0: '#26a69a',
    borderColor: '#c62828',
    borderColor0: '#00897b',
    borderWidth: 1.5,
  },
}

function last(arr, n) {
  return arr.slice(-n)
}

/** 將稀疏日期對映對齊到完整日期軸（缺日用前值，避免 Risk／Exposure 出現空值） */
function asofSeries(dates, byDate) {
  const keys = [...byDate.keys()].sort()
  let j = -1
  let lastVal = null
  return dates.map((d) => {
    while (j + 1 < keys.length && keys[j + 1] <= d) {
      j += 1
      lastVal = byDate.get(keys[j])
    }
    if (byDate.has(d)) return byDate.get(d)
    return lastVal
  })
}

function scoreColor(score) {
  if (score == null) return '#9e9e9e'
  if (score >= 85) return '#b71c1c'
  if (score >= 70) return '#c62828'
  if (score >= 55) return '#ef6c00'
  if (score >= 40) return '#f9a825'
  return '#2e7d32'
}

/** 選定日期的垂直輔助線（標籤只在 showLabel 時顯示） */
function selectedDateMarkLine(dates, selectedDate, { showLabel = true } = {}) {
  if (!selectedDate || !dates.includes(selectedDate)) return undefined
  return {
    symbol: 'none',
    animation: false,
    label: showLabel
      ? {
          show: true,
          formatter: String(selectedDate).slice(5),
          position: 'end',
          distance: 6,
          color: '#1565c0',
          fontSize: 12,
          fontWeight: 600,
          backgroundColor: 'rgba(255,255,255,0.92)',
          padding: [3, 6],
          borderRadius: 4,
          borderColor: '#90caf9',
          borderWidth: 1,
        }
      : { show: false },
    lineStyle: { type: 'dashed', color: '#1976d2', width: 1.5 },
    data: [{ xAxis: selectedDate }],
  }
}

export function scoreOption(series) {
  const dates = last(series.date, 180)
  const scores = last(series.risk_score || series.score, 180)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 110, top: 36, bottom: 40, containLabel: false },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', min: 0, max: 100, name: 'Risk' },
    series: [
      {
        type: 'bar',
        data: scores.map((s) => ({ value: s, itemStyle: { color: scoreColor(s ?? 0) } })),
        markLine: {
          symbol: 'none',
          label: {
            position: 'end',
            distance: 8,
            color: '#374151',
            fontSize: 11,
          },
          data: [
            { yAxis: 40, label: { formatter: 'WARNING 40' }, lineStyle: { type: 'dashed', color: '#f9a825' } },
            { yAxis: 55, label: { formatter: 'HIGH 55' }, lineStyle: { type: 'dashed', color: '#ef6c00' } },
            { yAxis: 70, label: { formatter: 'VERY HIGH 70' }, lineStyle: { type: 'dashed', color: '#c62828' } },
            { yAxis: 85, label: { formatter: 'EXTREME 85' }, lineStyle: { type: 'dashed', color: '#b71c1c' } },
          ],
        },
      },
    ],
  }
}

/** 總覽：日K + MA20 + 乖離 + 轉折分數（同軸對齊） */
export function overviewComboOption(series, monthDev, threshold = 0.8, selectedDate = null, windowSize = 120) {
  const n = Math.max(1, Math.min(windowSize || 120, (monthDev?.date || series.date || []).length || 120))
  const dates = last(monthDev?.date || series.date || [], n)
  const start = (monthDev?.date || []).length - dates.length
  const candle = dates.map((_, i) => {
    if (!monthDev?.date?.length) {
      const idx = series.date.length - dates.length + i
      return [series.open[idx], series.close[idx], series.low[idx], series.high[idx]]
    }
    const idx = start + i
    return [monthDev.open[idx], monthDev.close[idx], monthDev.low[idx], monthDev.high[idx]]
  })
  const ma20Line = monthDev?.ma20?.length
    ? last(monthDev.ma20, n)
    : last(series.ma20 || [], n)
  const devLine = monthDev?.deviation_pct?.length
    ? last(monthDev.deviation_pct, n)
    : last(series.dev20 || [], n)

  const scoreByDate = new Map()
  ;(series.date || []).forEach((d, i) => {
    const v = series.risk_score?.[i] ?? series.score?.[i]
    if (v != null) scoreByDate.set(d, v)
  })
  const exposureByDate = new Map()
  ;(series.date || []).forEach((d, i) => {
    const v = series.exposure?.[i]
    if (v != null) exposureByDate.set(d, v)
  })
  // 日K（含夜盤）可能多出「僅夜盤／結算」日；Risk 用日盤序列 → 以 asof 向前帶值，避免圖上出現空值斷裂
  const scores = asofSeries(dates, scoreByDate)
  const exposures = asofSeries(dates, exposureByDate).map((v) => (v == null ? null : v * 100))
  const dateMark = selectedDateMarkLine(dates, selectedDate)
  const dateMarkSilent = selectedDateMarkLine(dates, selectedDate, { showLabel: false })

  const scoreMarkData = [
    { yAxis: 40, label: { formatter: 'WARNING 40' }, lineStyle: { type: 'dashed', color: '#f9a825' } },
    { yAxis: 55, label: { formatter: 'HIGH 55' }, lineStyle: { type: 'dashed', color: '#ef6c00' } },
    { yAxis: 70, label: { formatter: 'VERY HIGH 70' }, lineStyle: { type: 'dashed', color: '#c62828' } },
    { yAxis: 85, label: { formatter: 'EXTREME 85' }, lineStyle: { type: 'dashed', color: '#b71c1c' } },
  ]
  if (dateMarkSilent) {
    scoreMarkData.push({
      xAxis: selectedDate,
      label: { show: false },
      lineStyle: dateMarkSilent.lineStyle,
    })
  }

  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, type: 'scroll' },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: [
      ...linkedDataZoom(4, { bottom: 8, height: 30, dates, left: 64, right: 128 }),
      ...priceAxisZoom(0, { top: '10%', height: '32%', right: 12 }),
    ],
    grid: [
      { left: 56, right: 128, top: 44, height: '40%' },
      { left: 56, right: 128, top: '48%', height: '8%' },
      { left: 56, right: 128, top: '58%', height: '10%' },
      { left: 56, right: 128, top: '70%', bottom: 72 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, show: false },
      { type: 'category', data: dates, gridIndex: 1, show: false },
      { type: 'category', data: dates, gridIndex: 2, show: false },
      {
        type: 'category',
        data: dates,
        gridIndex: 3,
        boundaryGap: true,
        axisTick: { alignWithLabel: true },
        axisLabel: timeAxisLabel(dates),
        axisLine: { lineStyle: { color: '#94a3b8' } },
      },
    ],
    yAxis: [
      {
        gridIndex: 0,
        scale: true,
        name: '點位',
        nameTextStyle: { fontSize: 11 },
        splitNumber: 5,
        min: (v) => v.min - (v.max - v.min) * 0.08,
        max: (v) => v.max + (v.max - v.min) * 0.08,
      },
      { gridIndex: 1, scale: true, name: '乖離%', nameTextStyle: { fontSize: 11 } },
      { gridIndex: 2, min: 0, max: 100, name: 'Risk', nameTextStyle: { fontSize: 11 } },
      { gridIndex: 3, min: 0, max: 100, name: '曝險%', nameTextStyle: { fontSize: 11 } },
    ],
    series: [
      {
        type: 'candlestick',
        name: '日K（含夜盤）',
        data: candle,
        xAxisIndex: 0,
        yAxisIndex: 0,
        ...CANDLE_STYLE,
        markLine: dateMark,
      },
      {
        type: 'line',
        name: 'MA20（月線）',
        data: ma20Line,
        xAxisIndex: 0,
        yAxisIndex: 0,
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.2, color: '#ff9800' },
        lineStyle: { color: '#ff9800', width: 2 },
      },
      {
        type: 'line',
        name: '最高 vs MA20 乖離%',
        data: devLine,
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.25, color: '#1976d2' },
        lineStyle: { color: '#1976d2', width: 2 },
        markLine: {
          symbol: 'none',
          animation: false,
          label: { show: false },
          data: [
            { yAxis: threshold, lineStyle: { type: 'dotted', color: '#d32f2f' } },
            { yAxis: -threshold, lineStyle: { type: 'dotted', color: '#d32f2f' } },
            ...(dateMarkSilent ? [{ xAxis: selectedDate, lineStyle: dateMarkSilent.lineStyle }] : []),
          ],
        },
      },
      {
        type: 'bar',
        name: 'Risk Score',
        data: scores.map((s) => ({
          value: s,
          itemStyle: { color: scoreColor(s ?? 0) },
        })),
        xAxisIndex: 2,
        yAxisIndex: 2,
        markLine: {
          symbol: 'none',
          animation: false,
          label: {
            position: 'end',
            distance: 8,
            color: '#374151',
            fontSize: 11,
          },
          data: scoreMarkData,
        },
      },
      {
        type: 'line',
        name: 'Recommended Exposure %',
        data: exposures,
        xAxisIndex: 3,
        yAxisIndex: 3,
        showSymbol: false,
        lineStyle: { color: '#6a1b9a', width: 2 },
        areaStyle: { color: 'rgba(106,27,154,0.12)' },
      },
    ],
  }
}

export function trendOption(series, selectedDate = null, windowSize = 160) {
  const n = Math.max(1, Math.min(windowSize || 160, series.date?.length || 160))
  const dates = last(series.date, n)
  const candle = dates.map((_, i) => {
    const idx = series.date.length - dates.length + i
    return [series.open[idx], series.close[idx], series.low[idx], series.high[idx]]
  })
  const line = (key) => dates.map((_, i) => series[key][series.date.length - dates.length + i])
  const dateMark = selectedDateMarkLine(dates, selectedDate)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    dataZoom: linkedDataZoom(1, { bottom: 4, dates }),
    grid: { left: 50, right: 28, top: 48, bottom: 70 },
    xAxis: { type: 'category', data: dates, axisLabel: timeAxisLabel(dates) },
    yAxis: { scale: true },
    series: [
      {
        type: 'candlestick',
        name: '台指期',
        data: candle,
        ...CANDLE_STYLE,
        markLine: dateMark,
      },
      {
        type: 'line',
        name: 'MA20',
        data: line('ma20'),
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.2, color: '#1976d2' },
        lineStyle: { width: 1.5, color: '#1976d2' },
      },
      {
        type: 'line',
        name: 'MA60',
        data: line('ma60'),
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.2, color: '#7b1fa2' },
        lineStyle: { width: 1.5, color: '#7b1fa2' },
      },
      {
        type: 'line',
        name: 'MA120',
        data: line('ma120'),
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.2, color: '#ef6c00' },
        lineStyle: { width: 1.5, color: '#ef6c00' },
      },
      {
        type: 'line',
        name: 'MA240',
        data: line('ma240'),
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.2, color: '#5d4037' },
        lineStyle: { width: 1.5, color: '#5d4037' },
      },
    ],
  }
}

export function deviationOption(series, selectedDate = null, windowSize = 200) {
  const n = Math.max(1, Math.min(windowSize || 200, series.date?.length || 200))
  const dates = last(series.date, n)
  const slice = (key) => last(series[key], n)
  const dateMark = selectedDateMarkLine(dates, selectedDate)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: linkedDataZoom(2, { bottom: 4, dates }),
    grid: [
      { left: 50, right: 28, top: 48, height: '28%' },
      { left: 50, right: 28, top: '52%', bottom: 70 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, show: false },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: timeAxisLabel(dates) },
    ],
    yAxis: [
      { gridIndex: 0, name: '20MA乖離%' },
      { gridIndex: 1, name: '60MA乖離%' },
    ],
    series: [
      {
        type: 'line',
        name: '20MA乖離',
        data: slice('dev20'),
        xAxisIndex: 0,
        yAxisIndex: 0,
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.25, color: '#1976d2' },
        lineStyle: { color: '#1976d2' },
        markLine: dateMark,
      },
      {
        type: 'line',
        name: '60MA乖離',
        data: slice('dev60'),
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.25, color: '#7b1fa2' },
        lineStyle: { color: '#7b1fa2' },
        markLine: selectedDateMarkLine(dates, selectedDate, { showLabel: false }),
      },
    ],
  }
}

export function priceVolumeOption(series, selectedDate = null, windowSize = 140) {
  const n = Math.max(1, Math.min(windowSize || 140, series.date?.length || 140))
  const dates = last(series.date, n)
  const start = series.date.length - dates.length
  const candle = dates.map((_, i) => [series.open[start + i], series.close[start + i], series.low[start + i], series.high[start + i]])
  const vol = dates.map((_, i) => ({
    value: series.volume[start + i],
    itemStyle: { color: (series.close[start + i] ?? 0) >= (series.open[start + i] ?? 0) ? '#ef5350' : '#26a69a' },
  }))
  const dateMark = selectedDateMarkLine(dates, selectedDate)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: linkedDataZoom(2, { bottom: 4, dates }),
    grid: [
      { left: 56, right: 28, top: 48, height: '54%' },
      { left: 56, right: 28, top: '70%', bottom: 70 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, show: false },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: timeAxisLabel(dates) },
    ],
    yAxis: [{ gridIndex: 0, scale: true, name: '點位', splitNumber: 5 }, { gridIndex: 1, name: '口數' }],
    series: [
      {
        type: 'candlestick',
        name: '台指期',
        data: candle,
        xAxisIndex: 0,
        yAxisIndex: 0,
        ...CANDLE_STYLE,
        markLine: dateMark,
      },
      { type: 'bar', name: '成交量', data: vol, xAxisIndex: 1, yAxisIndex: 1 },
      {
        type: 'line',
        name: '量20MA',
        data: last(series.vol_ma, n),
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: false,
        lineStyle: { color: '#455a64' },
        markLine: selectedDateMarkLine(dates, selectedDate, { showLabel: false }),
      },
    ],
  }
}

export function macdOption(series, selectedDate = null, windowSize = 140) {
  const n = Math.max(1, Math.min(windowSize || 140, series.date?.length || 140))
  const dates = last(series.date, n)
  const hist = last(series.macd_hist, n).map((v) => ({
    value: v,
    itemStyle: { color: (v ?? 0) >= 0 ? '#ef5350' : '#26a69a' },
  }))
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    dataZoom: linkedDataZoom(1, { bottom: 4, dates }),
    grid: { left: 56, right: 28, top: 48, bottom: 70 },
    xAxis: { type: 'category', data: dates, axisLabel: timeAxisLabel(dates) },
    yAxis: { name: 'MACD' },
    series: [
      {
        type: 'bar',
        name: 'MACD柱',
        data: hist,
        markLine: selectedDateMarkLine(dates, selectedDate),
      },
      {
        type: 'line',
        name: 'MACD',
        data: last(series.macd, n),
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.2 },
        lineStyle: { color: '#3949ab' },
      },
      {
        type: 'line',
        name: 'Signal',
        data: last(series.macd_signal, n),
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.2 },
        lineStyle: { color: '#f9a825' },
      },
    ],
  }
}

export function kdOption(series, selectedDate = null, windowSize = 140) {
  const n = Math.max(1, Math.min(windowSize || 140, series.date?.length || 140))
  const dates = last(series.date, n)
  const dateMark = selectedDateMarkLine(dates, selectedDate)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    dataZoom: linkedDataZoom(1, { bottom: 4, dates }),
    grid: { left: 56, right: 28, top: 48, bottom: 70 },
    xAxis: { type: 'category', data: dates, axisLabel: timeAxisLabel(dates) },
    yAxis: { min: 0, max: 100, name: 'KD' },
    series: [
      {
        type: 'line',
        name: 'K',
        data: last(series.k, n),
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.25, color: '#1976d2' },
        lineStyle: { color: '#1976d2' },
        markLine: {
          symbol: 'none',
          silent: true,
          animation: false,
          data: [
            { yAxis: 80, lineStyle: { type: 'dotted', color: '#bdbdbd' }, label: { formatter: '80' } },
            { yAxis: 20, lineStyle: { type: 'dotted', color: '#bdbdbd' }, label: { formatter: '20' } },
            ...(dateMark ? dateMark.data.map((d) => ({ ...d, label: dateMark.label, lineStyle: dateMark.lineStyle })) : []),
          ],
        },
      },
      {
        type: 'line',
        name: 'D',
        data: last(series.d, n),
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.25, color: '#ef6c00' },
        lineStyle: { color: '#ef6c00' },
      },
    ],
  }
}

export function breadthOption(series, selectedDate = null, windowSize = 160) {
  const n = Math.max(1, Math.min(windowSize || 160, series.date?.length || 160))
  const dates = last(series.date, n)
  const dateMark = selectedDateMarkLine(dates, selectedDate)
  const hasSelected = Boolean(dateMark)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    dataZoom: linkedDataZoom(3, { bottom: 4, dates }),
    grid: [
      { left: 50, right: 28, top: 48, height: '24%' },
      { left: 50, right: 28, top: '38%', height: '22%' },
      { left: 50, right: 28, top: '64%', bottom: 70 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, show: false },
      { type: 'category', data: dates, gridIndex: 1, show: false },
      { type: 'category', data: dates, gridIndex: 2, axisLabel: timeAxisLabel(dates) },
    ],
    yAxis: [{ gridIndex: 0, scale: true }, { gridIndex: 1 }, { gridIndex: 2, min: 0, max: 1 }],
    series: [
      {
        type: 'line',
        name: '台指期',
        data: last(series.close, n),
        xAxisIndex: 0,
        yAxisIndex: 0,
        showSymbol: true,
        symbol: 'circle',
        symbolSize: 8,
        triggerLineEvent: true,
        itemStyle: { color: '#212121', opacity: 0.15 },
        lineStyle: { width: 2, color: '#212121' },
        emphasis: {
          focus: 'series',
          itemStyle: { opacity: 1, borderWidth: 2, borderColor: '#1976d2' },
          scale: 1.4,
        },
        markLine: dateMark,
      },
      { type: 'bar', name: '上漲', data: last(series.up, n), xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: '#ef5350' } },
      { type: 'bar', name: '下跌', data: last(series.down, n).map((v) => (v == null ? null : -v)), xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: '#26a69a' } },
      {
        type: 'line',
        name: '漲跌比',
        data: last(series.ad_ratio, n),
        xAxisIndex: 2,
        yAxisIndex: 2,
        showSymbol: true,
        symbolSize: 6,
        triggerLineEvent: true,
        itemStyle: { opacity: 0.2 },
        markLine: {
          symbol: 'none',
          animation: false,
          label: { show: false },
          data: [
            { yAxis: 0.5, lineStyle: { type: 'dotted', color: '#9e9e9e' } },
            { yAxis: 0.4, lineStyle: { type: 'dotted', color: '#ef6c00' } },
            ...(hasSelected
              ? [{ xAxis: selectedDate, lineStyle: { type: 'dashed', color: '#1976d2', width: 1.5 } }]
              : []),
          ],
        },
      },
    ],
  }
}

export function externalOption(series, keys, names, windowSize = 180) {
  const n = Math.max(1, Math.min(windowSize || 180, series.date?.length || 180))
  const dates = last(series.date, n)
  const tx = last(series.close, n)
  const txBase = tx.find((v) => v != null)
  const echartsSeries = [
    {
      type: 'line',
      name: '台指期',
      showSymbol: false,
      lineStyle: { width: 2.5, color: '#212121' },
      data: tx.map((v) => (v == null || !txBase ? null : (v / txBase) * 100)),
    },
  ]
  keys.forEach((key, idx) => {
    const values = last(series[key] || [], n)
    const base = values.find((v) => v != null)
    echartsSeries.push({
      type: 'line',
      name: names[idx],
      showSymbol: false,
      data: values.map((v) => (v == null || !base ? null : (v / base) * 100)),
    })
  })
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    dataZoom: linkedDataZoom(1, { bottom: 4, dates }),
    grid: { left: 50, right: 20, top: 40, bottom: 70 },
    xAxis: { type: 'category', data: dates, axisLabel: timeAxisLabel(dates) },
    yAxis: { name: '再基期=100' },
    series: echartsSeries,
  }
}

/** 籌碼：外資現貨買賣超（億）＋期貨淨留倉變化 */
export function chipSpotFutOption(series, windowSize = 120) {
  const n = Math.max(1, Math.min(windowSize || 120, series.date?.length || 120))
  const dates = last(series.date, n)
  const close = last(series.close, n)
  const spot = last(series.spot_foreign_net || [], n)
  const trust = last(series.spot_trust_net || [], n)
  const oiChg = last(series.fut_foreign_oi_chg || [], n)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    // bottom 抬高：軸日期在滑桿上方；區間文字看圖下 timebar
    dataZoom: linkedDataZoom(3, { bottom: 10, height: 26, dates, left: 56, right: 28 }),
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 56, right: 28, top: 40, height: '28%' },
      { left: 56, right: 28, top: '42%', height: '15%' },
      { left: 56, right: 28, top: '61%', bottom: 70 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, show: false },
      { type: 'category', data: dates, gridIndex: 1, show: false },
      { type: 'category', data: dates, gridIndex: 2, axisLabel: timeAxisLabel(dates) },
    ],
    yAxis: [
      { gridIndex: 0, name: 'TX' },
      { gridIndex: 1, name: '現貨億' },
      { gridIndex: 2, name: '期貨口' },
    ],
    series: [
      {
        type: 'line',
        name: '台指期',
        data: close,
        showSymbol: false,
        xAxisIndex: 0,
        yAxisIndex: 0,
        lineStyle: { width: 2, color: '#212121' },
      },
      {
        type: 'bar',
        name: '外資現貨淨買超(億)',
        data: spot,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: (p) => (p.value >= 0 ? '#c62828' : '#2e7d32'),
        },
      },
      {
        type: 'bar',
        name: '投信現貨淨買超(億)',
        data: trust,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: '#1565c0', opacity: 0.55 },
      },
      {
        type: 'bar',
        name: '外資期貨淨OI變化',
        data: oiChg,
        xAxisIndex: 2,
        yAxisIndex: 2,
        itemStyle: {
          color: (p) => (p.value >= 0 ? '#c62828' : '#2e7d32'),
        },
      },
    ],
  }
}

export function chipOiPcrOption(series, windowSize = 120) {
  const n = Math.max(1, Math.min(windowSize || 120, series.date?.length || 120))
  const dates = last(series.date, n)
  const oiNet = last(series.fut_foreign_oi_net || [], n)
  const pcr = last(series.opt_foreign_pcr || [], n)
  const pcrMarks = [
    { y: 0.88, color: '#2e7d32', text: 'P20 0.88' },
    { y: 1.85, color: '#ef6c00', text: 'P80 1.85' },
    { y: 2.25, color: '#c62828', text: 'P90 2.25' },
  ]
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    dataZoom: linkedDataZoom(2, { bottom: 10, height: 26, dates, left: 64, right: 28 }),
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 64, right: 28, top: 40, height: '34%' },
      { left: 64, right: 28, top: '48%', bottom: 70 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, show: false },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: timeAxisLabel(dates) },
    ],
    yAxis: [
      { gridIndex: 0, name: '外資期貨淨OI', scale: true },
      { gridIndex: 1, name: 'PCR', scale: true, min: (v) => Math.min(0.5, v.min * 0.95), max: (v) => Math.max(2.5, v.max * 1.05) },
    ],
    series: [
      {
        type: 'line',
        name: '外資期貨淨留倉(多-空)',
        data: oiNet,
        showSymbol: false,
        xAxisIndex: 0,
        yAxisIndex: 0,
        lineStyle: { width: 2, color: '#6a1b9a' },
        areaStyle: { opacity: 0.08 },
      },
      {
        type: 'line',
        name: '外資選擇權 PCR',
        data: pcr,
        showSymbol: false,
        xAxisIndex: 1,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: '#ef6c00' },
        markLine: {
          symbol: 'none',
          silent: true,
          animation: false,
          label: {
            show: true,
            position: 'insideStartTop',
            distance: 4,
            fontSize: 11,
            fontWeight: 600,
            backgroundColor: 'rgba(255,255,255,0.92)',
            padding: [2, 5],
            borderRadius: 3,
            formatter: (p) => pcrMarks.find((m) => Math.abs(m.y - p.value) < 1e-6)?.text || '',
          },
          data: pcrMarks.map((m) => ({
            yAxis: m.y,
            lineStyle: { type: 'dashed', color: m.color, width: 1.2 },
            label: { color: m.color },
          })),
        },
      },
    ],
  }
}

/** PCR × 日K：上方加高 K 棒，下方 PCR 門檻線，用來對照高／低 PCR 後走勢 */
export function chipPcrKlineOption(series, windowSize = 120) {
  const n = Math.max(1, Math.min(windowSize || 120, series.date?.length || 120))
  const dates = last(series.date, n)
  const start = (series.date || []).length - dates.length
  const candle = dates.map((_, i) => {
    const idx = start + i
    return [series.open?.[idx], series.close?.[idx], series.low?.[idx], series.high?.[idx]]
  })
  const ma20 = last(series.ma20 || [], n)
  const pcr = last(series.opt_foreign_pcr || [], n)
  // 依視窗內高低收緊 Y 軸，讓振幅拉長（不要被大空白壓扁）
  const highs = candle.map((c) => c[3]).filter((v) => v != null && !Number.isNaN(Number(v))).map(Number)
  const lows = candle.map((c) => c[2]).filter((v) => v != null && !Number.isNaN(Number(v))).map(Number)
  let kMin
  let kMax
  if (highs.length && lows.length) {
    const hi = Math.max(...highs)
    const lo = Math.min(...lows)
    const pad = Math.max((hi - lo) * 0.04, hi * 0.001)
    kMin = lo - pad
    kMax = hi + pad
  }
  const pcrMarks = [
    { y: 0.88, color: '#2e7d32', text: 'P20 0.88' },
    { y: 1.85, color: '#ef6c00', text: 'P80 1.85' },
    { y: 2.25, color: '#c62828', text: 'P90 2.25' },
  ]
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, type: 'scroll' },
    dataZoom: [
      ...linkedDataZoom(2, { bottom: 10, height: 26, dates, left: 72, right: 36 }),
      // 右側振幅滑桿靠內，避免蓋住 PCR 標籤
      ...priceAxisZoom(0, { top: '7%', height: '50%', right: 8, width: 16 }),
    ],
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      // K 線區加高，振幅較好讀；底部留給軸日期 + 時間軸
      { left: 72, right: 36, top: 40, height: '52%' },
      { left: 72, right: 36, top: '60%', bottom: 70 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, show: false },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: timeAxisLabel(dates) },
    ],
    yAxis: [
      {
        gridIndex: 0,
        scale: true,
        name: 'TX 日K',
        splitNumber: 6,
        min: kMin,
        max: kMax,
        axisLabel: { hideOverlap: true },
      },
      {
        gridIndex: 1,
        name: 'PCR',
        scale: true,
        min: (v) => Math.min(0.45, (v.min ?? 1) * 0.9),
        max: (v) => Math.max(2.7, (v.max ?? 2) * 1.1),
        axisLabel: { hideOverlap: true },
      },
    ],
    series: [
      {
        type: 'candlestick',
        name: 'TX 日K',
        data: candle,
        xAxisIndex: 0,
        yAxisIndex: 0,
        ...CANDLE_STYLE,
        barWidth: '80%',
        barMinWidth: 9,
        barMaxWidth: 30,
      },
      {
        type: 'line',
        name: 'MA20',
        data: ma20,
        xAxisIndex: 0,
        yAxisIndex: 0,
        showSymbol: false,
        lineStyle: { color: '#ff9800', width: 2 },
      },
      {
        type: 'line',
        name: '外資 PCR',
        data: pcr,
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: false,
        lineStyle: { width: 2.2, color: '#ef6c00' },
        markLine: {
          symbol: 'none',
          silent: true,
          animation: false,
          // 標籤放圖內左側，避免被右側 Y 軸縮放條遮住
          label: {
            show: true,
            position: 'insideStartTop',
            distance: 4,
            fontSize: 11,
            fontWeight: 600,
            backgroundColor: 'rgba(255,255,255,0.92)',
            padding: [2, 5],
            borderRadius: 3,
            formatter: (p) => pcrMarks.find((m) => Math.abs(m.y - p.value) < 1e-6)?.text || '',
          },
          data: pcrMarks.map((m) => ({
            yAxis: m.y,
            lineStyle: { type: 'dashed', color: m.color, width: 1.2 },
            label: { color: m.color },
          })),
        },
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(198, 40, 40, 0.06)' },
          data: [[{ yAxis: 1.85 }, { yAxis: 99 }]],
        },
      },
    ],
  }
}

export function monthlyKOption(monthDev, _todayHigh, _monthlyClose, threshold = 0.8, windowSize = 90) {
  const n = Math.max(1, Math.min(windowSize || 90, (monthDev.date || []).length || 90))
  const dates = last(monthDev.date || [], n)
  const start = (monthDev.date || []).length - dates.length
  const candle = dates.map((_, i) => {
    const idx = start + i
    return [monthDev.open[idx], monthDev.close[idx], monthDev.low[idx], monthDev.high[idx]]
  })
  const ma20Line = last(monthDev.ma20 || monthDev.monthly_close || [], n)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: linkedDataZoom(2, { bottom: 4, dates }),
    grid: [
      { left: 56, right: 24, top: 40, height: '54%' },
      { left: 56, right: 24, top: '64%', bottom: 70 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, show: false },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: timeAxisLabel(dates) },
    ],
    yAxis: [
      { gridIndex: 0, scale: true, name: '點位', splitNumber: 5 },
      { gridIndex: 1, name: '乖離%' },
    ],
    series: [
      {
        type: 'candlestick',
        name: '日K（含夜盤）',
        data: candle,
        xAxisIndex: 0,
        yAxisIndex: 0,
        ...CANDLE_STYLE,
      },
      {
        type: 'line',
        name: 'MA20（月線）',
        data: ma20Line,
        xAxisIndex: 0,
        yAxisIndex: 0,
        showSymbol: false,
        lineStyle: { color: '#ff9800', width: 2 },
      },
      {
        type: 'line',
        name: '最高 vs MA20 乖離%',
        data: last(monthDev.deviation_pct || [], n),
        xAxisIndex: 1,
        yAxisIndex: 1,
        showSymbol: false,
        lineStyle: { color: '#1976d2', width: 2 },
        markLine: {
          symbol: 'none',
          data: [
            { yAxis: threshold, lineStyle: { type: 'dotted', color: '#d32f2f' } },
            { yAxis: -threshold, lineStyle: { type: 'dotted', color: '#d32f2f' } },
          ],
        },
      },
    ],
  }
}

export function fmt(n, digits = 0) {
  if (n == null || Number.isNaN(n)) return '—'
  return Number(n).toLocaleString('zh-TW', { maximumFractionDigits: digits, minimumFractionDigits: digits })
}

export function pct(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

export function bannerClass(score) {
  // 0–100 Risk Score
  if (score >= 85) return 'red'
  if (score >= 70) return 'red'
  if (score >= 55) return 'orange'
  if (score >= 40) return 'yellow'
  return 'green'
}
