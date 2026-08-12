<script setup>
import { computed, ref, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import BaseChart from '../components/BaseChart.vue'
import { breadthOption, fmt } from '../charts/options'

const store = useDashboardStore()
const chartDates = computed(() => store.chartDatesFrom(store.series?.date || []))
const windowSize = computed(() => chartDates.value.length)

const availableDates = computed(() => {
  const dates = store.series?.date || []
  const ups = store.series?.up || []
  return dates.filter((_, i) => ups[i] != null)
})

const selectedDate = ref('')

watch(
  chartDates,
  (dates) => {
    if (!dates.length) {
      selectedDate.value = ''
      return
    }
    if (!dates.includes(selectedDate.value)) {
      const withBreadth = availableDates.value.filter((d) => dates.includes(d))
      selectedDate.value = withBreadth.at(-1) || dates.at(-1)
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

const up = computed(() => at('up'))
const down = computed(() => at('down'))
const ad = computed(() => at('ad_ratio'))
const limitUp = computed(() => at('limit_up'))
const limitDown = computed(() => at('limit_down'))
const close = computed(() => at('close'))
const scoreE = computed(() => {
  const v = at('score_E')
  return v == null ? 0 : Number(v)
})
const breadth20 = computed(() => at('breadth20'))
const hasBreadth = computed(() => up.value != null)

const chartOption = computed(() => breadthOption(store.series, selectedDate.value, windowSize.value))

function pickDate(date) {
  if (typeof date === 'string' && chartDates.value.includes(date)) {
    selectedDate.value = date
  }
}

function onChartClick(params) {
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
  <h2 class="page-title">市場廣度：台指期 vs 上漲／下跌家數</h2>
  <p class="page-cap">
    Phase1 廣度僅計 E1（AD）／E2（breadth20）。不要只看台指；指數漲、大多數股票跌 = 背離。
    可點圖切換日期。
  </p>

  <div class="toolbar">
    <label>
      查看日期
      <select v-model="selectedDate">
        <option v-for="d in chartDates" :key="d" :value="d">
          {{ d }}{{ availableDates.includes(d) ? '' : '（無廣度）' }}
        </option>
      </select>
    </label>
    <button type="button" class="linkish" :disabled="!availableDates.length" @click="selectedDate = availableDates.at(-1)">
      跳到最新
    </button>
  </div>

  <div v-if="!chartDates.length" class="banner yellow">尚無資料。</div>
  <template v-else>
    <div class="metrics">
      <div class="metric"><div class="label">選定日期</div><div class="value" style="font-size:18px">{{ selectedDate }}</div></div>
      <div class="metric"><div class="label">台指收盤</div><div class="value">{{ fmt(close) }}</div></div>
      <div class="metric"><div class="label">上漲家數</div><div class="value">{{ hasBreadth ? fmt(up) : '—' }}</div></div>
      <div class="metric"><div class="label">下跌家數</div><div class="value">{{ hasBreadth ? fmt(down) : '—' }}</div></div>
      <div class="metric"><div class="label">漲跌比</div><div class="value">{{ ad == null ? '—' : ad.toFixed(2) }}</div></div>
      <div class="metric"><div class="label">漲停</div><div class="value">{{ hasBreadth ? fmt(limitUp) : '—' }}</div></div>
      <div class="metric"><div class="label">跌停</div><div class="value">{{ hasBreadth ? fmt(limitDown) : '—' }}</div></div>
      <div class="metric"><div class="label">E Breadth</div><div class="value" :class="scoreE > 0 ? 'on' : 'off'">{{ scoreE.toFixed(0) }} / 30</div></div>
      <div class="metric"><div class="label">breadth20</div><div class="value">{{ breadth20 == null ? '—' : Number(breadth20).toFixed(1) }}</div></div>
    </div>
    <div v-if="!hasBreadth" class="banner yellow">此日尚無上市廣度資料。</div>
    <div v-else-if="scoreE >= 8" class="banner red">廣度風險偏高（E≥8）：AD／breadth20 偏弱。</div>
    <div v-else-if="ad != null && ad >= 0.55" class="banner green">廣度健康：上漲家數明顯多於下跌。</div>
    <div v-else class="banner yellow">廣度中性，持續觀察漲跌比是否與指數背離。</div>
  </template>

  <div class="card">
    <BaseChart height="640px" :option="chartOption" @chart-click="onChartClick" @axis-click="onAxisClick" />
  </div>
</template>
