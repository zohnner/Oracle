/**
 * chat.js — chat panel: send, stream, history rendering, clear.
 */

// ── History ───────────────────────────────────────────────────────────────────

function renderHistory() {
  if (!State.chatHistory.length) return;
  document.getElementById('welcome')?.remove();
  State.chatHistory.forEach(m => appendMessage(m.role, m.content, false));
  scrollToBottom();
}

function appendMessage(role, content, animate = true) {
  document.getElementById('welcome')?.remove();
  const msgs = document.getElementById('messages');
  const div  = document.createElement('div');
  div.className = `msg ${role === 'user' ? 'user' : 'bot'}`;
  div.innerHTML = `
    <div class="msg-label">${role === 'user' ? 'YOU' : 'ORACLE'}</div>
    <div class="msg-bubble">${escHtml(content)}</div>`;
  if (!animate) div.style.animation = 'none';
  msgs.appendChild(div);
  scrollToBottom();
  return div.querySelector('.msg-bubble');
}

function showTyping() {
  document.getElementById('welcome')?.remove();
  const msgs = document.getElementById('messages');
  const div  = document.createElement('div');
  div.className = 'msg bot';
  div.id = 'typing';
  div.innerHTML = `
    <div class="msg-label">ORACLE</div>
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
  msgs.appendChild(div);
  scrollToBottom();
}

function removeTyping() {
  document.getElementById('typing')?.remove();
}

// ── Send ──────────────────────────────────────────────────────────────────────

async function sendMessage() {
  const input  = document.getElementById('user-input');
  const sendBtn = document.getElementById('send-btn');
  const text   = input.value.trim();
  if (!text || State.isLoading) return;

  State.isLoading = true;
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  appendMessage('user', text);
  showTyping();

  try {
    const res = await API.chat(text, State.chatHistory, true);

    if (!res.ok) {
      removeTyping();
      const { error } = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
      appendMessage('bot', `⚠ Error: ${error}`);
      return;
    }

    removeTyping();
    document.getElementById('welcome')?.remove();
    const msgs   = document.getElementById('messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg bot';
    msgDiv.innerHTML = `<div class="msg-label">ORACLE</div><div class="msg-bubble"></div>`;
    msgs.appendChild(msgDiv);
    const bubble = msgDiv.querySelector('.msg-bubble');

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // hold incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const d = JSON.parse(line.slice(6));
          if (d.token) { bubble.textContent += d.token; scrollToBottom(); }
          if (d.done)  { State.chatHistory = d.history; }
          if (d.error) { bubble.textContent = `⚠ ${d.error}`; }
        } catch { /* malformed SSE line — skip */ }
      }
    }
  } catch (err) {
    removeTyping();
    appendMessage('bot', '⚠ Connection error — is Ollama running? Check the terminal for details.');
    console.error('Chat error:', err);
  } finally {
    State.isLoading = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

async function clearHistory() {
  if (!confirm('Clear all chat history?')) return;
  const { error } = await API.clear();
  if (error) { showToast('Failed to clear history: ' + error, 'error'); return; }
  State.chatHistory = [];
  document.getElementById('messages').innerHTML = `
    <div id="welcome">
      <h2>// ORACLE ONLINE</h2>
      <p>History cleared. What do you want to research?</p>
      <div class="suggestions">
        <button class="suggestion-btn" onclick="suggest(this)">What are the biggest market movers today?</button>
        <button class="suggestion-btn" onclick="suggest(this)">Which bets have the most 24h volume right now?</button>
        <button class="suggestion-btn" onclick="suggest(this)">Compare Polymarket vs Kalshi on the same events</button>
      </div>
    </div>`;
}

// ── Input helpers ─────────────────────────────────────────────────────────────

function suggest(btn) {
  document.getElementById('user-input').value = btn.textContent.trim();
  sendMessage();
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}
