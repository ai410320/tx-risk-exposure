<script setup>
import { computed, ref, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import BaseChart from '../components/BaseChart.vue'
import { deviationOption, fmt, pct, trendOption } from '../charts/options'

const store = useDashboardStore()
const chartDates = computed(() => store.chartDatesFrom(store.series?.date || []))
const windowSize = computed(() => chartDates.value.length)

const selectedDate = ref('')

watch(
  chartDates,
  (dates) => {
    if (!dates.length) {
      selectedDate.value = ''
      return
    }
    if (!dates.includes(selectedDate.value)) {
      selectedDate.value = dates.at(-1)
    }
  },
  { immediate: true },
)

const selectedIndex = computed(() => {
  if (!selectedDate.value || !store.series?.date) return -1
  return store.series.date.indexOf(selectedDate.value)
})

function at(key) {
  const i = selectedIndex.value
  if (i < 0) return null
  return store.series[key]?.[i] ?? null
}

function trendLabel(close, ma20, ma60, ma120, ma240) {
  if ([close, ma20, ma60, ma120, ma240].some((v) => v == null || Number.isNaN(v))) return '資料不足'
  if (close > ma20 && ma20 > ma60 && ma60 > ma120 && ma120 > ma240) return '大多頭排列'
  if (close < ma20 && ma20 < ma60 && ma60 < ma120 && ma120 < ma240) return '空頭排列'
  if (close > ma20) return '短多、結構未齊'
  return '短線轉弱'
}

function heatLabel(dev20, dev60) {
  if (dev20 == null || dev60 == null || Number.isNaN(dev20) || Number.isNaN(dev60)) return '—'
  if (dev20 >= 10 || dev60 >= 18) return '極端'
  if (dev20 >= 8 || dev60 >= 15) return '過熱'
  if (dev20 >= 5 || dev60 >= 10) return '強勢'
  if (dev20 >= 0) return '正常多頭'
  return '低於均線'
}

const close = computed(() => at('close'))
const ma20 = computed(() => at('ma20'))
const ma60 = computed(() => at('ma60'))
const ma120 = computed(() => at('ma120'))
const ma240 = computed(() => at('ma240'))
const lastDev20 = computed(() => at('dev20'))
const lastDev60 = computed(() => at('dev60'))
const lastP20 = computed(() => at('dev20_pctile'))
const lastP60 = computed(() => at('dev60_pctile'))
const scoreA = computed(() => Number(at('score_A') ?? 0))
const scoreB = computed(() => Number(at('score_B') ?? 0))
const trend = computed(() => trendLabel(close.value, ma20.value, ma60.value, ma120.value, ma240.value))
const heat = computed(() => heatLabel(lastDev20.value, lastDev60.value))

const trendOpt = computed(() => trendOption(store.series, selectedDate.value, windowSize.value))
const devOpt = computed(() => deviationOption(store.series, selectedDate.value, windowSize.value))

function pickDate(date) {
  if (typeof date === 'string' && chartDates.value.includes(date)) {
    selectedDate.value = date
  }
}

function onTrendChartClick(params) {
  if (params?.componentType && params.componentType !== 'series') return
  let date = params?.name
  if (typeof date !== 'string' && params?.dataIndex != null) {
    date = chartDates.value[params.dataIndex]
  }
  pickDate(date)
}

function onDevChartClick(params) {
  if (params?.componentType && params.componentType !== 'series') return
  let date = params?.name
  if (typeof date !== 'string' && params?.dataIndex != null) {
    date = chartDates.value[params.dataIndex]
  }
  pickDate(date)
}

function onAxisClick({ date }) {
  pickDate(date)
}
</script>

<template>
  <h2 class="page-title">趨勢 × 均線乖離</h2>
  <p class="page-cap">
    對應 Group A（Trend）／B（Extension）。大多頭：收盤 &gt; 20MA &gt; 60MA &gt; 120MA &gt; 240MA。
    可點均線圖或乖離圖切換日期。
  </p>

  <div class="toolbar">
    <label>
      查看日期
      <select v-model="selectedDate">
        <option v-for="d in chartDates" :key="d" :value="d">{{ d }}</option>
      </select>
    </label>
    <button type="button" class="linkish" :disabled="!chartDates.length" @click="selectedDate = chartDates.at(-1)">
      跳到最新
    </button>
  </div>

  <div class="metrics">
    <div class="metric"><div class="label">選定日期</div><div class="value" style="font-size:18px">{{ selectedDate || '—' }}</div></div>
    <div class="metric"><div class="label">台指收盤</div><div class="value">{{ fmt(close) }}</div></div>
    <div class="metric"><div class="label">趨勢結構</div><div class="value" style="font-size:18px">{{ trend }}</div></div>
    <div class="metric"><div class="label">20MA 乖離</div><div class="value">{{ pct(lastDev20) }}</div></div>
    <div class="metric"><div class="label">60MA 乖離</div><div class="value">{{ pct(lastDev60) }}</div></div>
    <div class="metric"><div class="label">乖離狀態</div><div class="value">{{ heat }}</div></div>
    <div class="metric"><div class="label">20MA 百分位</div><div class="value">{{ lastP20 == null ? '—' : `${lastP20.toFixed(0)}%` }}</div></div>
    <div class="metric"><div class="label">60MA 百分位</div><div class="value">{{ lastP60 == null ? '—' : `${lastP60.toFixed(0)}%` }}</div></div>
    <div class="metric"><div class="label">A Trend</div><div class="value" :class="scoreA > 0 ? 'on' : 'off'">{{ scoreA.toFixed(0) }} / 30</div></div>
    <div class="metric"><div class="label">B Extension</div><div class="value" :class="scoreB > 0 ? 'on' : 'off'">{{ scoreB.toFixed(0) }} / 20</div></div>
  </div>

  <div class="card">
    <h3>台指期 vs 均線</h3>
    <BaseChart :option="trendOpt" @chart-click="onTrendChartClick" @axis-click="onAxisClick" />
  </div>
  <div class="card">
    <h3>20 / 60 MA 乖離</h3>
    <BaseChart :option="devOpt" @chart-click="onDevChartClick" @axis-click="onAxisClick" />
  </div>
</template>
