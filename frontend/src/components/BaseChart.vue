<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import '../charts/register'
import VChart from 'vue-echarts'
import { formatChartDateLabel } from '../charts/range'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '420px' },
})

const emit = defineEmits(['chart-click', 'axis-click'])

const chartRef = ref(null)
const rangeText = ref('')
const showTimebar = ref(false)
let zrHandler = null
let boundChart = null

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
    return
  }
  const dates = readAxisDates(chart)
  if (!dates.length) {
    rangeText.value = ''
    return
  }
  const { start, end } = readZoomPercent(chart)
  // 純日期區間（提示文字放在 HTML 列）
  const last = dates.length - 1
  const i0 = Math.max(0, Math.min(last, Math.round((start / 100) * last)))
  const i1 = Math.max(0, Math.min(last, Math.round((end / 100) * last)))
  const a = formatChartDateLabel(i0, dates[i0], dates)
  const b = formatChartDateLabel(i1, dates[i1], dates)
  rangeText.value = `${a}  ～  ${b}`
}

function onDataZoom() {
  syncZoomRangeLabel()
}

function unbindZr() {
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

const chartHeight = computed(() => props.height)

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

onBeforeUnmount(unbindZr)
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
      <span class="timebar-hint">時間軸（可左右拖動藍色區塊）</span>
      <span class="timebar-range">{{ rangeText || '—' }}</span>
    </div>
  </div>
</template>
