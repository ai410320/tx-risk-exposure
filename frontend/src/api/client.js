export async function fetchDashboard(lookback, percentile) {
  const params = new URLSearchParams({ lookback, percentile })
  const res = await fetch(`/api/dashboard?${params}`)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `API 錯誤 ${res.status}`)
  }
  return res.json()
}

export async function fetchRealtime() {
  const res = await fetch('/api/realtime')
  if (!res.ok) throw new Error(`即時報價失敗 ${res.status}`)
  return res.json()
}
