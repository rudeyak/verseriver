const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  poems: {
    list: (params = {}) => {
      const q = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
      )
      return request(`/poems?${q}`)
    },
    get: (id) => request(`/poems/${id}`),
    update: (id, data) => request(`/poems/${id}`, { method: 'PATCH', body: data }),
    delete: (id) => request(`/poems/${id}`, { method: 'DELETE' }),
    fetch: (id) => request(`/poems/${id}/fetch`, { method: 'POST' }),
  },
  sources: {
    list: () => request('/sources'),
    add: (data) => request('/sources', { method: 'POST', body: data }),
    update: (id, data) => request(`/sources/${id}`, { method: 'PATCH', body: data }),
    delete: (id) => request(`/sources/${id}`, { method: 'DELETE' }),
    refresh: (id) => request(`/sources/${id}/refresh`, { method: 'POST' }),
  },
  import: (urls) => request('/import', { method: 'POST', body: { urls } }),
  export: () => fetch(`${BASE}/export`).then((r) => r.json()),
  refresh: () => request('/refresh', { method: 'POST' }),
  scrapePending: () => request('/scrape-pending', { method: 'POST' }),
  stats: () => request('/stats'),
}
