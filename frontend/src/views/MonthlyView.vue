<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import BaseChart from '../components/BaseChart.vue'
import { fmt, monthlyKOption, pct } from '../charts/options'

const store = useDashboardStore()
const threshold = 0.8
const alert = computed(() => Math.abs(store.monthly.deviation_pct) > threshold)
const windowSize = computed(() =>
  store.chartDatesFrom(store.data?.month_dev_series?.date || []).length,
)
const option = computed(() =>
  monthlyKOption(
    store.data.month_dev_series,
    store.monthly.today_high,
    store.monthly.close,
    threshold,
    windowSize.value,
  ),
)
</script>

<template>
  <h2 class="page-title">日K 最高（含夜盤）vs MA20（月線）</h2>
  <p class="page-cap">
    公式：（當天最高含夜盤 − MA20）／MA20 × 100%。
    MA20＝含夜盤日K收盤的 20 日簡單均線（券商俗稱月線）。
  </p>
  <div class="banner" :class="alert ? 'red' : 'green'">
    {{ alert ? `MA20 乖離警示：${pct(store.monthly.deviation_pct)}` : `MA20 乖離正常：${pct(store.monthly.deviation_pct)}` }}
  </div>
  <div class="metrics">
    <div class="metric">
      <div class="label">當日最高（含夜盤）</div>
      <div class="value">{{ fmt(store.monthly.today_high) }}</div>
    </div>
    <div class="metric">
      <div class="label">MA20（月線）</div>
      <div class="value">{{ fmt(store.monthly.ma20 ?? store.monthly.close) }}</div>
    </div>
    <div class="metric">
      <div class="label">乖離率</div>
      <div class="value">{{ pct(store.monthly.deviation_pct) }}</div>
    </div>
    <div class="metric">
      <div class="label">時段</div>
      <div class="value">{{ store.quote.session_label }}</div>
    </div>
  </div>
  <div class="card">
    <h3>日K（含夜盤）</h3>
    <BaseChart height="720px" :option="option" />
  </div>
</template>
