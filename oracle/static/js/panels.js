/**
 * panels.js — render and fetch functions for every data panel.
 * All fetch calls use the API wrapper, all errors are shown to the user.
 */

// ── Helpers ───────────────────────────────────────────────────────────────────

function deltaHtml(delta) {
  if (delta == null) return '';
  if (delta > 0) return `<span class="delta up">▲${delta.toFixed(1)}</span>`;
  if (delta < 0) return `<span class="delta down">▼${Math.abs(delta).toFixed(1)}</span>`;
  return '<span class="delta flat">—</span>';
}

// ── Markets ───────────────────────────────────────────────────────────────────

function renderMarkets(markets, bodyId, source) {
  const body = document.getElementById(bodyId);
  if (!markets.length) { showEmpty(bodyId, 'No markets found'); return; }

  body.innerHTML = markets.map(m => {
    const bars = (m.pairs || []).map(p => {
      const lc  = p.label.toLowerCase();
      const cls = lc.startsWith('yes') ? 'fill-yes' : lc.startsWith('no') ? 'fill-no' : 'fill-other';
      const pc  = p.prob >= 60 ? 'hi' : p.prob <= 30 ? 'lo' : 'mi';
      return `
        <div class="prob-row">
          <div class="prob-label-row">
            <span class="prob-label">${escHtml(p.label)}${deltaHtml(p.delta)}</span>
            <span class="prob-pct ${pc}">${p.prob}%</span>
          </div>
          <div class="prob-bar-track">
            <div class="prob-bar-fill ${cls}" style="width:${p.prob}%"></div>
          </div>
        </div>`;
    }).join('');

    const srcTag   = source === 'kalshi'
      ? '<span class="market-source-tag source-kalshi">KALSHI</span>'
      : '<span class="market-source-tag source-poly">POLYMARKET</span>';
    const linkHref = source === 'kalshi'
      ? `https://kalshi.com/markets/${m.slug}`
      : `https://polymarket.com/event/${m.slug}`;
    const isPinned = State.watchlistSlugs.has(m.slug || '');
    const pinned   = m.pinned || isPinned;

    // Use data-attributes to avoid inline JS escaping nightmares
    return `
      <div class="market-card${pinned ? ' pinned-card' : ''}"
           data-question="${escAttr(m.question)}"
           data-slug="${escAttr(m.slug)}"
           data-source="${source}"
           onclick="askAbout(this.dataset.question)">
        ${srcTag}
        <div class="market-q">${escHtml(m.question)}</div>
        <div class="market-vol">24H VOL: <span>${fmtVol(m.volume24h)}</span></div>
        <div class="prob-bars">${bars}</div>
        <div class="market-actions">
          <div style="display:flex;gap:6px;align-items:center">
            ${m.slug ? `<a class="market-link" href="${linkHref}" target="_blank" onclick="event.stopPropagation()">→ VIEW</a>` : ''}
            <button class="btn-rabbithole"
                    onclick="event.stopPropagation();rabbitHole(this.closest('.market-card').dataset.question)"
                    title="Research this market">🐇 DIG</button>
          </div>
          <button class="btn-pin${isPinned ? ' pinned' : ''}"
                  title="${isPinned ? 'Unpin from watchlist' : 'Pin to watchlist'}"
                  onclick="event.stopPropagation();toggleWatchlist(this)">
            ${isPinned ? '📌' : '📍'}
          </button>
        </div>
      </div>`;
  }).join('');
}

async function searchMarkets() {
  const q = document.getElementById('market-search').value.trim();
  showLoading('markets-body');
  const { data, error } = await API.markets(q, 'poly');
  if (error) { showError('markets-body', error, 'searchMarkets'); return; }
  renderMarkets(data.poly || [], 'markets-body', 'poly');
}

async function searchKalshi() {
  const q = document.getElementById('kalshi-search').value.trim();
  showLoading('kalshi-body');
  const { data, error } = await API.markets(q, 'kalshi');
  if (error) { showError('kalshi-body', error, 'searchKalshi'); return; }
  renderMarkets(data.kalshi || [], 'kalshi-body', 'kalshi');
}

function askAbout(question) {
  document.getElementById('user-input').value = `Tell me more about: "${question}"`;
  document.getElementById('user-input').focus();
}

// ── News ──────────────────────────────────────────────────────────────────────

function renderNews(articles) {
  const body = document.getElementById('news-body');
  if (!articles.length) { showEmpty('news-body', 'No articles found'); return; }
  body.innerHTML = articles.map(a => `
    <div class="news-card">
      <div class="news-meta">
        <span>${escHtml(a.source || '')}</span>
        <span class="news-date">${a.publishedAt || ''}</span>
      </div>
      <a class="news-title" href="${escAttr(a.url)}" target="_blank" rel="noopener">${escHtml(a.title)}</a>
    </div>`).join('');
}

async function searchNews() {
  const q = document.getElementById('news-search').value.trim();
  showLoading('news-body');
  const { data, error } = await API.news(q);
  if (error) { showError('news-body', error, 'searchNews'); return; }
  renderNews(data);
}

// ── RSS ───────────────────────────────────────────────────────────────────────

function renderRSS(items) {
  const body = document.getElementById('rss-body');
  body.dataset.loaded = '1';
  if (!items.length) { showEmpty('rss-body', 'No feeds available'); return; }
  body.innerHTML = items.map(a => `
    <div class="rss-card">
      <div class="rss-meta">
        <span class="rss-source">${escHtml(a.source || '')}</span>
        <span class="rss-date">${a.publishedAt || ''}</span>
      </div>
      <a class="rss-title" href="${escAttr(a.url)}" target="_blank" rel="noopener">${escHtml(a.title)}</a>
    </div>`).join('');
}

async function loadRSS() {
  showLoading('rss-body');
  const { data, error } = await API.rss();
  if (error) { showError('rss-body', error, 'loadRSS'); return; }
  renderRSS(data);
}

async function searchRSS() {
  const q = document.getElementById('rss-search').value.trim();
  showLoading('rss-body');
  const { data, error } = await API.rss(q);
  if (error) { showError('rss-body', error, 'loadRSS'); return; }
  renderRSS(data);
}

// ── Reddit ────────────────────────────────────────────────────────────────────

function renderReddit(posts) {
  const body = document.getElementById('reddit-body');
  body.dataset.loaded = '1';
  if (!posts.length) { showEmpty('reddit-body', 'No posts found'); return; }
  body.innerHTML = posts.map(p => `
    <div class="reddit-card">
      <div class="reddit-meta">
        <span>r/${escHtml(p.subreddit)} · ${Number(p.score).toLocaleString()} pts · ${p.comments} comments</span>
        <span class="sentiment ${p.sentiment}">${p.sentiment.toUpperCase()}</span>
      </div>
      <a class="reddit-title" href="${escAttr(p.url)}" target="_blank" rel="noopener">${escHtml(p.title)}</a>
    </div>`).join('');
}

async function loadReddit() {
  showLoading('reddit-body');
  const { data, error } = await API.reddit();
  if (error) { showError('reddit-body', error, 'loadReddit'); return; }
  renderReddit(data);
}

async function searchReddit() {
  const q = document.getElementById('reddit-search').value.trim();
  if (!q) return;
  showLoading('reddit-body');
  const { data, error } = await API.reddit(q);
  if (error) { showError('reddit-body', error, 'loadReddit'); return; }
  renderReddit(data);
}

// ── Calendar ──────────────────────────────────────────────────────────────────

function renderCalendar(events) {
  const body = document.getElementById('calendar-body');
  body.dataset.loaded = '1';
  if (!events.length) { showEmpty('calendar-body', 'No events found'); return; }
  body.innerHTML = events.map(e => `
    <div class="cal-card${e.past ? ' past' : ''}">
      <div class="cal-icon">${e.icon}</div>
      <div class="cal-info">
        <div class="cal-title">${escHtml(e.title)}</div>
        <div class="cal-meta">
          <span>${e.date}</span>
          <span class="cal-impact ${e.impact}">${e.label}</span>
          <span>${e.impact.toUpperCase()}</span>
        </div>
      </div>
    </div>`).join('');
}

async function loadCalendar() {
  showLoading('calendar-body');
  const { data, error } = await API.calendar();
  if (error) { showError('calendar-body', error, 'loadCalendar'); return; }
  renderCalendar(data);
}

async function searchCalendar() {
  const q = document.getElementById('cal-search').value.trim();
  showLoading('calendar-body');
  const { data, error } = await API.calendar(q);
  if (error) { showError('calendar-body', error, 'loadCalendar'); return; }
  renderCalendar(data);
}

// ── Shifts ────────────────────────────────────────────────────────────────────

function renderShifts(shifts) {
  const body  = document.getElementById('shifts-body');
  const badge = document.getElementById('shifts-badge');
  if (badge) badge.textContent = shifts.length ? `(${shifts.length})` : '';
  if (!shifts.length) {
    showEmpty('shifts-body', 'No shifts detected yet.\nRefreshes flag moves &gt;5pts.');
    return;
  }
  body.innerHTML = shifts.map(s => `
    <div class="shift-card ${s.direction}">
      <div class="shift-arrow">${s.direction === 'up' ? '▲' : '▼'}</div>
      <div class="shift-info">
        <div class="shift-market">${escHtml(s.market)}</div>
        <div class="shift-meta">${escHtml(s.label)} · ${s.source.toUpperCase()} · ${s.timestamp.slice(0, 16).replace('T', ' ')}</div>
      </div>
      <div class="shift-prob ${s.direction}">${s.delta > 0 ? '+' : ''}${s.delta}pts → ${s.prob}%</div>
    </div>`).join('');
}

// ── Alerts ────────────────────────────────────────────────────────────────────

function renderAlerts(alerts) {
  const body  = document.getElementById('alerts-body');
  const badge = document.getElementById('alert-count-tab');
  if (badge) badge.textContent = alerts.length ? `(${alerts.length})` : '';
  if (!alerts.length) { showEmpty('alerts-body', 'No alerts set'); return; }
  body.innerHTML = alerts.map(a => `
    <div class="alert-card${a.fired ? ' fired' : ''}">
      <div class="alert-info">
        <div class="alert-question">${escHtml(a.slug)} · ${escHtml(a.label)} ${a.direction} ${a.threshold}%</div>
        <div class="alert-meta">
          ${a.fired ? '<span class="fired-tag">⚡ FIRED</span>' : ''}
          ${a.created?.slice(0, 10) || ''}
        </div>
      </div>
      <button class="btn-del-alert" onclick="deleteAlert('${escAttr(a.id)}')" title="Delete alert">✕</button>
    </div>`).join('');
}

function handleFiredAlerts(fired) {
  if (!fired.length) return;
  const banner = document.getElementById('alert-banner');
  banner.textContent = `⚠ ${fired.length} ALERT${fired.length > 1 ? 'S' : ''} TRIGGERED — ${(fired[0].market || '').slice(0, 40)}`;
  banner.classList.add('visible');
  if (Notification.permission === 'granted') {
    fired.forEach(f => new Notification('ORACLE Alert', {
      body: `${f.market}\n${f.label}: ${f.current_prob}%`,
    }));
  }
}

async function addAlert() {
  const slug   = document.getElementById('al-slug').value.trim();
  const label  = document.getElementById('al-label').value.trim();
  const thresh = parseFloat(document.getElementById('al-thresh').value);
  const dir    = document.getElementById('al-dir').value;

  if (!slug || !label || isNaN(thresh)) {
    showToast('Fill in all alert fields', 'error'); return;
  }

  const { data, error } = await API.alerts.add({ slug, label, threshold: thresh, direction: dir });
  if (error) { showToast(error, 'error'); return; }

  ['al-slug', 'al-label', 'al-thresh'].forEach(id => document.getElementById(id).value = '');
  const { data: alerts } = await API.alerts.list();
  renderAlerts(alerts || []);
  if (Notification.permission === 'default') Notification.requestPermission();
  showToast('Alert added');
}

async function deleteAlert(id) {
  await API.alerts.delete(id);
  const { data: alerts } = await API.alerts.list();
  renderAlerts(alerts || []);
}

// ── Watchlist ─────────────────────────────────────────────────────────────────

async function toggleWatchlist(btn) {
  const card     = btn.closest('.market-card');
  const slug     = card.dataset.slug;
  const question = card.dataset.question;
  const source   = card.dataset.source;

  if (State.watchlistSlugs.has(slug)) {
    const { error } = await API.watchlist.delete(slug);
    if (error) { showToast(error, 'error'); return; }
    State.watchlistSlugs.delete(slug);
    btn.textContent = '📍';
    btn.classList.remove('pinned');
    btn.title = 'Pin to watchlist';
    card.classList.remove('pinned-card');
    showToast('Unpinned');
  } else {
    const { error } = await API.watchlist.add({ slug, question, source });
    if (error) { showToast(error, 'error'); return; }
    State.watchlistSlugs.add(slug);
    btn.textContent = '📌';
    btn.classList.add('pinned');
    btn.title = 'Unpin from watchlist';
    card.classList.add('pinned-card');
    showToast('Pinned to watchlist');
  }
}

// ── Rabbit Hole ───────────────────────────────────────────────────────────────

async function rabbitHole(question) {
  document.getElementById('user-input').value =
    `Give me a full briefing on: "${question}". Include what Reddit is saying, relevant news, and any upcoming calendar events that could affect this.`;

  showToast('🐇 Digging into rabbit hole…');
  const { data, error } = await API.rabbithole(question);
  if (error) { showToast('Rabbit hole fetch failed: ' + error, 'error'); }

  if (data?.reddit?.posts?.length)  renderReddit(data.reddit.posts);
  if (data?.rss?.length)            renderRSS(data.rss);
  if (data?.calendar?.length)       renderCalendar(data.calendar);

  sendMessage();
}
