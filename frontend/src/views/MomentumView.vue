<script setup>
import { computed, ref, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import BaseChart from '../components/BaseChart.vue'
import HelpTip from '../components/HelpTip.vue'
import { fmt, kdOption, macdOption, priceVolumeOption } from '../charts/options'

const KD_DIV_HELP =
  '實際意義：價格創出新高，但 KD（動能）沒有同步創高，代表上漲力道開始跟不上價格。\n' +
  '這是「短期動能衰退」的警戒訊號，適合開始留意減碼，不是單獨出場或做空的理由。\n' +
  '本系統判定：近 20 日價格創新高，但 K 值高點未跟上，且收盤仍在高檔附近。'

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

const close = computed(() => at('close'))
const volume = computed(() => at('volume'))
const volRatio = computed(() => at('vol_ratio'))
const hist = computed(() => at('macd_hist'))
const prevHist = computed(() => {
  const i = selectedIndex.value
  if (i < 1) return null
  return store.series.macd_hist?.[i - 1] ?? null
})
const k = computed(() => at('k'))
const d = computed(() => at('d'))
const scoreC = computed(() => {
  const v = at('score_C')
  return v == null ? 0 : Number(v)
})
const scoreD = computed(() => {
  const v = at('score_D')
  return v == null ? 0 : Number(v)
})

const histChange = computed(() => {
  if (hist.value == null || prevHist.value == null) return '—'
  return hist.value < prevHist.value ? '縮小' : '放大'
})

const priceOpt = computed(() => priceVolumeOption(store.series, selectedDate.value, windowSize.value))
const macdOpt = computed(() => macdOption(store.series, selectedDate.value, windowSize.value))
const kdOpt = computed(() => kdOption(store.series, selectedDate.value, windowSize.value))

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
  <h2 class="page-title">價量 × MACD × KD</h2>
  <p class="page-cap">
    對應 Group C（Momentum）／D（PriceVolume）。單獨 KD 死叉或 MACD 翻綠不要當成出場訊號。
    可點任一圖表切換日期查看當日數據。
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
    <div class="metric"><div class="label">成交量</div><div class="value">{{ fmt(volume) }}</div></div>
    <div class="metric">
      <div class="label">量比（/20日均量）</div>
      <div class="value">{{ volRatio == null ? '—' : `${volRatio.toFixed(2)}x` }}</div>
    </div>
    <div class="metric">
      <div class="label">MACD 柱</div>
      <div class="value">{{ hist == null ? '—' : hist.toFixed(1) }}</div>
    </div>
    <div class="metric">
      <div class="label">K / D</div>
      <div class="value">{{ k == null ? '—' : `${k.toFixed(1)} / ${d == null ? '—' : d.toFixed(1)}` }}</div>
    </div>
    <div class="metric">
      <div class="label">柱狀變化</div>
      <div class="value" style="font-size:18px">{{ histChange }}</div>
    </div>
  </div>

  <div class="metrics">
    <div class="metric">
      <div class="label">C Momentum</div>
      <div class="value" :class="scoreC > 0 ? 'on' : 'off'">{{ scoreC.toFixed(0) }} / 15</div>
    </div>
    <div class="metric">
      <div class="label">D PriceVolume</div>
      <div class="value" :class="scoreD > 0 ? 'on' : 'off'">{{ scoreD.toFixed(0) }} / 15</div>
    </div>
    <div class="metric">
      <div class="label">
        KD 說明
        <HelpTip :text="KD_DIV_HELP" />
      </div>
      <div class="value" style="font-size:16px">見圖</div>
    </div>
  </div>

  <div class="card">
    <h3>C／D 代表什麼？</h3>
    <p class="page-cap">
      兩者都是<strong>多單風險加分</strong>（越高越偏「該留意減碼」），不是 KD 線的 K／D。
      分數低＝當天動能／價量沒有明顯轉弱訊號。
    </p>
    <table>
      <thead>
        <tr><th>組別</th><th>看什麼</th><th>主要加分條件</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>C Momentum<br /><span class="muted">上限 15</span></td>
          <td>漲勢動能有沒有變弱</td>
          <td>
            RSI 過熱（65→80+）＋1～7；
            K&gt;80（死叉再多加）＋1／＋4；
            MACD 柱連縮＋2～5；
            MACD&lt;0＋7；
            價創新高但動能沒跟上（背離）最多＋8
          </td>
        </tr>
        <tr>
          <td>D PriceVolume<br /><span class="muted">上限 15</span></td>
          <td>有沒有殺得很兇／量價轉差</td>
          <td>
            下跌＋爆量（量比&gt;1.5／2）＋5／＋8；
            創新高但量能萎縮＋3；
            單日急跌（−2%／−3%／−4%）＋4／＋7／＋10
          </td>
        </tr>
      </tbody>
    </table>
    <p class="page-cap" style="margin-top:10px">
      <strong>怎麼讀當日分數：</strong>
      C=1 常見於「只有 K 偏高、其餘未轉弱」；
      D=0 代表當天沒有爆量下跌或急殺。
      單獨 KD 死叉／MACD 翻綠不要當成出場或做空理由，要和其他組與 Exposure 一起看。
    </p>
  </div>

  <div class="card">
    <h3>價格 + 成交量</h3>
    <p class="page-cap">健康多頭：價格 ↑ 且成交量 ↑。危險：高檔爆量換手，再出現爆量長黑。</p>
    <BaseChart :option="priceOpt" height="520px" @chart-click="onChartClick" @axis-click="onAxisClick" />
  </div>

  <div class="card">
    <h3>MACD 柱狀體</h3>
    <p class="page-cap">指數還在創新高，但柱狀體連續縮小 = 上漲動能衰退。這是減碼確認，不是直接做空。</p>
    <BaseChart :option="macdOpt" height="360px" @chart-click="onChartClick" @axis-click="onAxisClick" />
  </div>

  <div class="card">
    <h3>KD</h3>
    <p class="page-cap">價格創新高、KD 沒創新高 = 頂背離。KD &gt; 80 可以維持很久，強勢市場不要只因為超買就出場。</p>
    <BaseChart :option="kdOpt" height="360px" @chart-click="onChartClick" @axis-click="onAxisClick" />
  </div>
</template>
