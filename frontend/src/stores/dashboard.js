import { defineStore } from 'pinia'
import { fetchDashboard } from '../api/client'
import { resolveWindowSize, sliceDates } from '../charts/range'

const savedRange = typeof localStorage !== 'undefined' ? localStorage.getItem('chartRange') : null

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    lookback: 800,
    percentile: 90,
    /** 圖表顯示區間：1M / 3M / 6M / 1Y / ALL */
    chartRange: savedRange && ['1M', '3M', '6M', '1Y', 'ALL'].includes(savedRange) ? savedRange : '6M',
    refreshSeconds: 60,
    loading: false,
    error: '',
    data: null,
    updatedAt: '',
  }),
  getters: {
    series: (state) => state.data?.series || null,
    snapshot: (state) => state.data?.snapshot || null,
    quote: (state) => state.data?.quote || null,
    monthly: (state) => state.data?.monthly || null,
    seriesWindow() {
      const dates = this.series?.date || []
      return resolveWindowSize(this.chartRange, dates.length)
    },
  },
  actions: {
    setChartRange(id) {
      this.chartRange = id
      try {
        localStorage.setItem('chartRange', id)
      } catch {
        /* ignore */
      }
    },
    chartDatesFrom(dates) {
      return sliceDates(dates || [], this.chartRange)
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        this.data = await fetchDashboard(this.lookback, this.percentile)
        this.updatedAt = new Date().toLocaleString('zh-TW')
      } catch (err) {
        this.error = err.message || String(err)
      } finally {
        this.loading = false
      }
    },
  },
})
