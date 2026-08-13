<script setup>
import { computed, ref, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import BaseChart from '../components/BaseChart.vue'
import { chipOiPcrOption, chipPcrKlineOption, chipSpotFutOption } from '../charts/options'
import { useNarrow } from '../charts/useNarrow'

const store = useDashboardStore()
const narrow = useNarrow()
const chartDates = computed(() => store.chartDatesFrom(store.series?.date || []))
const windowSize = computed(() => chartDates.value.length)
const chip = computed(() => store.data?.chip || {})

const availableDates = computed(() => {
  const dates = store.series?.date || []
  const spot = store.series?.spot_foreign_net || []
  return dates.filter((_, i) => spot[i] != null)
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
      const withChip = availableDates.value.filter((d) => dates.includes(d))
      selectedDate.value = withChip.at(-1) || dates.at(-1)
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

function fmtNum(v, digits = 1) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toFixed(digits)
}

function signed(v, digits = 1, unit = '') {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  const s = n > 0 ? '+' : ''
  return `${s}${n.toFixed(digits)}${unit}`
}

const scoreH = computed(() => Number(at('score_H') ?? 0))
const label = computed(() => String(at('chip_label') || chip.value.chip_label || '—'))
const bias = computed(() => Number(at('chip_bias') ?? chip.value.chip_bias ?? 0))

const biasTone = computed(() => {
  if (bias.value >= 1.5) return '多頭確認'
  if (bias.value >= 0.5) return '偏多'
  if (bias.value <= -1.5) return '空頭確認'
  if (bias.value <= -0.5) return '偏空'
  return '中性'
})

const spotOpt = computed(() => chipSpotFutOption(store.series, windowSize.value, narrow.value))
const oiOpt = computed(() => chipOiPcrOption(store.series, windowSize.value, narrow.value))
const pcrKOpt = computed(() => chipPcrKlineOption(store.series, windowSize.value, narrow.value))
</script>

<template>
  <h2 class="page-title">籌碼：三大法人現貨 × 期選留倉</h2>
  <p class="page-cap">
    補上「誰在買／誰在避險」。計入 Risk 的 <strong>Group H（上限 10）</strong>：偏空籌碼會提高多單風險分。
    資料為交易所日結算後才齊，盤中仍看前一交易日；單位：現貨＝億元、期貨／選擇權＝口數。
  </p>

  <div class="toolbar">
    <label>
      查看日期
      <select v-model="selectedDate">
        <option v-for="d in chartDates" :key="d" :value="d">{{ d }}</option>
      </select>
    </label>
    <button
      type="button"
      class="linkish"
      :disabled="!availableDates.length"
      @click="selectedDate = availableDates.at(-1)"
    >
      跳到最新籌碼日
    </button>
  </div>

  <div class="banner" :class="bias >= 0.5 ? 'green' : bias <= -0.5 ? 'orange' : ''">
    {{ selectedDate }}｜判讀：{{ biasTone }}｜H {{ scoreH.toFixed(0) }}/10
    <span class="muted">｜{{ label }}</span>
  </div>

  <div class="metrics">
    <div class="metric">
      <div class="label">外資現貨淨買超</div>
      <div class="value" :class="Number(at('spot_foreign_net')) >= 0 ? 'on' : 'off'">
        {{ signed(at('spot_foreign_net'), 1, ' 億') }}
      </div>
    </div>
    <div class="metric">
      <div class="label">外資現貨近5日</div>
      <div class="value">{{ signed(at('spot_foreign_net_5d'), 1, ' 億') }}</div>
    </div>
    <div class="metric">
      <div class="label">投信現貨淨買超</div>
      <div class="value">{{ signed(at('spot_trust_net'), 1, ' 億') }}</div>
    </div>
    <div class="metric">
      <div class="label">自營現貨淨買超</div>
      <div class="value">{{ signed(at('spot_dealer_net'), 1, ' 億') }}</div>
    </div>
    <div class="metric">
      <div class="label">外資期貨當日淨買賣</div>
      <div class="value">{{ signed(at('fut_foreign_deal_net'), 0, ' 口') }}</div>
    </div>
    <div class="metric">
      <div class="label">外資期貨淨留倉</div>
      <div class="value">{{ signed(at('fut_foreign_oi_net'), 0, ' 口') }}</div>
    </div>
    <div class="metric">
      <div class="label">外資期貨淨OI變化</div>
      <div class="value" :class="Number(at('fut_foreign_oi_chg')) >= 0 ? 'on' : 'off'">
        {{ signed(at('fut_foreign_oi_chg'), 0, ' 口') }}
      </div>
    </div>
    <div class="metric">
      <div class="label">外資選擇權 PCR</div>
      <div class="value">{{ fmtNum(at('opt_foreign_pcr'), 2) }}</div>
    </div>
  </div>

  <div class="card">
    <h3>怎麼分析（實務讀法）</h3>
    <table>
      <thead>
        <tr><th>組合</th><th>含義</th><th>操作暗示</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>外資現貨買＋期貨淨多增</td>
          <td>現貨與衍生性同向偏多</td>
          <td>偏多確認，可提高曝險信心</td>
        </tr>
        <tr>
          <td>外資現貨賣＋期貨淨空增</td>
          <td>現貨與衍生性同向偏空</td>
          <td>偏空確認，多單宜減碼（H 易上升）</td>
        </tr>
        <tr>
          <td>現貨買、期貨淨空增</td>
          <td>常見「買現貨＋期貨避險」</td>
          <td>多頭力道打折，勿解讀成單邊猛多</td>
        </tr>
        <tr>
          <td>現貨賣、期貨淨多增</td>
          <td>可能回補空單、或現貨調節</td>
          <td>方向雜訊大，等連續 2～3 日</td>
        </tr>
        <tr>
          <td>投信穩健買超</td>
          <td>中長線資金偏支撐</td>
          <td>下跌時可當緩衝，不單獨當進場訊號</td>
        </tr>
        <tr>
          <td>PCR ≥ 1.85（≈歷史 P80）</td>
          <td>賣權相對買權偏多（避險偏重）</td>
          <td>後續報酬／勝率偏弱、回撤偏深（2018–2026 回測）</td>
        </tr>
        <tr>
          <td>PCR ≥ 2.25（≈歷史 P90）</td>
          <td>極端避險／恐慌區</td>
          <td>後續更差；過程波動大，勿單看 PCR 抄底</td>
        </tr>
        <tr>
          <td>PCR ≤ 0.88（≈歷史 P20）</td>
          <td>買權配置偏多、避險偏少</td>
          <td>後續偏強機率較高；若已在高檔仍要防擁擠</td>
        </tr>
      </tbody>
    </table>
    <p class="page-cap" style="margin-top:10px">
      記法：先看<strong>同向</strong>（現貨＋期貨一起多／一起空）才提高權重；出現「現貨買／期貨空」先當避險，不要加碼過頭。
      籌碼是<strong>輔助確認</strong>，仍以 Risk／Exposure／均線結構為主。
      PCR 門檻來自 2018-12～2026-08 外資 PCR 分位與 TX 後續報酬回測（1.85≈P80、2.25≈P90、0.88≈P20）；舊經驗值 1.3 接近中位數，已停用。
    </p>
  </div>

  <div class="card chart-card">
    <h3>價格 × 外資現貨 × 期貨淨OI變化</h3>
    <p class="page-cap">紅柱＝買超／淨多增；綠柱＝賣超／淨空增（台股慣例）。</p>
    <BaseChart :option="spotOpt" />
  </div>

  <div class="card chart-card">
    <h3>外資期貨淨留倉 × 選擇權 PCR</h3>
    <p class="page-cap">淨留倉＝多方口數−空方口數；PCR＝外資賣權多方OI／買權多方OI。右側虛線為回測門檻（P20／P80／P90）。</p>
    <BaseChart :option="oiOpt" height="460px" />
  </div>

  <div class="card chart-card">
    <h3>日K × PCR（對照勝率）</h3>
    <p class="page-cap">
      上看 TX 日K（加高蠟燭＋MA20），下看 PCR。粉紅底為 PCR≥P80（1.85）偏高避險區：回測裡這區之後 20 日勝率／報酬偏弱。
      可拖時間軸對照「PCR 衝高後 K 線怎麼走」。
    </p>
    <BaseChart :option="pcrKOpt" height="720px" />
  </div>

  <div class="card">
    <h3>與總覽 Exposure 策略怎麼比？能整合嗎？</h3>
    <p class="page-cap">
      「日勝率」對只調多單曝險、不放空的策略幾乎一樣（漲跌符號不變），所以要比的是
      <strong>夏普、最大回撤、大跌日少虧多少</strong>。
    </p>
    <table>
      <thead>
        <tr><th>策略</th><th>重點（約 2024-06～2026-08 樣本）</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>總覽 Exposure（Risk）</td>
          <td>跟得上減碼，但回撤仍偏深；夏普約 1.3</td>
        </tr>
        <tr>
          <td>純籌碼部位</td>
          <td>夏普更高（約 1.9）、回撤較浅；報酬仍低於滿倉持有</td>
        </tr>
        <tr>
          <td>兩者取嚴（已整合）</td>
          <td>夏普最好、回撤最浅；大跌日平均虧損明顯小於滿倉</td>
        </tr>
        <tr>
          <td>Exposure 高 + 籌碼偏多</td>
          <td>後 20 日勝率約 77%（同向確認最有用）</td>
        </tr>
      </tbody>
    </table>
    <p class="page-cap" style="margin-top:10px">
      <strong>已整合進 Exposure：</strong>籌碼偏空／PCR≥P80 會當硬上限（偏空確認≤50%、偏空≤70%、PCR極端≤35%、PCR偏高≤70%），與 Risk 規則取較嚴。
      實務：Risk 決定何時減，籌碼決定「能不能加回去／還要不要再砍一刀」。
    </p>
  </div>

  <div class="card">
    <h3>Group H 計分（多單風險）</h3>
    <p class="page-cap">
      外資現貨大賣、近5日累賣、期貨淨空大增、現貨賣＋期貨空同向、PCR 偏高 → 加分（上限 10）。
      目前選定日 H＝{{ scoreH.toFixed(0) }}。
    </p>
  </div>
</template>
