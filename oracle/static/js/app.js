/**
 * app.js — top-level application: init, refresh, health, toast.
 * This is the entry point; all other modules must be loaded before it.
 */

// ── Toast notifications ───────────────────────────────────────────────────────

function showToast(message, type = 'info') {
  const existing = document.getElementById('oracle-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'oracle-toast';
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  // Animate in
  requestAnimationFrame(() => toast.classList.add('visible'));

  // Auto-dismiss
  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 300);
  }, 2800);
}

// ── Health check ──────────────────────────────────────────────────────────────

async function checkHealth() {
  const { data, error } = await API.health();
  if (error) return; // silent — dots just stay grey

  const setDot = (id, ok) => {
    const el = document.getElementById(id);
    if (el) el.className = 'hdot ' + (ok ? 'ok' : 'err');
  };

  setDot('h-ollama', data.ollama?.ok);
  setDot('h-news',   data.news_api?.ok);
  setDot('h-poly',   data.polymarket?.ok);
  setDot('h-kalshi', data.kalshi?.ok);
}

setInterval(checkHealth, 60_000);

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  const { data, error } = await API.init();

  if (error) {
    showToast('Failed to load — is the server running?', 'error');
    showError('markets-body', 'Server unreachable', 'init');
    showError('kalshi-body',  'Server unreachable', 'init');
    showError('news-body',    'Server unreachable', 'init');
    return;
  }

  State.chatHistory  = data.history  || [];
  State.watchlistSlugs = new Set((data.watchlist || []).map(w => w.slug));

  renderMarkets(data.poly_markets   || [], 'markets-body', 'poly');
  renderMarkets(data.kalshi_markets || [], 'kalshi-body',  'kalshi');
  renderNews(data.headlines || []);
  renderAlerts(data.alerts || []);
  renderShifts(data.shifts || []);
  renderHistory();
  setLastUpdated(data.last_updated);
  handleFiredAlerts(data.fired_alerts || []);
  checkHealth();
}

// ── Refresh ───────────────────────────────────────────────────────────────────

async function refreshData() {
  const btn = document.getElementById('refresh-btn');
  btn.textContent = '⟳ ...';
  btn.disabled = true;

  const { data, error } = await API.refresh();
  if (error) {
    showToast('Refresh failed: ' + error, 'error');
  } else {
    renderMarkets(data.poly_markets   || [], 'markets-body', 'poly');
    renderMarkets(data.kalshi_markets || [], 'kalshi-body',  'kalshi');
    renderNews(data.headlines || []);
    renderShifts(data.shifts  || []);
    setLastUpdated(data.last_updated);
    handleFiredAlerts(data.fired_alerts || []);
    showToast('Data refreshed');
  }

  btn.textContent = '⟳ REFRESH';
  btn.disabled = false;
}

// ── Boot ──────────────────────────────────────────────────────────────────────
startClock();
init();
