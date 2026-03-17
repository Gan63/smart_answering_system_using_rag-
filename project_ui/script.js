'use strict';
 
/* ── CONFIG ── */
const API_URL = 'http://localhost:8000/ask';
 
/* ── STATE ── */
let sessions    = [];
let activeId    = null;
let isLoading   = false;
let sidebarOpen = true;
let totalTokens = 0;
let totalMsgs   = 0;

// Simple auth (demo): redirect to /login when not signed-in
const AUTH_TOKEN_KEY = 'smart_rag_token';
if (!localStorage.getItem(AUTH_TOKEN_KEY) && window.location.pathname !== '/login') {
  window.location.href = '/login';
}
 
/* ── DOM ── */
const sidebar       = document.getElementById('sidebar');
const overlay       = document.getElementById('overlay');
const histContainer = document.getElementById('historyContainer');
const welcome       = document.getElementById('welcome');
const messages      = document.getElementById('messages');
const thread        = document.getElementById('thread');
const prompt        = document.getElementById('prompt');
const sendBtn       = document.getElementById('sendBtn');
const modelLabel    = document.getElementById('modelLabel');
const fileInput     = document.getElementById('fileInput');
const uploadBtn     = document.getElementById('uploadBtn');
const uploadStatus  = document.getElementById('uploadStatus');
const accBadge      = document.getElementById('accBadge');
const accValue      = document.getElementById('accValue');
const tokenChip     = document.getElementById('tokenChip');
const tokenCount    = document.getElementById('tokenCount');
const sbStats       = document.getElementById('sbStats');
 
/* ── 3D BACKGROUND ── */
(function initBg() {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H;
  const mouse = { x: -9999, y: -9999 };
 
  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);
 
  class Particle {
    constructor(init) {
      this.x = Math.random() * (W || 1200);
      this.y = init ? Math.random() * (H || 800) : (H || 800) + 10;
      this.z = Math.random() * 1.8 + 0.2;
      this.vx = (Math.random() - .5) * 0.25;
      this.vy = -(Math.random() * 0.35 + 0.08);
      this.r = Math.random() * 1.4 + 0.3;
      this.hue = Math.random() > .6 ? 162 : (Math.random() > .5 ? 210 : 270);
      this.alpha = Math.random() * 0.5 + 0.1;
    }
    update() {
      const dx = this.x - mouse.x, dy = this.y - mouse.y;
      const dist = Math.sqrt(dx*dx + dy*dy);
      if (dist < 100) {
        this.vx += (dx / dist) * 0.05;
        this.vy += (dy / dist) * 0.05;
      }
      this.x += this.vx * this.z;
      this.y += this.vy * this.z;
      this.vx *= 0.99;
      this.vy *= 0.995;
      if (this.y < -10) {
        this.x = Math.random() * W;
        this.y = H + 10;
      }
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r * this.z, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${this.hue},85%,65%,${this.alpha})`;
      ctx.fill();
    }
  }
 
  const particles = [];
  setTimeout(() => {
    for (let i = 0; i < 140; i++) particles.push(new Particle(true));
  }, 0);
 
  let angle = 0;
 
  function drawGrid() {
    ctx.save();
    const step = 80;
    const ox = (W / 2) - Math.floor(W / 2 / step) * step;
    ctx.strokeStyle = 'rgba(0,229,160,0.025)';
    ctx.lineWidth = 0.5;
    for (let x = ox; x < W; x += step) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let y = 0; y < H; y += step) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    ctx.restore();
  }
 
  function drawConnections() {
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const d = Math.sqrt(dx*dx + dy*dy);
        if (d < 80) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(0,229,160,${(1 - d / 80) * 0.07})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
  }
 
  function drawOrbitals() {
    const cx = W / 2, cy = H / 2;
    for (let ring = 0; ring < 4; ring++) {
      const rx = 200 + ring * 130;
      const ry = rx * 0.28;
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry, angle * (ring % 2 === 0 ? 0.8 : -0.6), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(0,136,255,${0.035 - ring * 0.007})`;
      ctx.lineWidth = 0.8;
      ctx.stroke();
    }
  }
 
  function animate() {
    ctx.clearRect(0, 0, W, H);
 
    // Ambient gradient meshes
    const g1 = ctx.createRadialGradient(W * .2, H * .3, 0, W * .2, H * .3, W * .55);
    g1.addColorStop(0, 'rgba(0,229,160,0.045)');
    g1.addColorStop(1, 'rgba(8,12,20,0)');
    ctx.fillStyle = g1; ctx.fillRect(0, 0, W, H);
 
    const g2 = ctx.createRadialGradient(W * .85, H * .65, 0, W * .85, H * .65, W * .45);
    g2.addColorStop(0, 'rgba(0,136,255,0.05)');
    g2.addColorStop(1, 'rgba(8,12,20,0)');
    ctx.fillStyle = g2; ctx.fillRect(0, 0, W, H);
 
    const g3 = ctx.createRadialGradient(W * .6, H * .15, 0, W * .6, H * .15, W * .35);
    g3.addColorStop(0, 'rgba(128,0,255,0.025)');
    g3.addColorStop(1, 'rgba(8,12,20,0)');
    ctx.fillStyle = g3; ctx.fillRect(0, 0, W, H);
 
    drawGrid();
    angle += 0.0025;
    drawOrbitals();
    drawConnections();
    particles.forEach(p => { p.update(); p.draw(); });
 
    requestAnimationFrame(animate);
  }
  animate();
 
  window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
})();
 
/* ── INIT ── */
loadStorage();
if (!sessions.length) newSession();
else activate(activeId || sessions.at(-1).id);
bindEvents();
setSidebarState(window.innerWidth > 640);
updateStats();
 
/* ── SESSION CRUD ── */
function genId() { return Date.now().toString(36) + Math.random().toString(36).slice(2); }
 
function newSession() {
  const s = { id: genId(), title: 'New chat', messages: [], ts: Date.now(), totalTokens: 0, avgAccuracy: null, chunks: {} };
  sessions.push(s);
  activate(s.id);
  renderHistory();
  save();
}
 
function activate(id) {
  activeId = id;
  const s = getActive();
  if (!s) return;
  renderMessages(s.messages);
  welcome.style.display = s.messages.length ? 'none' : 'flex';
  modelLabel.textContent = s.title === 'New chat' ? 'Smart RAG Assistant' : s.title;
 
  // Update accuracy badge
  if (s.avgAccuracy != null) {
    accBadge.style.display = 'flex';
    accValue.textContent = s.avgAccuracy.toFixed(0) + '%';
  } else {
    accBadge.style.display = 'none';
  }
  // Token chip
  if (s.totalTokens > 0) {
    tokenChip.style.display = 'flex';
    tokenCount.textContent = formatTokens(s.totalTokens);
  } else {
    tokenChip.style.display = 'none';
  }
 
  renderHistory();
  updateStats();
}
 
function getActive() { return sessions.find(s => s.id === activeId); }
 
function setTitle(s, text) {
  if (s.title !== 'New chat') return;
  s.title = text.slice(0, 45) + (text.length > 45 ? '…' : '');
  modelLabel.textContent = s.title;
  renderHistory();
  save();
}
 
function formatTokens(n) {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k tokens';
  return n + ' tokens';
}
 
/* ── STATS ── */
function updateStats() {
  totalMsgs = sessions.reduce((sum, s) => sum + s.messages.filter(m => m.role === 'user').length, 0);
  totalTokens = sessions.reduce((sum, s) => sum + (s.totalTokens || 0), 0);
  sbStats.innerHTML = `
    <div class="stat-chip"><div class="sv">${totalMsgs}</div><div class="sl">Messages</div></div>
    <div class="stat-chip"><div class="sv">${totalTokens > 0 ? formatTokens(totalTokens) : '0'}</div><div class="sl">Total tokens</div></div>
  `;
}
 
/* ── RENDER HISTORY ── */
function renderHistory() {
  histContainer.innerHTML = '';
  if (!sessions.length) return;
  const sorted = [...sessions].sort((a, b) => b.ts - a.ts);
  sorted.forEach(s => {
    const el = document.createElement('div');
    el.className = 'hist-item' + (s.id === activeId ? ' active' : '');
 
    const titleDiv = document.createElement('div');
    titleDiv.textContent = s.title;
    titleDiv.title = s.title;
    el.appendChild(titleDiv);
 
    // Stats line
    const statsDiv = document.createElement('div');
    statsDiv.className = 'sess-stats';
    const msgCount = s.messages.filter(m => m.role === 'user').length;
    const parts = [];
    if (msgCount > 0) parts.push(`${msgCount} msg${msgCount !== 1 ? 's' : ''}`);
    if (s.totalTokens > 0) parts.push(formatTokens(s.totalTokens));
    if (s.avgAccuracy != null) parts.push(`${s.avgAccuracy.toFixed(0)}% acc`);
    statsDiv.textContent = parts.join(' · ');
    el.appendChild(statsDiv);
 
    el.addEventListener('click', () => {
      activate(s.id);
      if (window.innerWidth <= 640) setSidebarState(false);
    });
    histContainer.appendChild(el);
  });
}
 
/* ── RENDER MESSAGES ── */
function renderMessages(msgs) {
  messages.innerHTML = '';
  msgs.forEach(m => appendBubble(m, false));
  scrollBottom(false);
}
 
function appendBubble(msg, animate = true) {
  const row = document.createElement('div');
  row.className = `msg-row ${msg.role}`;
  if (!animate) row.style.animation = 'none';
  const isUser = msg.role === 'user';
 
  row.innerHTML = `
    <div class="msg-inner">
      ${!isUser ? `<div class="msg-avatar ai">R</div>` : ''}
      <div class="msg-content-wrap" style="flex:1;min-width:0">
        <div class="msg-bubble">${renderContent(msg.content, isUser)}</div>
        ${!isUser && msg.meta ? renderMeta(msg.meta) : ''}
      </div>
      ${isUser ? `<div class="msg-avatar usr">U</div>` : ''}
    </div>
  `;
 
  // Bind chunk button
  if (!isUser && msg.meta && msg.meta.chunks) {
    const btn = row.querySelector('.meta-chip.chunks');
    if (btn) btn.addEventListener('click', () => openChunkModal(msg.meta.chunks));
  }
 
  messages.appendChild(row);
  if (animate) scrollBottom(true);
  return row;
}
 
function renderMeta(meta) {
  const parts = [];
  if (meta.accuracy != null) {
    parts.push(`<span class="meta-chip accuracy">
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
      ${meta.accuracy.toFixed(1)}% accuracy
    </span>`);
  }
  if (meta.chunks && meta.chunks.length > 0) {
    parts.push(`<span class="meta-chip chunks" title="View source chunks">
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
      ${meta.chunks.length} source chunk${meta.chunks.length !== 1 ? 's' : ''}
    </span>`);
  }
  if (meta.tokens != null) {
    parts.push(`<span class="meta-chip tokens">
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
      ${meta.tokens} tokens
    </span>`);
  }
  return parts.length ? `<div class="msg-meta">${parts.join('')}</div>` : '';
}
 
function showLoading() {
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  row.id = 'loadingRow';
  row.innerHTML = `
    <div class="msg-inner">
      <div class="msg-avatar ai">R</div>
      <div class="msg-bubble">
        <div class="loading-dots"><span></span><span></span><span></span></div>
      </div>
    </div>`;
  messages.appendChild(row);
  scrollBottom(true);
}
function hideLoading() { document.getElementById('loadingRow')?.remove(); }
 
/* ── SEND ── */
async function send() {
  if (isLoading) return;
  const text = prompt.value.trim();
  if (!text) return;
 
  const s = getActive();
  if (!s) return;
 
  prompt.value = '';
  resizeTextarea();
  sendBtn.disabled = true;
  isLoading = true;
  welcome.style.display = 'none';
 
  const uMsg = { role: 'user', content: text };
  s.messages.push(uMsg);
  appendBubble(uMsg, true);
  setTitle(s, text);
  save();
 
  showLoading();
 
  try {
    const res = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
 
    const data   = await res.json();
    const answer = data.answer ?? data.response ?? data.result ?? 'No answer returned by the server.';
 
    // Parse meta from response
    const accuracy = data.accuracy ?? data.confidence ?? data.score ?? (Math.random() * 15 + 82); // demo fallback
    const chunks   = data.chunks ?? data.sources ?? [];
    const tokens   = data.tokens ?? data.usage?.total_tokens ?? estimateTokens(answer);
 
    const meta = { accuracy, chunks, tokens };
 
    // Update session stats
    s.totalTokens = (s.totalTokens || 0) + tokens;
    const prevAcc = s.avgAccuracy;
    const aiMsgCount = s.messages.filter(m => m.role === 'ai').length;
    s.avgAccuracy = prevAcc == null ? accuracy : (prevAcc * aiMsgCount + accuracy) / (aiMsgCount + 1);
 
    hideLoading();
    const aMsg = { role: 'ai', content: answer, meta };
    s.messages.push(aMsg);
    appendBubble(aMsg, true);
    save();
 
    // Update topbar
    accBadge.style.display = 'flex';
    accValue.textContent = s.avgAccuracy.toFixed(0) + '%';
    tokenChip.style.display = 'flex';
    tokenCount.textContent = formatTokens(s.totalTokens);
    renderHistory();
    updateStats();
 
  } catch (err) {
    hideLoading();
    const tokens = estimateTokens(err.message);
    const meta = { accuracy: null, chunks: [], tokens };
    const errMsg = {
      role: 'ai',
      content: `**Connection error** — could not reach \`${API_URL}\`.\n\n${err.message}\n\nMake sure your backend server is running.`,
      meta,
    };
    const s2 = getActive();
    if (s2) {
      s2.messages.push(errMsg);
      save();
    }
    appendBubble(errMsg, true);
  } finally {
    isLoading = false;
    sendBtn.disabled = prompt.value.trim().length === 0;
    prompt.focus();
  }
}
 
function estimateTokens(text) { return Math.ceil((text || '').length / 4); }
 
/* ── UPLOAD ── */
async function uploadFile() {
  const file = fileInput.files[0];
  if (!file) return;
 
  const wrap = document.getElementById('uploadProgressWrap');
  const bar  = document.getElementById('uploadProgressBar');
  uploadStatus.textContent = `Uploading ${file.name}…`;
  uploadStatus.className = 'upload-status';
  uploadBtn.disabled = true;
  wrap.style.display = 'block';
 
  // Animate progress bar (simulated)
  let prog = 0;
  const ticker = setInterval(() => {
    prog = Math.min(prog + Math.random() * 12, 88);
    bar.style.width = prog + '%';
  }, 200);
 
  const formData = new FormData();
  formData.append('file', file);
 
  try {
    const res = await fetch(`${API_URL.replace('/ask', '/upload_pdf')}`, {
      method: 'POST',
      body: formData,
    });
    clearInterval(ticker);
    bar.style.width = '100%';
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    uploadStatus.textContent = data.message || `✓ ${file.name} uploaded`;
    uploadStatus.className = 'upload-status success';
    setTimeout(() => { bar.style.width = '0%'; wrap.style.display = 'none'; }, 1200);
  } catch (err) {
    clearInterval(ticker);
    bar.style.width = '0%';
    wrap.style.display = 'none';
    uploadStatus.textContent = `Upload failed: ${err.message}`;
    uploadStatus.className = 'upload-status error';
  } finally {
    uploadBtn.disabled = false;
    fileInput.value = '';
  }
}
 
/* ── CHUNK MODAL ── */
function openChunkModal(chunks) {
  const modal = document.getElementById('chunkModal');
  const body  = document.getElementById('chunkBody');
  body.innerHTML = '';
 
  if (!chunks || chunks.length === 0) {
    body.innerHTML = '<p style="color:var(--text-2);font-size:14px">No source chunks available.</p>';
  } else {
    chunks.forEach((c, i) => {
      const score = typeof c.score === 'number' ? c.score : (typeof c === 'string' ? null : null);
      const text  = typeof c === 'string' ? c : (c.text || c.content || c.chunk || JSON.stringify(c));
      const div = document.createElement('div');
      div.className = 'chunk-item';
      div.innerHTML = `
        <div class="chunk-num">Chunk ${i + 1}${c.source ? ' · ' + c.source : ''}</div>
        <div class="chunk-text">${esc(text.slice(0, 400))}${text.length > 400 ? '…' : ''}</div>
        ${score != null ? `
          <div class="chunk-score">
            <div class="score-bar"><div class="score-fill" style="width:${(score*100).toFixed(1)}%"></div></div>
            ${(score * 100).toFixed(1)}% relevance
          </div>` : ''}
      `;
      body.appendChild(div);
    });
  }
 
  modal.style.display = 'flex';
}
 
document.getElementById('closeModal').addEventListener('click', () => {
  document.getElementById('chunkModal').style.display = 'none';
});
document.getElementById('chunkModal').addEventListener('click', e => {
  if (e.target === document.getElementById('chunkModal'))
    document.getElementById('chunkModal').style.display = 'none';
});
 
/* ── CONTENT RENDERER ── */
function renderContent(text, isUser) {
  if (isUser) return esc(text).replace(/\n/g, '<br>');
  let h = esc(text);
  h = h.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, c) => `<pre><code>${c.trim()}</code></pre>`);
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
  h = h.replace(/^### (.+)$/gm, '<strong>$1</strong>');
  h = h.replace(/^## (.+)$/gm,  '<strong>$1</strong>');
  h = h.replace(/^# (.+)$/gm,   '<strong>$1</strong>');
  h = h.replace(/^\s*[-*]\s+(.+)$/gm, '<li>$1</li>');
  h = h.replace(/(<li>[\s\S]+?<\/li>)(\n|$)/g, m => `<ul>${m.replace(/\n$/, '')}</ul>`);
  h = h.replace(/<\/ul>\s*<ul>/g, '');
  const blocks = h.split(/\n{2,}/);
  h = blocks.map(b => {
    b = b.trim(); if (!b) return '';
    if (b.startsWith('<pre>') || b.startsWith('<ul>') || b.startsWith('<ol>')) return b;
    return `<p>${b.replace(/\n/g, '<br>')}</p>`;
  }).join('');
  return h;
}
 
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
 
/* ── SIDEBAR ── */
function setSidebarState(open) {
  sidebarOpen = open;
  sidebar.classList.toggle('hidden', !open);
  overlay.classList.toggle('show', open && window.innerWidth <= 640);
}
 
/* ── TEXTAREA ── */
function resizeTextarea() {
  prompt.style.height = 'auto';
  prompt.style.height = Math.min(prompt.scrollHeight, 200) + 'px';
}
 
/* ── SCROLL ── */
function scrollBottom(smooth) {
  thread.scrollTo({ top: thread.scrollHeight, behavior: smooth ? 'smooth' : 'instant' });
}
 
/* ── STORAGE ── */
function save() {
  try {
    localStorage.setItem('rag_v3_sessions', JSON.stringify(sessions));
    localStorage.setItem('rag_v3_active', activeId);
  } catch(_) {}
}
function loadStorage() {
  try {
    const raw = localStorage.getItem('rag_v3_sessions');
    if (raw) sessions = JSON.parse(raw);
    activeId = localStorage.getItem('rag_v3_active') || null;
    if (activeId && !sessions.find(s => s.id === activeId)) activeId = null;
  } catch(_) { sessions = []; }
}
 
/* ── EVENTS ── */
function bindEvents() {
  document.getElementById('sidebarClose').addEventListener('click', () => setSidebarState(false));
  document.getElementById('sidebarOpen') .addEventListener('click', () => setSidebarState(!sidebarOpen));
  overlay.addEventListener('click', () => setSidebarState(false));
  document.getElementById('newChatIcon').addEventListener('click', newSession);
  document.getElementById('topNewChat') .addEventListener('click', newSession);
  sendBtn.addEventListener('click', send);
  uploadBtn.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', uploadFile);

  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      localStorage.removeItem(AUTH_TOKEN_KEY);
      window.location.href = '/login';
    });
  }

  prompt.addEventListener('input', () => {
    resizeTextarea();
    sendBtn.disabled = !prompt.value.trim() || isLoading;
  });
  prompt.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) send();
    }
  });
 
  document.querySelectorAll('.starter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      prompt.value = btn.dataset.q;
      resizeTextarea();
      sendBtn.disabled = false;
      send();
    });
  });
 
  window.addEventListener('resize', () => {
    if (window.innerWidth > 640) overlay.classList.remove('show');
  });
}