<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import BaseChart from '../components/BaseChart.vue'
import { externalOption, pct } from '../charts/options'

const store = useDashboardStore()
const windowSize = computed(() => store.chartDatesFrom(store.series?.date || []).length)
const pairs = [
  ['nasdaq_ret5', 'Nasdaq'],
  ['sox_ret5', 'SOX 費半'],
  ['samsung_ret5', 'Samsung'],
  ['hynix_ret5', 'Hynix'],
]
const scoreG = computed(() => {
  const arr = store.series?.score_G
  if (!arr?.length) return 0
  return Number(arr.at(-1) ?? 0)
})
const includeExternal = computed(() => store.snapshot?.include_external !== false)
</script>

<template>
  <h2 class="page-title">外部市場（Group G）</h2>
  <p class="page-cap">
    Nasdaq／SOX／韓半 對台股科技權值特別重要。G 上限 10 分；可用環境變數 INCLUDE_EXTERNAL_GROUP 開關。
    美股多為前一交易日收盤；亞股（韓／日）若已開盤可顯示當日。台指日盤未結算時，圖表仍會補上當日外部值。
  </p>
  <div class="metrics">
    <div class="metric">
      <div class="label">G External</div>
      <div class="value" :class="scoreG > 0 ? 'on' : 'off'">{{ scoreG.toFixed(0) }} / 10</div>
    </div>
    <div class="metric">
      <div class="label">計入 Risk</div>
      <div class="value" style="font-size:18px">{{ includeExternal ? '是' : '否' }}</div>
    </div>
    <div v-for="[key, name] in pairs" :key="key" class="metric">
      <div class="label">{{ name }} 近5日</div>
      <div class="value">{{ pct(store.series[key]?.at(-1)) }}</div>
    </div>
  </div>
  <div v-if="scoreG >= 5" class="banner orange">外部市場偏弱（G≥5），注意科技權值連動。</div>
  <div class="card"><h3>vs 美股指數</h3><BaseChart :option="externalOption(store.series, ['nasdaq','sox','spx'], ['Nasdaq','SOX','S&P500'], windowSize)" /></div>
  <div class="card"><h3>vs 韓股半導體／台積電 ADR</h3><BaseChart :option="externalOption(store.series, ['kospi','samsung','hynix','tsm_adr'], ['KOSPI','Samsung','SK Hynix','台積電ADR'], windowSize)" /></div>
  <div class="card"><h3>vs 日經</h3><BaseChart :option="externalOption(store.series, ['nikkei'], ['Nikkei'], windowSize)" /></div>
</template>
