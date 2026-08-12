<script setup>
import { computed, ref, watch } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import BaseChart from '../components/BaseChart.vue'
import { bannerClass, fmt, overviewComboOption, pct } from '../charts/options'

const GROUP_META = [
  ['score_A', 'A', 'Trend', 30, '均線結構／斜率', '短中線轉弱、跌破 MA20／MA60'],
  ['score_B', 'B', 'Extension', 20, '乖離是否過熱', '漲太多、高檔過熱（早減關鍵）'],
  ['score_C', 'C', 'Momentum', 15, 'RSI／KD／MACD', '動能衰退、頂背離、MACD 轉弱'],
  ['score_D', 'D', 'PriceVolume', 15, '當日漲跌＋成交量', '爆量下跌、急殺'],
  ['score_E', 'E', 'Breadth', 30, '上漲／下跌家數', '指數還撐、個股已經弱'],
  ['score_F', 'F', 'Volatility', 15, 'ATR 波動', '波動突然放大'],
  ['score_G', 'G', 'External', 10, '美股／費半／韓半', '外部科技鏈同步轉弱'],
  ['score_H', 'H', 'Chip', 10, '法人現貨／期選留倉', '外資賣超＋期貨淨空增'],
]

const LEVEL_META = {
  LOW: { label: 'LOW', color: '🟢' },
  NORMAL: { label: 'NORMAL', color: '🟢' },
  WARNING: { label: 'WARNING', color: '🟡' },
  HIGH: { label: 'HIGH', color: '🟠' },
  VERY_HIGH: { label: 'VERY HIGH', color: '🔴' },
  EXTREME: { label: 'EXTREME', color: '🔴' },
}

const store = useDashboardStore()
const quote = computed(() => store.quote)
const monthDev = computed(() => store.data?.month_dev_series || {})
const backtest = computed(() => store.data?.backtest || null)
const taiex = computed(() => store.data?.taiex || null)
const liveRisk = computed(() => store.data?.live_risk || null)
const earlyAlerts = computed(() => store.data?.early_alerts || [])

const chartDates = computed(() => {
  const dates = monthDev.value.date?.length ? monthDev.value.date : store.series?.date || []
  return store.chartDatesFrom(dates)
})

const windowSize = computed(() => chartDates.value.length)

/** 最近一筆有 Risk／Exposure 的 series 日期（略過僅補外部市場的空列） */
const lastScoredDate = computed(() => {
  const dates = store.series?.date || []
  const risks = store.series?.risk_score || store.series?.score || []
  const exps = store.series?.exposure || []
  for (let i = dates.length - 1; i >= 0; i -= 1) {
    const hasRisk = risks[i] != null && !Number.isNaN(Number(risks[i]))
    const hasExp = exps[i] != null && !Number.isNaN(Number(exps[i]))
    if (hasRisk || hasExp) return dates[i]
  }
  return dates.at(-1) || ''
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
      // 首頁預設落在有評分的日，避免停在「僅外部／夜盤」空列
      const prefer = lastScoredDate.value
      selectedDate.value = dates.includes(prefer) ? prefer : dates.at(-1)
    }
  },
  { immediate: true },
)

/** Risk／Exposure 專用：選定日若無評分（外部補列），回退到前一評分日 */
const scoredIndex = computed(() => {
  const dates = store.series?.date || []
  const risks = store.series?.risk_score || store.series?.score || []
  const exps = store.series?.exposure || []
  if (!selectedDate.value || !dates.length) return -1
  let best = -1
  for (let i = 0; i < dates.length; i += 1) {
    if (dates[i] > selectedDate.value) break
    const hasRisk = risks[i] != null && !Number.isNaN(Number(risks[i]))
    const hasExp = exps[i] != null && !Number.isNaN(Number(exps[i]))
    if (hasRisk || hasExp) best = i
  }
  return best
})

const scoreAsOf = computed(() => {
  if (!selectedDate.value || scoredIndex.value < 0) return false
  return store.series.date[scoredIndex.value] !== selectedDate.value
})

const scoreAsOfDate = computed(() => {
  if (!scoreAsOf.value || scoredIndex.value < 0) return ''
  return store.series.date[scoredIndex.value]
})

const monthIndex = computed(() => {
  if (!selectedDate.value || !monthDev.value.date) return -1
  return monthDev.value.date.indexOf(selectedDate.value)
})

function atScored(key) {
  const i = scoredIndex.value
  if (i < 0) return null
  return store.series[key]?.[i] ?? null
}

function atMonth(key) {
  const i = monthIndex.value
  if (i < 0) return null
  return monthDev.value[key]?.[i] ?? null
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

function levelFromRisk(risk, levelStr) {
  const key = (levelStr || '').toUpperCase()
  const base = LEVEL_META[key] || (
    risk >= 85 ? LEVEL_META.EXTREME
      : risk >= 70 ? LEVEL_META.VERY_HIGH
        : risk >= 55 ? LEVEL_META.HIGH
          : risk >= 40 ? LEVEL_META.WARNING
            : risk >= 25 ? LEVEL_META.NORMAL
              : LEVEL_META.LOW
  )
  let hint = ''
  if (risk >= 35 && risk < 40) {
    hint = '已接近 WARNING（40）減碼門檻，建議開始留意／分批減碼'
  } else if (risk >= 40 && risk < 48) {
    hint = '已達減碼區，建議把曝險往 70% 靠攏'
  } else if (risk >= 48 && risk < 55) {
    hint = 'WARNING 偏高，Exposure 目標約 50%，勿只看分數覺得「還好」'
  } else if (risk >= 55) {
    hint = '風險偏高，優先看 Exposure，不要只看分數感覺「還好」'
  } else if (risk >= 25) {
    hint = '輕度警戒：可續抱但別加碼過頭'
  } else {
    hint = '風險偏低（相對本系統）'
  }
  return { ...base, hint }
}

function riskReadingLine(risk) {
  if (risk >= 85) return '極端風險區'
  if (risk >= 70) return '高風險區'
  if (risk >= 55) return '明顯風險區'
  if (risk >= 40) return '減碼區（WARNING）'
  if (risk >= 35) return '接近減碼門檻'
  if (risk >= 25) return '輕度警戒'
  return '相對安全區'
}

function actionFromExposure(exp) {
  if (exp == null || Number.isNaN(exp)) return '—'
  const pctExp = Math.round(exp * 100)
  if (pctExp <= 20) return `大幅減碼／出場（曝險 ${pctExp}%）`
  if (pctExp <= 50) return `明顯減碼（曝險 ${pctExp}%）`
  if (pctExp <= 70) return `開始減碼（曝險 ${pctExp}%）`
  if (pctExp < 100) return `輕微減碼（曝險 ${pctExp}%）`
  return `繼續持有（曝險 ${pctExp}%）`
}

const risk = computed(() => {
  const v = atScored('risk_score') ?? atScored('score')
  return v == null ? 0 : Number(v)
})
const exposure = computed(() => {
  const v = atScored('exposure')
  return v == null ? null : Number(v)
})
const riskLevel = computed(() => String(atScored('risk_level') || ''))
const earlyCutB = computed(() => Boolean(atScored('early_cut_B')))
const drawdownCut = computed(() => Boolean(atScored('drawdown_cut')))
const ddFromHigh = computed(() => atScored('dd_from_high20'))
const reboundStage = computed(() => {
  const v = atScored('rebound_stage')
  return v == null ? 0 : Number(v)
})
const washoutRecent = computed(() => Boolean(atScored('washout_recent')))
const meta = computed(() => levelFromRisk(risk.value, riskLevel.value))
const readingLine = computed(() => riskReadingLine(risk.value))
const action = computed(() => actionFromExposure(exposure.value))
const nearWarning = computed(() => risk.value >= 35 && risk.value < 40)
const reboundLabel = computed(() => {
  const s = reboundStage.value
  if (!washoutRecent.value && s <= 0) return null
  if (s >= 4) return '跌深轉折 4/4（結構恢復）'
  if (s >= 3) return '跌深轉折 3/4（MA20 斜率轉正）'
  if (s >= 2) return '跌深轉折 2/4（站回 MA20）'
  if (s >= 1) return '跌深轉折 1/4（強反彈觀察）'
  if (washoutRecent.value) return '洗盤區：等待轉折確認'
  return null
})
const trend = computed(() =>
  trendLabel(atScored('close'), atScored('ma20'), atScored('ma60'), atScored('ma120'), atScored('ma240')),
)
const heat = computed(() => heatLabel(atScored('dev20'), atScored('dev60')))
const ma20Dev = computed(() => atMonth('deviation_pct') ?? atScored('high_ma20_dev'))
const todayHigh = computed(() => atMonth('daily_high') ?? atMonth('high'))
const ma20 = computed(() => atMonth('ma20') ?? atMonth('monthly_close'))

const groups = computed(() =>
  GROUP_META.map(([key, letter, name, cap, watches, means]) => {
    const score = Number(atScored(key) ?? 0)
    return { letter, name, score, cap, watches, means, on: score > 0, pct: cap ? score / cap : 0 }
  }),
)

const topGroups = computed(() =>
  [...groups.value].sort((a, b) => b.pct - a.pct || b.score - a.score).slice(0, 2),
)

const groupReading = computed(() => {
  const sorted = [...groups.value].sort((a, b) => b.score - a.score)
  const b = groups.value.find((g) => g.letter === 'B')
  const a = groups.value.find((g) => g.letter === 'A')
  const d = groups.value.find((g) => g.letter === 'D')
  if (b && b.score >= 16) return '偏「高檔過熱」：B 已觸發早減，先降曝險，不必等總分爆高。'
  if (a && d && a.score >= 12 && d.score >= 5 && (!b || b.score <= 4)) {
    return '偏「跌勢確認」：結構轉弱 + 價量轉差，過熱分已消退。'
  }
  if (a && a.score >= 10 && (!b || b.score <= 6)) return '偏「趨勢轉弱」：先看均線是否續壞，留意破 MA60。'
  if (b && b.score >= 10 && a && a.score <= 8) return '偏「衝高過熱」：還可能再漲，但該開始準備減碼。'
  const lead = sorted.filter((g) => g.score > 0).slice(0, 2).map((g) => g.letter).join('、')
  return lead ? `目前較高的組是 ${lead}：先看總 Exposure，再用這幾組找原因。` : '各組分數都低，代表分項風險訊號不多。'
})

const option = computed(() =>
  overviewComboOption(store.series, monthDev.value, 0.8, selectedDate.value, windowSize.value),
)

const recent = computed(() => {
  const s = store.series
  if (!s?.date?.length) return []
  const n = Math.min(40, s.date.length)
  const start = s.date.length - n
  return Array.from({ length: n }, (_, i) => {
    const idx = start + i
    const risk = s.risk_score?.[idx] ?? s.score?.[idx]
    const exp = s.exposure?.[idx]
    // 略過僅補外部市場、尚無日盤評分的列
    if (risk == null && exp == null) return null
    return {
      date: s.date[idx],
      close: fmt(s.close[idx]),
      risk,
      exposure: exp == null ? '—' : `${Math.round(exp * 100)}%`,
      level: s.risk_level?.[idx] || '',
    }
  })
    .filter(Boolean)
    .reverse()
})

function pickDate(date) {
  if (typeof date === 'string' && chartDates.value.includes(date)) {
    selectedDate.value = date
  }
}

function jumpToLatestScored() {
  const prefer = lastScoredDate.value
  if (prefer && chartDates.value.includes(prefer)) {
    selectedDate.value = prefer
    return
  }
  if (chartDates.value.length) selectedDate.value = chartDates.value.at(-1)
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

function selectRecent(date) {
  pickDate(date)
}

function fmtPct(n, digits = 1) {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(digits)}%`
}
</script>

<template>
  <h2 class="page-title">台指轉折點 × 動態部位（Baseline）</h2>
  <p class="page-cap">
    Risk Score 0～100 → Recommended Exposure。標的：TX；B≥16 早減；回撤累進減碼（8%/12%/18%→70%/50%/25%）；砍倉後需結構恢復才加回；跌深後有轉折提示。點圖或下拉可查看歷史某日。
  </p>

  <div class="toolbar">
    <label>
      查看日期
      <select v-model="selectedDate">
        <option v-for="d in chartDates" :key="d" :value="d">{{ d }}</option>
      </select>
    </label>
    <button type="button" class="linkish" :disabled="!chartDates.length" @click="jumpToLatestScored">
      跳到最新
    </button>
  </div>

  <div class="banner live-quote">
    即時：{{ fmt(quote.price) }}
    <span class="muted">{{ quote.session_label || '—' }}｜{{ quote.quote_time || '—' }}｜{{ quote.source || '—' }}</span>
    <template v-if="liveRisk">
      ｜盤中試算 Risk <strong>{{ liveRisk.risk_score }}</strong>
      → Exposure <strong>{{ liveRisk.exposure_pct }}%</strong>
      <span v-if="liveRisk.day_change_pct != null" class="muted">（較近收 {{ liveRisk.day_change_pct }}%）</span>
    </template>
  </div>

  <div class="banner" :class="bannerClass(risk)">
    {{ meta.color }} {{ meta.label }}（{{ readingLine }}）：{{ scoreAsOf ? `${selectedDate}（評分 ${scoreAsOfDate}）` : selectedDate }} Risk {{ risk.toFixed(1) }}/100
    → Exposure {{ exposure == null ? '—' : `${Math.round(exposure * 100)}%` }}｜{{ action }}
    <span v-if="earlyCutB">｜B 早減觸發</span>
    <span v-if="drawdownCut">｜回撤減碼（距20日高 {{ ddFromHigh == null ? '—' : `${(ddFromHigh * 100).toFixed(1)}%` }}）</span>
    <span v-if="reboundLabel">｜{{ reboundLabel }}</span>
  </div>
  <p v-if="scoreAsOf" class="page-cap" style="color:#b45309">
    選定日 {{ selectedDate }} 尚無日盤 Risk／Exposure（常見於盤中未結算，或僅補了外部市場）。上方分數為前一評分日 {{ scoreAsOfDate }} 的 asof 值；盤中請另看即時試算。
  </p>
  <p v-if="meta.hint" class="page-cap" :style="nearWarning ? 'color:#b45309;font-weight:600' : ''">
    {{ meta.hint }}
  </p>

  <div v-if="earlyAlerts.length" class="card">
    <h3>前瞻／盤中警戒（不用等收盤）</h3>
    <p class="page-cap">用最近收盤結構 + 即時報價試算。7/16→7/17 這類跳升，重點是「前一天已弱」與「當天開盤／盤中就惡化」。</p>
    <ul class="alert-list">
      <li v-for="(a, i) in earlyAlerts" :key="i" :class="a.level">
        <strong>{{ a.title }}</strong>
        <span>{{ a.detail }}</span>
      </li>
    </ul>
  </div>

  <div v-if="liveRisk" class="card">
    <h3>盤中／夜盤試算 Risk（即時）</h3>
    <p class="page-cap">
      目前報價 {{ fmt(quote.price) }}（{{ quote.session_label }} {{ quote.quote_time }}）。
      正式 Risk 仍以日盤收盤列為準；此區用即時價提前警戒。
    </p>
    <div class="metrics">
      <div class="metric"><div class="label">即時價</div><div class="value">{{ fmt(liveRisk.price) }}</div></div>
      <div class="metric"><div class="label">試算 Risk</div><div class="value">{{ liveRisk.risk_score }} / 100</div></div>
      <div class="metric"><div class="label">試算 Exposure</div><div class="value">{{ liveRisk.exposure_pct }}%</div></div>
      <div class="metric"><div class="label">當日漲跌</div><div class="value">{{ liveRisk.day_change_pct == null ? '—' : `${liveRisk.day_change_pct}%` }}</div></div>
      <div class="metric"><div class="label">開盤跳空</div><div class="value">{{ liveRisk.gap_pct == null ? '—' : `${liveRisk.gap_pct}%` }}</div></div>
      <div class="metric"><div class="label">距20日高回撤</div><div class="value">{{ liveRisk.dd_from_high20 == null ? '—' : `${(liveRisk.dd_from_high20 * 100).toFixed(1)}%` }}</div></div>
      <div class="metric"><div class="label">相對 MA20</div><div class="value" :class="liveRisk.below_ma20 ? 'on' : 'off'">{{ liveRisk.below_ma20 ? '跌破' : '之上' }}</div></div>
      <div class="metric"><div class="label">相對 MA60</div><div class="value" :class="liveRisk.below_ma60 ? 'on' : 'off'">{{ liveRisk.below_ma60 ? '跌破' : '之上' }}</div></div>
    </div>
    <p v-if="liveRisk.scenarios?.length" class="page-cap">壓力情境（從現價再跌多少會更糟）：</p>
    <table v-if="liveRisk.scenarios?.length">
      <thead><tr><th>情境</th><th>價位</th><th>約再跌</th></tr></thead>
      <tbody>
        <tr v-for="s in liveRisk.scenarios" :key="s.name">
          <td>{{ s.name }}</td>
          <td>{{ fmt(s.price) }}</td>
          <td>{{ s.need_drop_pct }}%</td>
        </tr>
      </tbody>
    </table>
    <p class="page-cap" style="margin-top:8px">{{ liveRisk.note }}｜基準日 {{ liveRisk.as_of_basis }}</p>
  </div>

  <div class="card">
    <h3>Risk Score 怎麼讀</h3>
    <p class="page-cap">
      Risk 是「多單風險溫度計」（0～100），<strong>不是</strong>明天漲跌預測。
      實務上請先看 <strong>Exposure %</strong>（建議還留幾成），再用分數與 A–G 看原因。
    </p>
    <table>
      <thead>
        <tr><th>分數</th><th>等級</th><th>白話</th><th>建議曝險</th></tr>
      </thead>
      <tbody>
        <tr :class="{ active: risk < 25 }"><td>&lt; 25</td><td>LOW</td><td>相對安心</td><td>約 100%</td></tr>
        <tr :class="{ active: risk >= 25 && risk < 35 }"><td>25～34</td><td>NORMAL</td><td>輕度警戒，別盲目加碼</td><td>約 90%</td></tr>
        <tr :class="{ active: risk >= 35 && risk < 40 }"><td>35～39</td><td>NORMAL↑</td><td>看起來「還好」，但其實已接近減碼門檻</td><td>約 90%（建議開始留意）</td></tr>
        <tr :class="{ active: risk >= 40 && risk < 48 }"><td>40～47</td><td>WARNING</td><td>該認真減碼</td><td>約 70%</td></tr>
        <tr :class="{ active: risk >= 48 && risk < 55 }"><td>48～54</td><td>WARNING↑</td><td>風險升高，Exposure 應明顯下降</td><td>約 50%</td></tr>
        <tr :class="{ active: risk >= 55 && risk < 70 }"><td>55～69</td><td>HIGH</td><td>明顯風險</td><td>約 35%</td></tr>
        <tr :class="{ active: risk >= 70 && risk < 85 }"><td>70～84</td><td>VERY HIGH</td><td>高風險</td><td>約 20%</td></tr>
        <tr :class="{ active: risk >= 85 }"><td>≥ 85</td><td>EXTREME</td><td>極端風險</td><td>約 5%</td></tr>
      </tbody>
    </table>
    <p class="page-cap" style="margin-top:10px">
      記法：<strong>35 分起就要當回事</strong>；40 分起目標約 70%，48 分起約 50%。
      硬規則：B≥16→上限 70%；回撤 ≥8%/12%/18%→上限 70%/50%/25%。砍倉後不可只因 Risk 微降就加回，需結構恢復或跌深轉折確認。
    </p>
  </div>

  <div class="metrics">
    <div class="metric"><div class="label">選定日期</div><div class="value" style="font-size:18px">{{ selectedDate || '—' }}</div></div>
    <div class="metric"><div class="label">Risk Score</div><div class="value">{{ risk.toFixed(1) }} / 100</div></div>
    <div class="metric"><div class="label">Exposure</div><div class="value">{{ exposure == null ? '—' : `${Math.round(exposure * 100)}%` }}</div></div>
    <div class="metric"><div class="label">趨勢結構</div><div class="value" style="font-size:18px">{{ trend }}</div></div>
    <div class="metric"><div class="label">20/60 乖離</div><div class="value">{{ heat }}</div></div>
    <div class="metric"><div class="label">最高 vs MA20</div><div class="value">{{ pct(ma20Dev) }}</div></div>
    <div class="metric"><div class="label">當日最高</div><div class="value">{{ fmt(todayHigh) }}</div></div>
    <div class="metric"><div class="label">MA20</div><div class="value">{{ fmt(ma20) }}</div></div>
    <div class="metric"><div class="label">台指即時</div><div class="value">{{ fmt(quote.price) }}</div></div>
  </div>
  <p class="page-cap">
    最新評分基準日：{{ store.snapshot?.last_date }}｜即時：{{ quote.quote_time }} {{ quote.session_label }}（{{ quote.source }}）
    ｜最高 vs MA20 為獨立警報，不併入 0～100
  </p>

  <div class="card">
    <h3>Risk × Exposure × 日K／MA20</h3>
    <p class="page-cap">
      上：日K（含夜盤）+ MA20；中：最高 vs MA20；下：Risk／Exposure。點圖切換日期。
      底部藍色軸可左右拖時間；K 線區可上下拖動／右側滑桿調振幅（Shift+滾輪也可縮放）。
    </p>
    <BaseChart
      :option="option"
      height="980px"
      @chart-click="onChartClick"
      @axis-click="onAxisClick"
    />
  </div>

  <div class="grid-2">
    <div class="card">
      <h3>分組分數 A–G（{{ selectedDate }}）</h3>
      <p class="page-cap">分數是「風險點」不是績效；越高＝該層越危險。加總後才變成總 Risk。</p>
      <table>
        <thead><tr><th>組</th><th>名稱</th><th>分數</th><th>上限</th><th>在看什麼</th></tr></thead>
        <tbody>
          <tr
            v-for="g in groups"
            :key="g.letter"
            :class="{ active: topGroups.some((t) => t.letter === g.letter) && g.score > 0 }"
          >
            <td>{{ g.letter }}</td>
            <td>{{ g.name }}</td>
            <td :class="g.on ? 'on' : 'off'">{{ g.score.toFixed(0) }}</td>
            <td>{{ g.cap }}</td>
            <td style="font-size:13px;color:#4b5563">{{ g.watches }}</td>
          </tr>
        </tbody>
      </table>
      <p class="page-cap" style="margin-top:10px;color:#b45309">本日解讀：{{ groupReading }}</p>
    </div>
    <div class="card">
      <h3>分組分數怎麼讀</h3>
      <p class="page-cap">
        先看總 Risk／Exposure（要不要減），再看哪一組最高（為什麼）。
        <strong>0 分＝這層沒亮紅燈。</strong>
      </p>
      <table>
        <thead><tr><th>組</th><th>高分代表</th></tr></thead>
        <tbody>
          <tr v-for="g in groups" :key="`hint-${g.letter}`">
            <td>{{ g.letter }} {{ g.name }}</td>
            <td>{{ g.means }}</td>
          </tr>
        </tbody>
      </table>
      <p class="page-cap" style="margin-top:10px">
        常見組合：
        <br />・<strong>B 高、A 低</strong> → 衝高／過熱，偏提早減碼
        <br />・<strong>A／D 高、B 低</strong> → 已轉弱或殺跌中
        <br />・<strong>E／G 高</strong> → 廣度或外部先壞，指數可能晚一步
        <br />・<strong>B≥16</strong> → 不論總分，Exposure 上限直接 70%
      </p>
    </div>
  </div>

  <div class="card">
    <h3>Exposure 規則（§30）</h3>
    <table>
      <thead><tr><th>Risk</th><th>等級</th><th>目標曝險</th></tr></thead>
      <tbody>
        <tr :class="{ active: risk < 20 }"><td>&lt; 20</td><td>LOW</td><td>100%</td></tr>
        <tr :class="{ active: risk >= 20 && risk < 40 }"><td>20～39</td><td>NORMAL</td><td>90%</td></tr>
        <tr :class="{ active: risk >= 40 && risk < 48 }"><td>40～47</td><td>WARNING</td><td>70%</td></tr>
        <tr :class="{ active: risk >= 48 && risk < 55 }"><td>48～54</td><td>WARNING↑</td><td>50%</td></tr>
        <tr :class="{ active: risk >= 55 && risk < 70 }"><td>55～69</td><td>HIGH</td><td>35%</td></tr>
        <tr :class="{ active: risk >= 70 && risk < 85 }"><td>70～84</td><td>VERY HIGH</td><td>20%</td></tr>
        <tr :class="{ active: risk >= 85 }"><td>≥ 85</td><td>EXTREME</td><td>5%</td></tr>
        <tr><td colspan="3">另：B≥16 → Exposure 上限 70%（早減，優先於恢復）</td></tr>
        <tr><td colspan="3">另：回撤 ≥8%→70%、≥12%→50%、≥18%→25%（累進）</td></tr>
        <tr><td colspan="3">另：砍倉後加回需結構恢復（MA20／MA60）或跌深轉折階段確認</td></tr>
        <tr><td colspan="3">跌深轉折：washout 後 強反彈→站 MA20→斜率轉正→站 MA60，分階段提示加回</td></tr>
      </tbody>
    </table>
  </div>

  <div class="grid-2">
    <div class="card">
      <h3>TAIEX 對照（^TWII）</h3>
      <template v-if="taiex">
        <div class="metrics">
          <div class="metric"><div class="label">日期</div><div class="value" style="font-size:16px">{{ taiex.date }}</div></div>
          <div class="metric"><div class="label">收盤</div><div class="value">{{ fmt(taiex.close) }}</div></div>
          <div class="metric"><div class="label">Risk</div><div class="value">{{ taiex.risk_score == null ? '—' : taiex.risk_score.toFixed(1) }}</div></div>
          <div class="metric"><div class="label">Exposure</div><div class="value">{{ taiex.exposure == null ? '—' : `${Math.round(taiex.exposure * 100)}%` }}</div></div>
        </div>
        <p class="page-cap">主序列為 TX；此為現貨指數對照，非下單標的。</p>
      </template>
      <p v-else class="page-cap">尚無 TAIEX 對照資料。</p>
    </div>
    <div class="card">
      <h3>回測摘要（目前視窗）</h3>
      <template v-if="backtest && !backtest.error">
        <div class="metrics">
          <div class="metric"><div class="label">區間</div><div class="value" style="font-size:14px">{{ backtest.start }}～{{ backtest.end }}</div></div>
          <div class="metric"><div class="label">CAGR 持有</div><div class="value" style="font-size:16px">{{ fmtPct(backtest.cagr_bh) }}</div></div>
          <div class="metric"><div class="label">CAGR 策略</div><div class="value" style="font-size:16px">{{ fmtPct(backtest.cagr_strat) }}</div></div>
          <div class="metric"><div class="label">MDD 持有</div><div class="value" style="font-size:16px">{{ fmtPct(backtest.mdd_bh) }}</div></div>
          <div class="metric"><div class="label">MDD 策略</div><div class="value" style="font-size:16px">{{ fmtPct(backtest.mdd_strat) }}</div></div>
        </div>
        <p class="page-cap">{{ backtest.note }}</p>
      </template>
      <p v-else class="page-cap">{{ backtest?.error || '尚無回測結果。' }}</p>
    </div>
  </div>

  <div class="card">
    <h3>近期 Risk／Exposure</h3>
    <p class="page-cap">點列可切換上方選定日期。</p>
    <table>
      <thead><tr><th>日期</th><th>收盤</th><th>Risk</th><th>Exposure</th><th>等級</th></tr></thead>
      <tbody>
        <tr
          v-for="row in recent"
          :key="row.date"
          class="click-row"
          :class="{ active: row.date === selectedDate }"
          @click="selectRecent(row.date)"
        >
          <td>{{ row.date }}</td>
          <td>{{ row.close }}</td>
          <td>{{ row.risk == null ? '—' : Number(row.risk).toFixed(1) }}</td>
          <td>{{ row.exposure }}</td>
          <td>{{ row.level }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  <p class="page-cap">更新時間：{{ store.updatedAt }}｜Risk Score 是機率式風險管理模型，不保證預測最高點。</p>
</template>
