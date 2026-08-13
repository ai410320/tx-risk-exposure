<script setup>
import { onMounted, onUnmounted, watch } from 'vue'
import { useDashboardStore } from './stores/dashboard'
import { CHART_RANGE_OPTIONS } from './charts/range'

const store = useDashboardStore()
let timer = null

function restartTimer() {
  if (timer) clearInterval(timer)
  if (store.refreshSeconds > 0) {
    timer = setInterval(() => store.load(), store.refreshSeconds * 1000)
  }
}

onMounted(async () => {
  await store.load()
  restartTimer()
})

watch(() => store.refreshSeconds, restartTimer)
watch(
  () => store.lookback,
  () => {
    store.load()
  },
)
onUnmounted(() => timer && clearInterval(timer))
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <h1>台指轉折點</h1>
      <div class="sub">Risk 0～100 → Exposure</div>
      <nav class="nav">
        <router-link to="/">總覽／Risk</router-link>
        <router-link to="/chip">籌碼／法人</router-link>
        <router-link to="/outlook">走勢判讀</router-link>
        <router-link to="/trend">趨勢與乖離</router-link>
        <router-link to="/momentum">價量與動能</router-link>
        <router-link to="/breadth">市場廣度</router-link>
        <router-link to="/external">外部市場</router-link>
        <router-link to="/monthly">日K／MA20乖離</router-link>
      </nav>
      <div class="settings">
        <label>圖表區間</label>
        <div class="range-btns">
          <button
            v-for="opt in CHART_RANGE_OPTIONS"
            :key="opt.id"
            type="button"
            class="range-btn"
            :class="{ active: store.chartRange === opt.id }"
            @click="store.setChartRange(opt.id)"
          >
            {{ opt.label }}
          </button>
        </div>
        <p class="hint">只影響圖表顯示長度；可再拖圖下方滑桿微調。</p>

        <label>計算用歷史天數</label>
        <input
          :value="store.lookback"
          type="number"
          min="250"
          max="1200"
          step="5"
          @change="store.setLookback($event.target.value)"
        />
        <p class="hint">預設 365 天（約一年）。愈長首次載入愈慢；圖表顯示長度請用上方區間。</p>

        <label>自動刷新（秒）</label>
        <select v-model.number="store.refreshSeconds">
          <option :value="0">關閉</option>
          <option :value="30">30</option>
          <option :value="60">60</option>
          <option :value="120">120</option>
        </select>
        <button :disabled="store.loading" @click="store.load()">
          {{ store.loading ? '載入中…' : '立即刷新' }}
        </button>
      </div>
    </aside>
    <main class="content">
      <div v-if="store.error" class="error">
        {{ store.error }}
        <br />
        若是線上版：第一次開可能要等 1～2 分鐘（冷啟動抓資料），請按「立即刷新」再試。
        <br />
        本機請確認後端 `uvicorn server:app --reload --port 8000` 已啟動。
      </div>
      <div v-else-if="!store.data && store.loading" class="loading">
        正在載入台指期、廣度與外部市場…（線上首次可能較久）
      </div>
      <router-view v-else-if="store.data" />
    </main>
  </div>
</template>
