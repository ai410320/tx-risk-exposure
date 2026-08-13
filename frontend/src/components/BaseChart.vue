<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import '../charts/register'
import VChart from 'vue-echarts'
import { formatChartDateLabel } from '../charts/range'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '420px' },
})

const emit = defineEmits(['chart-click', 'axis-click'])

const chartRef = ref(null)
const scrubRef = ref(null)
const rangeText = ref('')
const startLabel = ref('')
const endLabel = ref('')
const showTimebar = ref(false)
const zoomStart = ref(0)
const zoomEnd = ref(100)
const isDragging = ref(false)
const scrubCursor = ref('pointer')
let zrHandler = null
let boundChart = null
let wheelCleanup = null
const isNarrow = ref(false)
let mq = null
let scrubDrag = null

function onMqChange(event) {
  isNarrow.value = Boolean(event.matches)
}

function getChart() {
  const inst = chartRef.value
  if (!inst) return null
  return inst.chart || null
}

function onClick(params) {
  emit('chart-click', params)
}

function unwrap(val) {
  return Array.isArray(val) ? val[0] : val
}

function readZoomPercent(chart) {
  const zooms = chart.getOption()?.dataZoom || []
  let start = 0
  let end = 100
  for (const z of zooms) {
    const type = unwrap(z.type)
    if (type !== 'slider' && type !== 'inside') continue
    if (z.start != null) start = Number(unwrap(z.start))
    if (z.end != null) end = Number(unwrap(z.end))
    if (type === 'slider') break
  }
  return { start, end }
}

function readAxisDates(chart) {
  const axes = chart.getOption()?.xAxis || []
  for (let i = axes.length - 1; i >= 0; i -= 1) {
    const data = unwrap(axes[i]?.data)
    if (Array.isArray(data) && data.length) return data
  }
  // fallback：從 option prop
  const propAxes = props.option?.xAxis
  if (Array.isArray(propAxes)) {
    for (let i = propAxes.length - 1; i >= 0; i -= 1) {
      if (propAxes[i]?.data?.length) return propAxes[i].data
    }
  } else if (propAxes?.data?.length) {
    return propAxes.data
  }
  return []
}

function hasSliderZoom(chart) {
  const zooms = chart.getOption()?.dataZoom || []
  if (zooms.some((z) => unwrap(z.type) === 'slider')) return true
  const propZooms = props.option?.dataZoom
  return Array.isArray(propZooms) && propZooms.some((z) => z.type === 'slider')
}

function syncZoomRangeLabel() {
  const chart = getChart()
  const enabled = Boolean(chart && hasSliderZoom(chart))
  showTimebar.value = enabled
  if (!enabled) {
    rangeText.value = ''
    startLabel.value = ''
    endLabel.value = ''
    return
  }
  const dates = readAxisDates(chart)
  if (!dates.length) {
    rangeText.value = ''
    startLabel.value = ''
    endLabel.value = ''
    return
  }
  const { start, end } = readZoomPercent(chart)
  zoomStart.value = start
  zoomEnd.value = end
  const last = dates.length - 1
  const i0 = Math.max(0, Math.min(last, Math.round((start / 100) * last)))
  const i1 = Math.max(0, Math.min(last, Math.round((end / 100) * last)))
  const a = formatChartDateLabel(i0, dates[i0], dates)
  const b = formatChartDateLabel(i1, dates[i1], dates)
  startLabel.value = a
  endLabel.value = b
  rangeText.value = `${a}  ～  ${b}`
}

const MIN_ZOOM_SPAN = 3

const scrubFillStyle = computed(() => ({
  left: `${zoomStart.value}%`,
  width: `${Math.max(0, zoomEnd.value - zoomStart.value)}%`,
}))

function scrubTrackRect() {
  const track = scrubRef.value?.querySelector?.('.timebar-track')
  return (track || scrubRef.value)?.getBoundingClientRect?.() || null
}

function scrubPercent(clientX) {
  const rect = scrubTrackRect()
  if (!rect) return 0
  return Math.max(0, Math.min(100, ((clientX - rect.left) / Math.max(1, rect.width)) * 100))
}

function applyScrubZoom(start, end) {
  let s = Math.max(0, Math.min(100, start))
  let e = Math.max(0, Math.min(100, end))
  if (e - s < MIN_ZOOM_SPAN) {
    if (scrubDrag?.mode === 'start') s = Math.max(0, e - MIN_ZOOM_SPAN)
    else e = Math.min(100, s + MIN_ZOOM_SPAN)
  }
  zoomStart.value = s
  zoomEnd.value = e
  getChart()?.dispatchAction({ type: 'dataZoom', start: s, end: e })
}

function hitMode(clientX) {
  const rect = scrubTrackRect()
  if (!rect) return 'window'
  const pct = scrubPercent(clientX)
  const start = zoomStart.value
  const end = zoomEnd.value
  const startX = rect.left + (start / 100) * rect.width
  const endX = rect.left + (end / 100) * rect.width
  const hit = isNarrow.value ? 24 : 16
  if (Math.abs(clientX - startX) <= hit && Math.abs(clientX - endX) <= hit) {
    return clientX < (startX + endX) / 2 ? 'start' : 'end'
  }
  if (Math.abs(clientX - startX) <= hit || pct < start) return 'start'
  if (Math.abs(clientX - endX) <= hit || pct > end) return 'end'
  return 'window'
}

function cursorForMode(mode) {
  if (mode === 'start' || mode === 'end') return 'ew-resize'
  if (mode === 'window') return 'grab'
  return 'pointer'
}

function onScrubPointerDown(event) {
  const pct = scrubPercent(event.clientX)
  const mode = hitMode(event.clientX)
  scrubDrag = { mode, originPct: pct, start: zoomStart.value, end: zoomEnd.value }
  isDragging.value = true
  scrubCursor.value = mode === 'window' ? 'grabbing' : 'ew-resize'
  event.currentTarget.setPointerCapture?.(event.pointerId)
  event.preventDefault()
}

function onScrubPointerMove(event) {
  if (!scrubDrag) {
    scrubCursor.value = cursorForMode(hitMode(event.clientX))
    return
  }
  const pct = scrubPercent(event.clientX)
  if (scrubDrag.mode === 'start') {
    applyScrubZoom(Math.min(pct, scrubDrag.end - MIN_ZOOM_SPAN), scrubDrag.end)
    return
  }
  if (scrubDrag.mode === 'end') {
    applyScrubZoom(scrubDrag.start, Math.max(pct, scrubDrag.start + MIN_ZOOM_SPAN))
    return
  }
  const delta = pct - scrubDrag.originPct
  let nextStart = scrubDrag.start + delta
  let nextEnd = scrubDrag.end + delta
  if (nextStart < 0) {
    nextEnd -= nextStart
    nextStart = 0
  }
  if (nextEnd > 100) {
    nextStart -= nextEnd - 100
    nextEnd = 100
  }
  applyScrubZoom(nextStart, nextEnd)
}

function onScrubPointerUp() {
  scrubDrag = null
  isDragging.value = false
}

function onScrubPointerLeave() {
  if (!scrubDrag) scrubCursor.value = 'pointer'
}

function onDataZoom() {
  syncZoomRangeLabel()
}

function unbindWheel() {
  if (wheelCleanup) {
    wheelCleanup()
    wheelCleanup = null
  }
}

function allowPageScroll(chart) {
  unbindWheel()
  const el = chart?.getDom?.()
  if (!el) return
  // zrender 會在 canvas 上 preventDefault(wheel)，導致 hover 圖表時整頁不能捲
  const onWheel = (event) => event.stopImmediatePropagation()
  el.addEventListener('wheel', onWheel, { capture: true, passive: true })
  wheelCleanup = () => el.removeEventListener('wheel', onWheel, { capture: true })
}

function unbindZr() {
  unbindWheel()
  if (boundChart && zrHandler) {
    boundChart.getZr().off('click', zrHandler)
  }
  zrHandler = null
  boundChart = null
}

function bindZr() {
  unbindZr()
  const chart = getChart()
  if (!chart) return
  boundChart = chart
  allowPageScroll(chart)
  zrHandler = (event) => {
    if (event?.target) return
    const point = [event.offsetX, event.offsetY]
    for (let axisIndex = 0; axisIndex < 4; axisIndex += 1) {
      try {
        const result = chart.convertFromPixel({ xAxisIndex: axisIndex }, point)
        if (!Array.isArray(result) || result[0] == null) continue
        const dataIndex = Math.round(result[0])
        const option = chart.getOption()
        const dates = option?.xAxis?.[axisIndex]?.data
        if (!dates || dataIndex < 0 || dataIndex >= dates.length) continue
        emit('axis-click', { date: dates[dataIndex], dataIndex, xAxisIndex: axisIndex })
        return
      } catch {
        // ignore
      }
    }
  }
  chart.getZr().on('click', zrHandler)
  syncZoomRangeLabel()
}

const chartHeight = computed(() => {
  const raw = props.height || '420px'
  if (!isNarrow.value) return raw
  const n = Number.parseInt(String(raw), 10)
  if (!Number.isFinite(n)) return '360px'
  return `${Math.max(300, Math.min(Math.round(n * 0.62), 640))}px`
})

onMounted(() => {
  mq = window.matchMedia('(max-width: 900px)')
  isNarrow.value = mq.matches
  mq.addEventListener('change', onMqChange)
})

watch(
  () => [chartRef.value, props.option],
  async () => {
    await nextTick()
    bindZr()
    // vue-echarts 重設 option 後再同步一次
    setTimeout(syncZoomRangeLabel, 0)
  },
  { flush: 'post' },
)

onBeforeUnmount(() => {
  unbindZr()
  mq?.removeEventListener('change', onMqChange)
})
</script>

<template>
  <div class="chart-wrap">
    <v-chart
      ref="chartRef"
      class="echart"
      :style="{ height: chartHeight, width: '100%' }"
      :option="option"
      autoresize
      @click="onClick"
      @datazoom="onDataZoom"
      @finished="syncZoomRangeLabel"
    />
    <div v-if="showTimebar" class="chart-timebar">
      <div class="timebar-meta">
        <span class="timebar-time">{{ startLabel || '—' }}</span>
        <span class="timebar-sep">/</span>
        <span class="timebar-time is-end">{{ endLabel || '—' }}</span>
      </div>
      <div
        ref="scrubRef"
        class="timebar-scrub"
        :class="{ 'is-dragging': isDragging }"
        :style="{ cursor: scrubCursor }"
        @pointerdown="onScrubPointerDown"
        @pointermove="onScrubPointerMove"
        @pointerup="onScrubPointerUp"
        @pointercancel="onScrubPointerUp"
        @pointerleave="onScrubPointerLeave"
      >
        <div class="timebar-track">
          <div class="timebar-fill" :style="scrubFillStyle" />
        </div>
      </div>
    </div>
  </div>
</template>
