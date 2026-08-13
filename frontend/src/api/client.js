async function fetchJson(url, { retries = 2, timeoutMs = 120000 } = {}) {
  let lastErr
  for (let attempt = 0; attempt <= retries; attempt++) {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), timeoutMs)
    try {
      const res = await fetch(url, { signal: ctrl.signal })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `API 錯誤 ${res.status}`)
      }
      return await res.json()
    } catch (err) {
      lastErr = err
      const aborted = err?.name === 'AbortError'
      const msg = aborted
        ? `請求逾時（>${Math.round(timeoutMs / 1000)}s），雲端冷啟動可能仍在抓資料`
        : err.message || String(err)
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)))
        continue
      }
      throw new Error(msg)
    } finally {
      clearTimeout(timer)
    }
  }
  throw lastErr
}

export async function fetchDashboard(lookback) {
  const params = new URLSearchParams({ lookback })
  return fetchJson(`/api/dashboard?${params}`, { retries: 2, timeoutMs: 120000 })
}

export async function fetchRealtime() {
  return fetchJson('/api/realtime', { retries: 1, timeoutMs: 20000 })
}
