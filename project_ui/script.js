'use strict';

/* ── CONFIG ── */
// Intercept all fetch requests to automatically attach JWT token
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    let [resource, config] = args;
    const token = localStorage.getItem('smart_rag_token');
    
    let urlStr = "";
    if (typeof resource === 'string') {
        urlStr = resource;
    } else if (resource instanceof Request) {
        urlStr = resource.url;
    } else if (resource instanceof URL) {
        urlStr = resource.toString();
    }
    
    // Only intercept requests to our own API
    if (token && urlStr.startsWith('/')) {
        config = config || {};
        
        // Handle headers object
        if (config.headers instanceof Headers) {
            config.headers.set('Authorization', `Bearer ${token}`);
        } else {
            config.headers = { ...config.headers, 'Authorization': `Bearer ${token}` };
        }
        
        // If it was a Request object, we must pass the modified config as the second argument
        // fetch(Request, config) takes precedence over Request's internal headers.
    }
    
    return originalFetch.apply(this, [resource, config]);
};

/* ── STATE ── */
let currentSession = {
    sessionId: null,
    filename: null
};
let currentChatId = null;
let conversation = [];
let chats = [];
let isLoading = false;
let sidebarOpen = true;
let _modePreviewTimer = null;  // for live mode detection preview

/* ── HISTORY ── */
const historyContainer = document.getElementById('historyContainer');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const modelLabel = document.getElementById('modelLabel');
const sbStats = document.getElementById('sbStats');
const tokenChip = document.getElementById('tokenChip');
const accBadge = document.getElementById('accBadge');

/* ── SIDEBAR STAT COUNTERS ── */
let _totalChunks = 0;
let _totalVectors = 0;

function updateSidebarStats({ chunkCount, vectorCount } = {}) {
    if (chunkCount !== undefined) _totalChunks = chunkCount;
    if (vectorCount !== undefined) _totalVectors = vectorCount;
    if (!sbStats) return;
    sbStats.innerHTML = `
        <div class="stat-pill">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            <span>${_totalChunks.toLocaleString()} chunks</span>
        </div>
        <div class="stat-pill">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/><path d="M12 14a2 2 0 1 0 2-2 2 2 0 0 0-2 2z"/></svg>
            <span>${_totalVectors.toLocaleString()} vectors</span>
        </div>
    `;
}

let allSessions = [];

/* ── DOM ── */
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('overlay');
const welcome = document.getElementById('welcome');
const messages = document.getElementById('messages');
const thread = document.getElementById('thread');
const promptEl = document.getElementById('prompt');
const sendBtn = document.getElementById('sendBtn');
const fileInput = document.getElementById('fileInput');
        const uploadBtn = document.getElementById('uploadBtn') || document.querySelector('.upload-icon');
const uploadStatus = document.getElementById('uploadStatus');
const uploadMessage = document.getElementById('uploadMessage');

/* ── INIT ── */
console.log("🎉 JS LOADED - Frontend ready");
checkAuth(); // Added auth guard
bindEvents();
setSidebarState(window.innerWidth > 640);
loadSessions(); // loadSessions will call loadChats at the end

async function checkAuth() {
    const token = localStorage.getItem('smart_rag_token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    try {
        const res = await fetch('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error('Unauthorized');
        
        const user = await res.json();
        // Update UI with user info
        updateUserUI(user);
    } catch (e) {
        console.error('Auth check failed:', e);
        localStorage.removeItem('smart_rag_token');
        window.location.href = '/login';
    }
}

function updateUserUI(user) {
    const userNameEl = document.querySelector('.user-name');
    const userSubEl = document.querySelector('.user-sub');
    const userAvatarEl = document.querySelector('.user-avatar');
    
    if (userNameEl) userNameEl.textContent = user.full_name;
    if (userSubEl) userSubEl.textContent = user.email;
    if (userAvatarEl) userAvatarEl.textContent = user.full_name.charAt(0).toUpperCase();
}

function logout() {
    localStorage.removeItem('smart_rag_token');
    localStorage.removeItem('smart_rag_user');
    window.location.href = '/login';
}

/* ── GLOBAL CONTEXT MENU STATE ── */
let _openMenu = null;
document.addEventListener('click', (e) => {
    if (_openMenu && !_openMenu.contains(e.target)) closeAllMenus();
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAllMenus();
});

function closeAllMenus() {
    document.querySelectorAll('.ctx-menu').forEach(m => m.remove());
    _openMenu = null;
}

function openContextMenu(anchorEl, items) {
    closeAllMenus();
    const menu = document.createElement('div');
    menu.className = 'ctx-menu';
    items.forEach(item => {
        const btn = document.createElement('button');
        btn.className = 'ctx-item' + (item.danger ? ' ctx-danger' : '');
        btn.innerHTML = `<span class="ctx-icon">${item.icon}</span>${item.label}`;
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            closeAllMenus();
            item.action();
        });
        menu.appendChild(btn);
    });
    document.body.appendChild(menu);
    _openMenu = menu;
    // Position below the anchor button
    const rect = anchorEl.getBoundingClientRect();
    let top = rect.bottom + 4;
    let left = rect.right - 140; // align right edge
    // keep inside viewport
    if (left < 4) left = 4;
    if (top + 80 > window.innerHeight) top = rect.top - 80;
    menu.style.top  = `${top}px`;
    menu.style.left = `${left}px`;
}

/* ── NEW CHAT ── */
function completelyNewChat() {
    currentSession = { sessionId: null, filename: null };
    if (document.getElementById('fileInput')) document.getElementById('fileInput').value = '';
    if (document.getElementById('uploadStatus')) {
        document.getElementById('uploadStatus').textContent = '';
        document.getElementById('uploadStatus').className = 'upload-status';
    }
    if (document.getElementById('uploadMessage')) {
        document.getElementById('uploadMessage').textContent = '';
        document.getElementById('uploadMessage').style.display = 'none';
    }
    document.querySelectorAll('.session-item, .history-item').forEach(item => {
        item.classList.remove('active');
    });
    newChat();
}

function newChat() {
    currentChatId = null;
    console.log("New chat - Current Chat ID:", currentChatId);
    conversation = [];
    messages.innerHTML = '';
    promptEl.value = '';
    // Reset session info UI
    document.querySelectorAll('.session-info').forEach(el => {
      el.innerHTML = '<p class="chunks">📄 Chunks: -</p><p class="vectors">🧠 Vectors: -</p>';
    });
    if (currentSession.sessionId) {
        promptEl.placeholder = `New chat about ${currentSession.filename} (has RAG context)`;
        modelLabel.textContent = 'New Chat';
    } else {
        welcome.style.display = 'flex';
        promptEl.placeholder = 'Upload a document to start chatting...';
        modelLabel.textContent = 'Smart RAG Assistant';
    }
    // Textarea is ALWAYS enabled — user can type at any time
    promptEl.disabled = false;
    sendBtn.disabled = promptEl.value.trim().length === 0;
    tokenChip.style.display = 'none';
    loadChats();
}

/* ── RENDER MESSAGES ── */
function appendBubble(role, content) {
    appendBubbleWithMeta(role, content);
}

function appendBubbleWithMeta(role, content, sources = [], images = [], modeBadgeHTML = '') {
    const row = document.createElement('div');
    row.className = `msg-row ${role}`;
    const isUser = role === 'user';

    // Build inline image gallery from API images array (separate from LLM text)
    let imageGalleryHTML = '';
    if (!isUser && images && images.length > 0) {
        const imgItems = images.map((img, idx) => {
            // Path is already normalized by backend (/data/extracted_images/...)
            let src = img.path || img.url || '';
            // Safety: normalize backslashes, ensure leading slash
            src = src.replace(/\\/g, '/').split(' | ')[0].trim();
            if (src && !src.startsWith('/') && !src.startsWith('data:') && !src.startsWith('http')) src = '/' + src;
            const caption = img.caption || `Image ${idx + 1}`;
            const escapedSrc = src.replace(/"/g, '%22');
            return `<div style="display:inline-flex;flex-direction:column;align-items:center;gap:4px;margin:4px;">
                <img id="img-${idx}-${Date.now()}" src="${escapedSrc}" alt="${esc(caption)}"
                     style="max-width:300px;max-height:220px;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,0.5);cursor:pointer;display:block;border:1px solid rgba(255,255,255,0.1);"
                     onclick="window.open(this.src,'_blank')"
                     onerror="this.outerHTML='<div style=\'padding:8px 12px;background:rgba(255,80,80,0.15);border:1px solid rgba(255,80,80,0.4);border-radius:8px;font-size:12px;color:#ff8080;max-width:300px;word-break:break-all\'>\u26a0\ufe0f Cannot load: ${escapedSrc}</div>'" />
                <span style="font-size:11px;color:var(--text-2,#8888aa);text-align:center;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(caption)}">${esc(caption)}</span>
            </div>`;
        }).join('');
        imageGalleryHTML = `<div class="image-gallery" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.07);">${imgItems}</div>`;
    }

    let metaHTML = '';
    if (!isUser && sources.length) {
        metaHTML = sources.slice(0,3).map(s => `<span class="meta-chip chunks" title="${esc(s)}">${esc(s.length > 20 ? s.slice(0,20)+'...' : s)}</span>`).join('');
        metaHTML = `<div class="msg-meta">${metaHTML}</div>`;
    }

    row.innerHTML = `
        <div class="msg-inner">
            ${!isUser ? `<div class="msg-avatar ai">R</div>` : ''}
            <div class="msg-content-wrap" style="flex:1;min-width:0">
                ${!isUser && modeBadgeHTML ? modeBadgeHTML : ''}
                <div class="msg-bubble">${renderContent(content, isUser)}${imageGalleryHTML}</div>
                ${metaHTML}
            </div>
            ${isUser ? `<div class="msg-avatar usr">U</div>` : ''}
        </div>
    `;

    messages.appendChild(row);
    renderMermaidIn(row);
    setupCodeBlocks(row);
    scrollBottom(true);
    return row;
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

function hideLoading() {
    document.getElementById('loadingRow')?.remove();
}

/* ── SEND ── */
/* ── TOAST NOTIFICATION ── */
function showToast(message, type = 'warning') {
    let toast = document.getElementById('ragToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'ragToast';
        toast.style.cssText = `
            position: fixed;
            bottom: 120px;
            left: 50%;
            transform: translateX(-50%) translateY(20px);
            background: var(--surface-2, #1e1e2e);
            color: var(--text-1, #e0e0ff);
            border: 1px solid rgba(255,160,50,0.5);
            border-radius: 12px;
            padding: 12px 20px;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            z-index: 9999;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.25s ease, transform 0.25s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            max-width: 360px;
            text-align: center;
        `;
        document.body.appendChild(toast);
    }
    toast.innerHTML = `<span style="font-size:18px">${type === 'warning' ? '⚠️' : type === 'info' ? '✅' : 'ℹ️'}</span> ${message}`;
    toast.style.borderColor = type === 'info' ? 'rgba(0,229,160,0.5)' : type === 'warning' ? 'rgba(255,160,50,0.5)' : 'rgba(100,180,255,0.5)';
    toast.style.opacity = '1';
    toast.style.transform = 'translateX(-50%) translateY(0)';
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(-50%) translateY(20px)';
    }, 3500);
}

async function send(overrideMsg = null, screenshotB64 = null) {
    if (isLoading) return;
    const text = overrideMsg || promptEl.value.trim();
    if (!text && !screenshotB64) return;

    // If no document uploaded, notify user and stop
    // Allow all messages to go through, backend rules will handle if doc is needed.

    promptEl.value = '';
    resizeTextarea();
    sendBtn.disabled = true;
    isLoading = true;
    welcome.style.display = 'none';
    hideModePreview();

    appendBubble('user', text);
    showLoading();

    try {
        const payload = {
            message: text,
            session_id: currentSession.sessionId,
            file_name: currentSession.filename,
            chat_id: currentChatId,
            screenshot: screenshotB64 // Optional vision context
        };
        const res = await fetch(`/api/hybrid-chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const errorText = await res.text();
          console.error('Chat error:', res.status, errorText);
          throw new Error(`HTTP ${res.status}: ${errorText || res.statusText}`);
        }
        const data = await res.json();
        hideLoading();

        // Build mode badge HTML
        const modeInfo = getModeInfo(data.mode);
        const modeBadgeHTML = `<div class="mode-badge mode-${(data.mode || 'rag').toLowerCase()}">
            <span class="mode-icon">${modeInfo.icon}</span>
            <span class="mode-label">${modeInfo.label}</span>
        </div>`;

        appendBubbleWithMeta('ai', data.response, data.sources || [], data.images || [], modeBadgeHTML);
        // Update token count
        const tokenCountEl = document.getElementById('tokenCount');
        if (tokenCountEl && data.tokens && data.tokens.total_tokens !== undefined) {
          tokenCountEl.textContent = data.tokens.total_tokens.toLocaleString() + ' tokens';
          tokenChip.style.display = 'flex';
        }
        let wasNewChat = false;
        if (!currentChatId && data.chat_id) {
            wasNewChat = true;
        }
        if (data.chat_id) currentChatId = data.chat_id;
        console.log("Updated Current Chat ID:", currentChatId, "Mode:", data.mode);
        
        // Ensure new chats appear in the sidebar immediately
        if (wasNewChat) {
            loadChats();
        }
    } catch (err) {
        hideLoading();
        appendBubble('ai', `**Error:** Could not get an answer. \n\n${err.message}`);
    } finally {
        isLoading = false;
        sendBtn.disabled = promptEl.value.trim().length === 0;
        promptEl.focus();
    }
}

/* ── MODE HELPERS ── */
function getModeInfo(mode) {
    switch ((mode || '').toUpperCase()) {
        case 'CODE':   return { icon: '💻', label: 'Code Assistant' };
        case 'HYBRID': return { icon: '🔀', label: 'Hybrid Mode' };
        case 'DS':     return { icon: '📊', label: 'Data Science' };
        case 'STUDY':  return { icon: '🧠', label: 'Study Mode' };
        case 'CAREER': return { icon: '💼', label: 'Career Advisor' };
        case 'IMAGE':  return { icon: '🎨', label: 'Image Prompt' };
        case 'REPORT': return { icon: '📄', label: 'Formal Report' };
        case 'RAG':
        default:       return { icon: '📚', label: 'RAG Mode' };
    }
}

function showModePreview(mode) {
    let el = document.getElementById('modePreview');
    if (!el) {
        el = document.createElement('div');
        el.id = 'modePreview';
        el.className = 'mode-preview';
        const inputArea = document.querySelector('.input-area');
        if (inputArea) inputArea.insertBefore(el, inputArea.firstChild);
    }
    const info = getModeInfo(mode);
    el.innerHTML = `${info.icon} <span>${info.label}</span>`;
    el.className = `mode-preview mode-preview-${mode.toLowerCase()}`;
    el.style.display = 'flex';
}

function hideModePreview() {
    const el = document.getElementById('modePreview');
    if (el) el.style.display = 'none';
}

async function detectModePreview(text) {
    if (!text || text.length < 3) { hideModePreview(); return; }
    try {
        const hasCtx = !!currentSession.sessionId;
        const res = await fetch(`/api/detect-mode?q=${encodeURIComponent(text)}&has_context=${hasCtx}`);
        if (res.ok) {
            const data = await res.json();
            showModePreview(data.mode);
        }
    } catch(_) {}
}

/* ── UPLOAD ── */
async function uploadFile() {
    const file = fileInput.files[0];
    if (!file) return;

    const wrap = document.getElementById('uploadProgressWrap');
    const bar = document.getElementById('uploadProgressBar');
    uploadStatus.textContent = `Uploading ${file.name}…`;
    uploadStatus.className = 'upload-status';
    uploadBtn.disabled = true;
    wrap.style.display = 'block';

    let prog = 0;
    const ticker = setInterval(() => {
        prog = Math.min(prog + Math.random() * 12, 88);
        bar.style.width = prog + '%';
    }, 200);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`/upload`, {
            method: 'POST',
            body: formData,
        });
        clearInterval(ticker);
        bar.style.width = '100%';
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        showProcessingState(data);

        currentSession.sessionId = data.session_id;
        currentSession.filename = data.filename;

        // Update sidebar stats from upload response
        // Do not overwrite sidebar totals with partial upload response counts yet.
        // We will refresh once processing is complete.

        uploadStatus.innerHTML = `✔ ${file.name} uploaded successfully<br>
  <div class="session-info">
    <p class="file">✔ ${data.filename} uploaded</p>
    <p class="chunks">📄 Chunks: ${data.chunk_count || 0}</p>
    <p class="vectors">🧠 Vectors: ${data.vector_count || 0}</p>
  </div>`;
        uploadStatus.className = 'upload-status success';
        
        if (uploadMessage) {
            uploadMessage.textContent = data.message;
            uploadMessage.style.display = 'block';
        }
        
        welcome.style.display = 'none';
        promptEl.disabled = false;
        promptEl.placeholder = `Ask questions about ${currentSession.filename}`;

        setTimeout(() => { 
            wrap.style.display = 'none'; 
            loadSessions(); 
        }, 1200);
    } catch (err) {
        clearInterval(ticker);
        wrap.style.display = 'none';
        console.error('Upload error:', err);
        uploadStatus.textContent = `❌ Upload failed: ${err.message}`;
        uploadStatus.className = 'upload-status error';
        if (uploadMessage) {
          uploadMessage.textContent = 'Please try again or check console.';
          uploadMessage.style.display = 'block';
        }
    } finally {
        uploadBtn.disabled = false;
        fileInput.value = '';
    }
}

async function showProcessingState(data) {
    if (!data?.filename) return;
    uploadStatus.textContent = '🔄 Processing document...';
    uploadStatus.className = 'upload-status processing';
    
    // Show loading dots
    const processingRow = document.createElement('div');
    processingRow.id = 'processingRow';
    processingRow.className = 'msg-row ai';
    processingRow.innerHTML = `
        <div class="msg-inner">
            <div class="msg-avatar ai">R</div>
            <div class="msg-bubble">
                <div class="loading-dots"><span></span><span></span><span></span></div>
                <div style="font-size:13px;color:var(--text-2);margin-top:8px;">Processing ${data.filename}...</div>
            </div>
        </div>`;
    
    messages.appendChild(processingRow);
    scrollBottom(true);
    
    // Poll for readiness
    await checkProcessingComplete(data.session_id, data.filename);
}

async function checkProcessingComplete(sessionId, filename) {
    const maxAttempts = 30; // 30s timeout
    let attempts = 0;
    
    while (attempts < maxAttempts) {
        try {
        const testRes = await fetch(`/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    question: 'test readiness', 
                    session_id: sessionId 
                }),
            });
            const testData = await testRes.json();
            
            if (testData.context && testData.context.text_context && testData.context.text_context.length > 100) {
                // Processing complete
                // Processing complete
                document.getElementById('processingRow')?.remove();
                uploadStatus.textContent = `✅ ${filename} ready!`;
                uploadStatus.className = 'upload-status success';
                welcome.style.display = 'none';
                promptEl.disabled = false;
                promptEl.placeholder = `Ask questions about ${filename}`;
                loadSessions(); // Refresh sidebar stats and items after processing complete
                return;
            }
        } catch (e) {
            // Still processing or error, continue polling
        }
        
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
    }
    
    // Timeout
    document.getElementById('processingRow')?.remove();
    uploadStatus.textContent = `⏱ Processing taking longer than expected...`;
    uploadStatus.className = 'upload-status';
}


/* ── MARKDOWN / DIAGRAM RENDERER ── */

// Configure marked once (GFM mode: tables, strikethrough, breaks)
if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true, headerIds: false, mangle: false });
}

// Configure mermaid once (dark theme matching the app)
if (typeof mermaid !== 'undefined') {
    mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
            primaryColor: '#00e5a0', primaryTextColor: '#f0f4ff',
            primaryBorderColor: '#0088ff', lineColor: '#8e9ab8',
            background: '#080c14', mainBkg: 'rgba(0,229,160,0.08)',
            nodeBorder: '#00e5a0', edgeLabelBackground: '#080c14',
            clusterBkg: 'rgba(0,136,255,0.08)', titleColor: '#f0f4ff',
        },
        securityLevel: 'loose',
    });
}

let _mermaidCounter = 0;

function renderContent(text, isUser) {
    if (isUser) return esc(text).replace(/\n/g, '<br>');

    // ── Step 1: extract mermaid fences BEFORE marked processes them ──
    const mermaidBlocks = [];
    const PLACEHOLDER = '\x00MERMAID\x00';
    text = text.replace(/```mermaid\n([\s\S]*?)```/gi, (_, code) => {
        const id = _mermaidCounter++;
        mermaidBlocks.push({ id, code: code.trim() });
        return `${PLACEHOLDER}${id}${PLACEHOLDER}`;
    });

    // ── Step 2: run marked for full GFM (tables, headings, lists, bold…) ──
    let html = '';
    if (typeof marked !== 'undefined') {
        try { html = marked.parse(text); }
        catch (e) { html = esc(text).replace(/\n/g, '<br>'); }
    } else {
        html = esc(text)
            .replace(/```[\w]*\n?([\s\S]*?)```/g, (_, c) => `<pre><code>${c.trim()}</code></pre>`)
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    }

    // ── Step 3: replace placeholders with mermaid diagram containers ──
    mermaidBlocks.forEach(({ id, code }) => {
        // decode HTML entities marked may have introduced
        const safeCode = code.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
        const divId = `mermaid-${Date.now()}-${id}`;
        const diagramDiv = `<div class="mermaid-wrap"><div class="mermaid" id="${divId}">${safeCode}</div></div>`;
        // replace raw placeholder or any <p>…</p> wrapper marked adds
        const re = new RegExp(`(<p>\\s*)?${PLACEHOLDER}${id}${PLACEHOLDER}(\\s*</p>)?`, 'g');
        html = html.replace(re, diagramDiv);
    });

    return html;
}

// Call after appending a bubble to the DOM to render mermaid diagrams inside it
function renderMermaidIn(element) {
    if (typeof mermaid === 'undefined') return;
    const nodes = element.querySelectorAll('.mermaid');
    if (!nodes.length) return;
    nodes.forEach(node => {
        const code = node.textContent.trim();
        const svgId = node.id + '-svg';
        node.textContent = code;
        mermaid.render(svgId, code)
            .then(({ svg }) => { node.innerHTML = svg; })
            .catch(err => {
                node.innerHTML = `<pre style="color:#ff8080;font-size:12px">Diagram error: ${esc(String(err))}</pre>`;
            });
    });
}

// ── NEW: Code Block Copy Feature ──
function setupCodeBlocks(element) {
    const codeBlocks = element.querySelectorAll('pre');
    codeBlocks.forEach(block => {
        if (block.querySelector('.copy-code-btn')) return; // Avoid duplicates
        
        const button = document.createElement('button');
        button.className = 'copy-code-btn';
        button.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
            <span>Copy</span>
        `;
        
        button.onclick = () => {
            const code = block.querySelector('code').innerText;
            navigator.clipboard.writeText(code).then(() => {
                button.classList.add('copied');
                button.querySelector('span').innerText = 'Copied!';
                setTimeout(() => {
                    button.classList.remove('copied');
                    button.querySelector('span').innerText = 'Copy';
                }, 2000);
            });
        };
        
        block.style.position = 'relative';
        block.appendChild(button);
    });
}


function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/* ── SIDEBAR ── */
function highlightActiveChat(chatId) {
  document.querySelectorAll('.chat-item').forEach(item => {
    item.classList.toggle('active', item.dataset.chatId === chatId);
  });
  document.querySelectorAll('.session-item, .history-item:not(.chat-item)').forEach(item => {
    item.classList.remove('active');
  });
}

function setSidebarState(open) {
    sidebarOpen = open;
    sidebar.classList.toggle('hidden', !open);
    overlay.classList.toggle('show', open && window.innerWidth <= 640);
}

/* ── TEXTAREA ── */
function resizeTextarea() {
    promptEl.style.height = 'auto';
    promptEl.style.height = Math.min(promptEl.scrollHeight, 200) + 'px';
}

/* ── SCROLL ── */
function scrollBottom(smooth) {
    thread.scrollTo({ top: thread.scrollHeight, behavior: smooth ? 'smooth' : 'instant' });
}

/* ── EVENTS ── */
function bindEvents() {
    console.log("🔗 Binding UI events...");

    const safeBind = (id, event, fn) => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener(event, fn);
        } else {
            console.warn(`[WARN] Element #${id} not found. Skipping binding.`);
        }
    };

    safeBind('sidebarClose', 'click', () => setSidebarState(false));
    safeBind('sidebarOpen', 'click', () => setSidebarState(!sidebarOpen));
    safeBind('sidebarToggle', 'click', () => {
        sidebar.classList.toggle('hidden');
        if (window.innerWidth <= 640) {
            overlay.classList.toggle('show');
        }
    });

    if (overlay) overlay.addEventListener('click', () => setSidebarState(false));

    safeBind('newChatIcon', 'click', completelyNewChat);
    safeBind('topNewChat', 'click', completelyNewChat);
    safeBind('sidebarNewChatBtn', 'click', completelyNewChat);
    safeBind('clearHistoryBtn', 'click', clearCurrentHistory);
    safeBind('sendBtn', 'click', send);
    
    const uploadBtnEl = document.getElementById('uploadBtn');
    if (uploadBtnEl) {
        uploadBtnEl.addEventListener('click', () => {
            const fi = document.getElementById('fileInput');
            if (fi) fi.click();
        });
    }

    const fileInputEl = document.getElementById('fileInput');
    if (fileInputEl) fileInputEl.addEventListener('change', uploadFile);
    
    safeBind('logoutBtn', 'click', logout);

    if (promptEl) {
        promptEl.addEventListener('input', () => {
            resizeTextarea();
            sendBtn.disabled = !promptEl.value.trim() || isLoading;
            clearTimeout(_modePreviewTimer);
            _modePreviewTimer = setTimeout(() => {
                detectModePreview(promptEl.value.trim());
            }, 400);
        });
        promptEl.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!sendBtn.disabled) send();
            }
        });
    }

    // Starter Buttons
    document.querySelectorAll('.starter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const q = btn.dataset.q;
            if (q) {
                promptEl.value = q;
                resizeTextarea();
                send();
            }
        });
    });

    safeBind('micBtn', 'click', toggleSpeech);
    safeBind('screenshotBtn', 'click', captureScreenshot);

    window.addEventListener('resize', () => {
        const ov = document.getElementById('overlay');
        if (window.innerWidth > 640 && ov) ov.classList.remove('show');
    });

    if (historyContainer) {
        historyContainer.addEventListener('click', (e) => {
            // Delegation for menu/items
            const dotBtn = e.target.closest('.three-dot-btn');
            if (dotBtn) {
                handleMenuClick(e, dotBtn);
                return;
            }
            const chatItem = e.target.closest('.chat-item');
            if (chatItem && chatItem.dataset.chatId && !e.target.closest('.three-dot-btn')) {
                loadChat(chatItem.dataset.chatId);
            }
        });
    }
    
    console.log("✅ All UI bindings complete.");
}

function handleMenuClick(e, dotBtn) {
    e.stopPropagation();
    e.preventDefault();
    const type = dotBtn.dataset.type;
    if (type === 'chat') {
        const chatId = dotBtn.dataset.chatId;
        openContextMenu(dotBtn, [
            {
                icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
                label: 'Rename',
                action: () => renameChat(chatId, dotBtn.dataset.title)
            },
            {
                icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18m-2 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>',
                label: 'Delete chat',
                danger: true,
                action: () => deleteChat(chatId)
            }
        ]);
    } else if (type === 'file') {
        const sessionId = dotBtn.dataset.sessionId;
        const filename = dotBtn.dataset.filename;
        openContextMenu(dotBtn, [
            {
                icon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18m-2 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>',
                label: 'Delete file & data',
                danger: true,
                action: () => deleteUploadedFile(sessionId, filename)
            }
        ]);
    }
}

async function loadChats() {
    try {
        const res = await fetch('/chats');
        if (!res.ok) return;
        const data = await res.json();
        chats = data.chats || [];

        // ── Chat items ──
        const chatItemsHTML = chats.map(chat => {
            const isActive = chat.chat_id === currentChatId ? ' active' : '';
            const date = new Date(chat.timestamp * 1000).toLocaleDateString();
            return `
                <div class="history-item chat-item${isActive}" data-chat-id="${chat.chat_id}">
                    <div class="chat-item-row">
                        <span class="chat-item-title">${esc(chat.title)}</span>
                        <button class="three-dot-btn" data-type="chat" data-chat-id="${chat.chat_id}" data-title="${esc(chat.title)}" title="More options" aria-label="More options">
                            <span>&#8942;</span>
                        </button>
                    </div>
                    <div class="history-meta">
                        <div style="display:flex; gap:8px;">
                           <span class="msg-count">${chat.message_count || 0} msgs</span>
                           <span class="last-msg">${date}</span>
                        </div>
                    </div>
                </div>`;
        }).join('');

        // ── Session / uploaded file items ──
        let sessionHTML = '';
        let totalChunksAll = 0;
        let totalVectorsAll = 0;
        if (allSessions.length > 0) {
            const sessionPromises = allSessions.map(async session => {
                let chunkCount = 0, vectorCount = 0;
                try {
                    const statsRes = await fetch(`/api/session/${session.session_id}`);
                    const stats = await statsRes.json();
                    chunkCount  = stats.chunk_count  || 0;
                    vectorCount = stats.vector_count || 0;
                    totalChunksAll += chunkCount;
                    totalVectorsAll += vectorCount;
                } catch (_) {}

                const isActive = session.session_id === currentSession.sessionId ? ' active' : '';
                const date = new Date(session.created_at * 1000).toLocaleDateString();
                return `
                    <div class="history-item session-item${isActive}" data-session-id="${session.session_id}">
                        <div class="chat-item-row">
                            <span class="chat-item-title">📄 ${esc(session.filename)}</span>
                            <button class="three-dot-btn" data-type="file"
                                    data-session-id="${session.session_id}"
                                    data-filename="${esc(session.filename)}"
                                    title="More options" aria-label="More options">
                                <span>&#8942;</span>
                            </button>
                        </div>
                        <div class="session-info">
                            <span>📊 Chunks: ${chunkCount}</span>
                            <span>🧠 Vectors: ${vectorCount}</span>
                        </div>
                        <div class="history-meta">
                            <span class="last-msg">${date}</span>
                        </div>
                    </div>`;
            });
            const sessionHTMLs = await Promise.all(sessionPromises);
            sessionHTML = `<div class="sb-section-label" style="margin-top:8px;">Uploaded Files</div>${sessionHTMLs.join('')}`;
            // Update counts in sidebar stats
            updateSidebarStats({ 
                chunkCount: totalChunksAll,
                vectorCount: totalVectorsAll
            });
        }

        historyContainer.innerHTML = `
            <div class="sb-section">
                <div class="sb-section-label">Chats</div>
                ${chatItemsHTML || '<div class="empty-hint">No chats yet</div>'}
            </div>
            <div class="sb-section">${sessionHTML}</div>
        `;

    } catch (e) {
        console.error('Load chats error:', e);
    }
}

function renderSessions() {
    allSessions.forEach(session => renderSessionItem(session));
}

async function loadSessions() {
    try {
        const res = await fetch('/sessions');
        if (!res.ok) return;
        const data = await res.json();
        allSessions = data.sessions || [];
        // Trigger loadChats only after sessions are populated to ensure correct sidebar render
        loadChats(); 
    } catch (e) {
        console.error('Load sessions error:', e);
    }
}

function renderSessionItem(session) {
    const div = document.createElement('div');
    div.className = 'history-item' + (session.session_id === currentSession.sessionId ? ' active' : '');
    div.dataset.sessionId = session.session_id;
    div.innerHTML = `
        <div class="history-title">${esc(session.filename)}</div>
        <div class="history-meta">
            <span class="msg-count">${session.message_count || 0} messages</span>
            <span class="last-msg">${new Date(session.created_at * 1000).toLocaleDateString()}</span>
        </div>
    `;
    div.addEventListener('click', () => loadSessionHistory(session.session_id));
    historyContainer.appendChild(div);
}

async function loadChat(chatId) {
    console.log("Loading chat, setting Current Chat ID:", chatId);
    if (isLoading) return;
    try {
        const res = await fetch(`/chat/${chatId}`);
        if (!res.ok) throw new Error(`Failed to load chat: ${res.status}`);
        const data = await res.json();
        console.log("📦 Chat data:", data);
        
        if (!data.chat || !data.chat.messages) {
            console.error("❌ No messages found in chat data:", data);
            appendBubble('ai', '**Error:** Chat not found or empty!');
            return;
        }
        
        currentChatId = chatId;
        conversation = data.chat.messages;

        // Restore context session if present
        if (data.chat.session_id) {
          currentSession.sessionId = data.chat.session_id;
          currentSession.filename  = data.chat.file_name || data.chat.title;
          console.log("🔗 Restored Session ID for chat:", currentSession.sessionId);
        }

        messages.innerHTML = '';
        welcome.style.display = 'none';
        promptEl.disabled = false;
        promptEl.placeholder = `Continue "${data.chat.title}"`;
        modelLabel.textContent = data.chat.title;

        data.chat.messages.forEach(msg => {
            const role = msg.role === 'user' ? 'user' : 'ai';
            appendBubble(role, msg.content);
        });
        scrollBottom(true);

        // Update stats
        // message count removed as per request, just refreshing sidebar from overall state
        updateSidebarStats();
        const tokenCountEl = document.getElementById('tokenCount');
        if (tokenCountEl) tokenCountEl.textContent = '0 tokens';
        tokenChip.style.display = 'flex';
        highlightActiveChat(chatId);
        console.log("✅ Chat loaded successfully:", chatId, "messages:", data.chat.messages.length);
    } catch (e) {
        console.error('Load chat error:', e);
        appendBubble('ai', '**Error:** Could not load chat. Check console.');
    }
}

async function loadSessionHistory(sessionId) {
    if (isLoading) return;
    try {
        const res = await fetch(`/history/${sessionId}`);
        if (!res.ok) throw new Error('Failed to load history');
        const data = await res.json();
        const session = allSessions.find(s => s.session_id === sessionId);
        if (!session) return;

        currentSession.sessionId = sessionId;
        currentSession.filename = session.filename;
        currentChatId = null; // New session resets chat
        conversation = [];
        messages.innerHTML = '';
        welcome.style.display = 'none';
        promptEl.disabled = false;
        promptEl.placeholder = `Ask questions about ${session.filename}`;
        modelLabel.textContent = session.filename;

        data.history.forEach(msg => {
            appendBubble('user', msg.query);
            appendBubble('ai', msg.answer);
        });
        scrollBottom();

        // Update stats
        const stats = data.stats || { message_count: data.history.length, total_tokens: 0 };
        sbStats.innerHTML = `
            <span>${stats.message_count} messages</span>
            <span>${stats.total_tokens.toLocaleString()} tokens</span>
        `;
        tokenChip.style.display = 'flex';
        tokenChip.querySelector('#tokenCount').textContent = `${stats.total_tokens.toLocaleString()} tokens`;
        highlightActiveChat(currentChatId);
    } catch (e) {
        console.error('Load session history error:', e);
        appendBubble('ai', '**Error:** Could not load history.');
    }
}

async function clearCurrentHistory() {
    if (!currentSession.sessionId) return;
    if (!confirm('Clear this chat history?')) return;
    try {
        const res = await fetch(`/session/${currentSession.sessionId}`, { method: 'DELETE' });
        if (res.ok) {
            newChat();
            loadSessions();
        }
    } catch (e) {
        console.error('Clear history error:', e);
    }
}

/* ── DELETE CHAT (permanent) ── */
async function deleteChat(chat_id) {
  if (!confirm('Delete this chat permanently? This cannot be undone.')) return;
  try {
    const res = await fetch(`/chat/${chat_id}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    console.log('[OK] Deleted chat:', chat_id);
    if (currentChatId === chat_id) newChat();
    await loadChats();
    showToast('Chat deleted permanently.', 'info');
  } catch (e) {
    console.error('Delete chat error:', e);
    showToast(`Delete failed: ${e.message}`, 'warning');
  }
}

/* ── RENAME CHAT ── */
async function renameChat(chat_id, current_title) {
  const newTitle = prompt('Rename this chat history:', current_title);
  if (!newTitle || newTitle.trim() === '' || newTitle === current_title) return;

  try {
    const res = await fetch(`/chat/${chat_id}/rename`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTitle.trim() })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    console.log('[OK] Renamed chat:', chat_id);
    if (currentChatId === chat_id) {
       modelLabel.textContent = newTitle.trim();
    }
    await loadChats();
    showToast('Chat renamed successfully.', 'info');
  } catch (e) {
    console.error('Rename error:', e);
    showToast(`Rename failed: ${e.message}`, 'warning');
  }
}

/* ── DELETE UPLOADED FILE + VECTORS (permanent) ── */
async function deleteUploadedFile(sessionId, filename) {
  if (!confirm(`Delete "${filename}" and all its vectors from the database? This cannot be undone.`)) return;
  try {
    const res = await fetch(`/file/${sessionId}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    console.log('[OK] Deleted file:', data);

    // If the deleted session was the active one, reset state
    if (currentSession.sessionId === sessionId) {
      currentSession.sessionId = null;
      currentSession.filename  = null;
      promptEl.placeholder = 'Upload a document to start chatting...';
    }

    await loadSessions();
    await loadChats();
    showToast(`"${filename}" deleted from database.`, 'info');
    } catch (e) {
    console.error('Delete file error:', e);
    showToast(`Delete failed: ${e.message}`, 'warning');
  }
}

/* ── VOICE / SPEECH RECOGNITION ── */
let recognition = null;
let isRecording = false;

function toggleSpeech() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showToast("Speech recognition not supported in this browser.", "warning");
        return;
    }

    if (!recognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            isRecording = true;
            document.getElementById('micBtn').classList.add('recording');
            document.getElementById('micBtn').style.color = '#ff4b4b';
            promptEl.placeholder = "Listening...";
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            promptEl.value = transcript;
            resizeTextarea();
            sendBtn.disabled = false;
            // Optionally auto-send
            // send();
        };

        recognition.onerror = (event) => {
            console.error('Speech error:', event.error);
            stopRecording();
            showToast(`Speech error: ${event.error}`, "warning");
        };

        recognition.onend = () => {
            stopRecording();
        };
    }

    if (isRecording) {
        recognition.stop();
    } else {
        recognition.start();
    }
}

function stopRecording() {
    isRecording = false;
    const micBtn = document.getElementById('micBtn');
    if (micBtn) {
        micBtn.classList.remove('recording');
        micBtn.style.color = '';
    }
    promptEl.placeholder = currentSession.sessionId 
        ? `Ask questions about ${currentSession.filename}` 
        : 'Upload a document to start chatting...';
}

/* ── DEBUG SCREENSHOT (Screen Capture API) ── */
async function captureScreenshot() {
    const btn = document.getElementById('screenshotBtn');
    if (!btn) return;
    
    const originalHTML = btn.innerHTML;
    
    try {
        btn.disabled = true;
        btn.classList.add('loading');
        
        showToast("Select a window or screen to analyze", "info");
        
        // 1. Request Screen Media (allows capturing other windows/screens)
        const stream = await navigator.mediaDevices.getDisplayMedia({
            video: { cursor: "always" },
            audio: false
        });
        
        // 2. Capture a frame from the stream
        const video = document.createElement('video');
        video.srcObject = stream;
        await video.play();
        
        // Create canvas to draw the frame
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // 3. Stop all tracks in the stream
        stream.getTracks().forEach(track => track.stop());
        
        const imageData = canvas.toDataURL('image/png');
        
        // 4. Trigger send process
        const currentMsg = promptEl.value.trim() || "Analyze this screen capture in detail. Describe the content and help me understand it.";
        await send(currentMsg, imageData);
        
        showToast(`Capture sent for analysis`, 'info');

    } catch (err) {
        if (err.name === 'NotAllowedError') {
            showToast('Capture cancelled by user', 'warning');
        } else {
            console.error('❌ Screen capture failed:', err);
            showToast('Screen capture failed. Check console.', 'warning');
        }
    } finally {
        btn.disabled = false;
        btn.classList.remove('loading');
        btn.innerHTML = originalHTML;
    }
}

