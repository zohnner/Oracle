/**
 * api.js — centralised fetch wrapper.
 * Every backend call goes through here so error handling is consistent.
 */

/**
 * Fetch JSON from a URL. Returns { data, error }.
 * Never throws — callers check error instead.
 */
async function apiFetch(url, options = {}) {
  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      return { data: null, error: `HTTP ${res.status}: ${text || res.statusText}` };
    }
    const data = await res.json();
    return { data, error: null };
  } catch (err) {
    // Network failure, JSON parse error, etc.
    return { data: null, error: err.message || 'Network error' };
  }
}

// ── Convenience wrappers ──────────────────────────────────────────────────────

const API = {
  init:       ()          => apiFetch('/api/init'),
  refresh:    ()          => apiFetch('/api/refresh', { method: 'POST' }),
  clear:      ()          => apiFetch('/api/clear',   { method: 'POST' }),

  chat: (message, history, stream = true) =>
    fetch('/api/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ message, history, stream }),
    }),

  markets:  (q, source) => apiFetch(`/api/markets?source=${source || 'all'}${q ? '&q=' + encodeURIComponent(q) : ''}`),
  news:     (q)         => apiFetch(`/api/news${q    ? '?q=' + encodeURIComponent(q) : ''}`),
  rss:      (q)         => apiFetch(`/api/rss${q     ? '?q=' + encodeURIComponent(q) : ''}`),
  reddit:   (q)         => apiFetch(`/api/reddit${q  ? '?q=' + encodeURIComponent(q) : ''}`),
  calendar: (q, days)   => apiFetch(`/api/calendar${q ? '?q=' + encodeURIComponent(q) : (days ? '?days=' + days : '')}`),
  shifts:   (limit)     => apiFetch(`/api/shifts${limit ? '?limit=' + limit : ''}`),
  health:   ()          => apiFetch('/api/health'),
  sentiment:(q)         => apiFetch(`/api/reddit/sentiment?q=${encodeURIComponent(q)}`),
  rabbithole:(q)        => apiFetch(`/api/rabbithole?q=${encodeURIComponent(q)}`),

  alerts: {
    list:   ()     => apiFetch('/api/alerts'),
    add:    (body) => apiFetch('/api/alerts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    delete: (id)   => apiFetch(`/api/alerts/${id}`, { method: 'DELETE' }),
  },

  watchlist: {
    list:   ()     => apiFetch('/api/watchlist'),
    add:    (body) => apiFetch('/api/watchlist', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    delete: (slug) => apiFetch(`/api/watchlist/${encodeURIComponent(slug)}`, { method: 'DELETE' }),
  },
};
