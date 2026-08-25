<script setup>
import { computed, ref, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import BaseChart from '../components/BaseChart.vue'
import {
  biasClass,
  classifyOutlook,
  rowFromSeries,
} from '../outlook/regime'
import { buildPlaybook } from '../outlook/playbook'
import { fmt, pct } from '../charts/options'
import { CHART_RANGE_OPTIONS, linkedDataZoom, timeAxisLabel } from '../charts/range'

const REVIEW_TRADING_DAYS =
  CHART_RANGE_OPTIONS.find((o) => o.id === '6M')?.tradingDays || 132

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
    if (!dates.includes(selectedDate.value)) selectedDate.value = dates.at(-1)
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

const row = computed(() => rowFromSeries(store.series, selectedIndex.value))
const outlook = computed(() => (row.value ? classifyOutlook(row.value) : null))
const playbook = computed(() =>
  row.value ? buildPlaybook(row.value, store.series, selectedIndex.value) : null,
)

const liveRow = computed(() => {
  const s = store.series
  if (!s?.date?.length) return null
  const base = rowFromSeries(s, s.date.length - 1)
  const live = store.data?.live_risk
  if (!base || !live?.price) return base
  return {
    ...base,
    close: live.price,
    high: live.price,
    // 其餘指標沿用近收；短線用即時價對 MA 判斷
  }
})
const liveOutlook = computed(() => (liveRow.value ? classifyOutlook(liveRow.value) : null))
const livePlaybook = computed(() => {
  if (!liveRow.value || !store.series?.date?.length) return null
  return buildPlaybook(liveRow.value, store.series, store.series.date.length - 1)
})

function outlookRowsFrom(start) {
  const s = store.series
  if (!s?.date?.length) return []
  const from = Math.max(0, start)
  return s.date.slice(from).map((date, i) => {
    const idx = from + i
    const o = classifyOutlook(rowFromSeries(s, idx))
    return {
      date,
      close: s.close[idx],
      path: o.path.title,
      code: o.path.code,
      long: o.long.label,
      short: o.short.label,
      risk: s.risk_score?.[idx] ?? s.score?.[idx],
      exposure: s.exposure?.[idx],
    }
  })
}

const pathHistory = computed(() => {
  const s = store.series
  if (!s?.date?.length) return []
  return outlookRowsFrom(s.date.length - (windowSize.value || 120))
})

const option = computed(() => {
  const hist = pathHistory.value
  const dates = hist.map((h) => h.date)
  const closes = hist.map((h) => h.close)
  const pathCodeToY = {
    bull_extend: 5,
    bull_digest: 4,
    bull_pullback: 3,
    repair_rally: 4,
    chop: 3,
    weakening: 2,
    bear_bounce: 2,
    bear_base: 1,
    bear_extend: 0,
    unclear: 3,
  }
  const pathY = hist.map((h) => pathCodeToY[h.code] ?? 3)
  const sel = selectedDate.value
  return {
    tooltip: {
      trigger: 'axis',
      formatter(params) {
        const i = params?.[0]?.dataIndex
        if (i == null || !hist[i]) return ''
        const h = hist[i]
        return [
          h.date,
          `走法：${h.path}`,
          `長線：${h.long}`,
          `短線：${h.short}`,
          `收盤：${fmt(h.close)}`,
          `Risk：${h.risk == null ? '—' : Number(h.risk).toFixed(1)}`,
        ].join('<br/>')
      },
    },
    legend: { top: 0 },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: linkedDataZoom(2),
    grid: [
      { left: 56, right: 28, top: 40, height: '42%' },
      { left: 56, right: 28, top: '56%', bottom: 40 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, show: false },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: timeAxisLabel(dates) },
    ],
    yAxis: [
      { type: 'value', scale: true, gridIndex: 0, name: '點位' },
      {
        type: 'value',
        min: -0.2,
        max: 5.2,
        interval: 1,
        gridIndex: 1,
        name: '走法',
        axisLabel: {
          formatter(v) {
            const map = {
              5: '多頭延續',
              4: '整理／反彈',
              3: '回檔／震盪',
              2: '轉弱／反彈',
              1: '空方震盪',
              0: '空頭延續',
            }
            return map[v] || ''
          },
        },
      },
    ],
    series: [
      {
        name: '收盤',
        type: 'line',
        data: closes,
        showSymbol: true,
        symbolSize: 5,
        xAxisIndex: 0,
        yAxisIndex: 0,
        lineStyle: { width: 2, color: '#1565c0' },
        markLine: sel
          ? {
              symbol: 'none',
              label: { formatter: String(sel).slice(5) },
              data: [{ xAxis: sel }],
              lineStyle: { type: 'dashed', color: '#1976d2' },
            }
          : undefined,
      },
      {
        name: '走法強度',
        type: 'line',
        step: 'middle',
        data: pathY,
        showSymbol: false,
        xAxisIndex: 1,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: '#6a1b9a' },
        areaStyle: { color: 'rgba(106,27,154,0.08)' },
      },
    ],
  }
})

function pickDate(date) {
  if (typeof date === 'string' && chartDates.value.includes(date)) selectedDate.value = date
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

const recent = computed(() => {
  const s = store.series
  if (!s?.date?.length) return []
  return outlookRowsFrom(s.date.length - REVIEW_TRADING_DAYS).reverse()
})
</script>

<template>
  <h2 class="page-title">走勢判讀</h2>
  <p class="page-cap">
    以「長期持有多單」為預設：先判斷現在是上升／盤整／回檔／轉弱，再給續抱或等回加碼的參考帶。
    點位是均線與近高低推導的參考，不是保證進出場價；曝險仍以 Risk → Exposure 為準。
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

  <template v-if="playbook && outlook">
    <div class="banner" :class="biasClass(playbook.phase.tone)">
      {{ selectedDate }}｜情勢：{{ playbook.phase.label }}｜操作：{{ playbook.stance.label }}
    </div>
    <p class="page-cap">{{ playbook.phase.plain }}</p>
    <p class="page-cap">走法：{{ outlook.path.title }} — {{ outlook.path.summary }}</p>
    <p v-if="outlook.path.note" class="page-cap" style="color:#b45309">{{ outlook.path.note }}</p>

    <div class="metrics">
      <div class="metric">
        <div class="label">情勢</div>
        <div class="value" :class="biasClass(playbook.phase.tone)" style="font-size:18px">{{ playbook.phase.label }}</div>
      </div>
      <div class="metric">
        <div class="label">操作建議</div>
        <div class="value" style="font-size:18px">{{ playbook.stance.label }}</div>
      </div>
      <div class="metric">
        <div class="label">長線</div>
        <div class="value" :class="biasClass(outlook.long.bias)" style="font-size:18px">{{ outlook.long.label }}</div>
      </div>
      <div class="metric">
        <div class="label">短線</div>
        <div class="value" :class="biasClass(outlook.short.bias)" style="font-size:18px">{{ outlook.short.label }}</div>
      </div>
      <div class="metric"><div class="label">收盤</div><div class="value">{{ fmt(at('close')) }}</div></div>
      <div class="metric"><div class="label">vs MA20</div><div class="value">{{ pct(at('dev20')) }}</div></div>
      <div class="metric"><div class="label">vs MA60</div><div class="value">{{ pct(at('dev60')) }}</div></div>
      <div class="metric"><div class="label">Risk</div><div class="value">{{ at('risk_score') == null ? '—' : Number(at('risk_score')).toFixed(1) }}</div></div>
      <div class="metric">
        <div class="label">Exposure</div>
        <div class="value">{{ at('exposure') == null ? '—' : `${Math.round(at('exposure') * 100)}%` }}</div>
      </div>
    </div>

    <div class="card playbook-card">
      <h3>長期偏多操作劇本</h3>
      <p>{{ playbook.stance.detail }}</p>
      <div class="grid-2" style="margin-top:12px">
        <div>
          <h4 class="playbook-h">適合進場／加碼</h4>
          <p>{{ playbook.entry }}</p>
        </div>
        <div>
          <h4 class="playbook-h">出場／降碼參考</h4>
          <p>{{ playbook.exit }}</p>
        </div>
      </div>
      <div class="metrics" style="margin-top:12px">
        <div v-for="lv in playbook.levels" :key="lv.key" class="metric">
          <div class="label">{{ lv.label }}</div>
          <div class="value" style="font-size:16px">{{ lv.value }}</div>
        </div>
      </div>
      <ul class="playbook-list">
        <li v-for="(item, i) in playbook.doNow" :key="i">{{ item }}</li>
      </ul>
      <p class="page-cap" style="margin-top:8px">
        盤整期原則：不追高、不翻空；回測 MA20～MA60 且收盤站穩才加；日收破 MA60 先降碼。
      </p>
    </div>

    <div class="grid-2">
      <div class="card">
        <h3>長線依據</h3>
        <p>{{ outlook.long.detail }}</p>
        <p class="page-cap" style="margin-top:8px">
          MA20 {{ fmt(at('ma20')) }}｜MA60 {{ fmt(at('ma60')) }}｜MA120 {{ fmt(at('ma120')) }}｜MA240 {{ fmt(at('ma240')) }}
        </p>
      </div>
      <div class="card">
        <h3>短線依據</h3>
        <p>{{ outlook.short.detail }}</p>
        <p class="page-cap" style="margin-top:8px">
          A {{ Number(at('score_A') || 0).toFixed(0) }}｜B {{ Number(at('score_B') || 0).toFixed(0) }}｜
          D {{ Number(at('score_D') || 0).toFixed(0) }}｜回撤
          {{ at('dd_from_high20') == null ? '—' : `${(Number(at('dd_from_high20')) * 100).toFixed(1)}%` }}
        </p>
      </div>
    </div>
  </template>

  <div v-if="livePlaybook && liveOutlook && store.data?.live_risk" class="card">
    <h3>即時價下的走勢（試算）</h3>
    <p class="page-cap">
      用即時 {{ fmt(store.data.live_risk.price) }}（{{ store.quote?.session_label }}）重判情勢；長線結構仍多半沿用近收。
    </p>
    <div class="banner" :class="biasClass(livePlaybook.phase.tone)" style="margin-bottom:10px">
      情勢：{{ livePlaybook.phase.label }}｜操作：{{ livePlaybook.stance.label }}
    </div>
    <div class="metrics">
      <div class="metric">
        <div class="label">即時走法</div>
        <div class="value" style="font-size:16px">{{ liveOutlook.path.title }}</div>
      </div>
      <div class="metric">
        <div class="label">長線</div>
        <div class="value" :class="biasClass(liveOutlook.long.bias)" style="font-size:16px">{{ liveOutlook.long.label }}</div>
      </div>
      <div class="metric">
        <div class="label">短線</div>
        <div class="value" :class="biasClass(liveOutlook.short.bias)" style="font-size:16px">{{ liveOutlook.short.label }}</div>
      </div>
    </div>
    <p class="page-cap">{{ livePlaybook.entry }}</p>
  </div>

  <div class="card">
    <h3>走法對照表</h3>
    <table>
      <thead><tr><th>長線</th><th>短線</th><th>綜合走法</th><th>白話</th></tr></thead>
      <tbody>
        <tr><td>偏多</td><td>偏多</td><td>多頭延續</td><td>續漲機率較高，仍看過熱／Risk</td></tr>
        <tr><td>偏多</td><td>偏空</td><td>長多短空（回檔）</td><td>多頭修正，不是立刻翻空</td></tr>
        <tr><td>偏多</td><td>震盪</td><td>多頭震盪整理</td><td>漲後消化，等均線跟上</td></tr>
        <tr><td>中性</td><td>偏多</td><td>反彈修復</td><td>反彈中，看能否站回 MA60</td></tr>
        <tr><td>中性</td><td>震盪</td><td>震盪整理</td><td>方向不清，降頻操作</td></tr>
        <tr><td>中性</td><td>偏空</td><td>轉弱觀察</td><td>有轉空疑慮</td></tr>
        <tr><td>偏空</td><td>偏多</td><td>空頭反彈</td><td>反彈先當空方回補</td></tr>
        <tr><td>偏空</td><td>震盪</td><td>空方震盪</td><td>築底或續跌未定</td></tr>
        <tr><td>偏空</td><td>偏空</td><td>空頭延續</td><td>反彈偏弱處理</td></tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h3>走法時間序列</h3>
    <p class="page-cap">上：收盤；下：走法強度（越高越偏多頭延續）。點圖可切換日期。</p>
    <BaseChart :option="option" height="560px" @chart-click="onChartClick" @axis-click="onAxisClick" />
  </div>

  <div class="card">
    <h3>走法回看（近半年）</h3>
    <p class="page-cap">約 {{ recent.length }} 個交易日，由新到舊。點列可切換上方判讀日期。</p>
    <div class="outlook-review">
      <table>
        <thead><tr><th>日期</th><th>收盤</th><th>長線</th><th>短線</th><th>走法</th><th>Risk</th></tr></thead>
        <tbody>
          <tr
            v-for="r in recent"
            :key="r.date"
            class="click-row"
            :class="{ active: r.date === selectedDate }"
            @click="pickDate(r.date)"
          >
            <td>{{ r.date }}</td>
            <td>{{ fmt(r.close) }}</td>
            <td>{{ r.long }}</td>
            <td>{{ r.short }}</td>
            <td>{{ r.path }}</td>
            <td>{{ r.risk == null ? '—' : Number(r.risk).toFixed(1) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.outlook-review {
  max-height: min(70vh, 640px);
  overflow: auto;
  -webkit-overflow-scrolling: touch;
}
.outlook-review thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #fff;
}
.playbook-card h4.playbook-h {
  margin: 0 0 6px;
  font-size: 13px;
  color: #475569;
}
.playbook-list {
  margin: 12px 0 0;
  padding-left: 1.2em;
  color: #334155;
  line-height: 1.55;
}
</style>
