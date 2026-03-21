'use strict';

/* ── CONFIG ── */
 // Dynamic base URL (works with any port:8000/8001/etc)
// Uses relative paths automatically

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

/* ── HISTORY ── */
const historyContainer = document.getElementById('historyContainer');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const modelLabel = document.getElementById('modelLabel');
const sbStats = document.getElementById('sbStats');
const tokenChip = document.getElementById('tokenChip');
const accBadge = document.getElementById('accBadge');

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
bindEvents();
setSidebarState(window.innerWidth > 640);
loadChats();
loadSessions(); // Keep existing sessions sidebar option

/* ── NEW CHAT ── */
function newChat() {
    currentChatId = null;
    console.log("New chat - Current Chat ID:", currentChatId);
    conversation = [];
    messages.innerHTML = '';
    promptEl.value = '';
    if (currentSession.sessionId) {
        promptEl.disabled = false;
        promptEl.placeholder = `New chat about ${currentSession.filename} (has RAG context)`;
        modelLabel.textContent = 'New Chat';
        sendBtn.disabled = false;
    } else {
        welcome.style.display = 'flex';
        promptEl.disabled = true;
        promptEl.placeholder = 'Upload a document to start chatting...';
        sendBtn.disabled = true;
        modelLabel.textContent = 'Smart RAG Assistant';
    }
    tokenChip.style.display = 'none';
    loadChats();
}

/* ── RENDER MESSAGES ── */
function appendBubble(role, content) {
    appendBubbleWithMeta(role, content);
}

function appendBubbleWithMeta(role, content, sources = [], images = []) {
    const row = document.createElement('div');
    row.className = `msg-row ${role}`;
    const isUser = role === 'user';

    let metaHTML = '';
    if (!isUser && (sources.length || images.length)) {
        metaHTML = sources.slice(0,3).map(s => `<span class="meta-chip chunks" title="${esc(s)}">${esc(s.length > 20 ? s.slice(0,20)+'...' : s)}</span>`).join('') +
                   images.slice(0,2).map(() => '<span class="meta-chip images" title="Image">🖼️</span>').join('');
        metaHTML = `<div class="msg-meta">${metaHTML}</div>`;
    }

    row.innerHTML = `
        <div class="msg-inner">
            ${!isUser ? `<div class="msg-avatar ai">R</div>` : ''}
            <div class="msg-content-wrap" style="flex:1;min-width:0">
                <div class="msg-bubble">${renderContent(content, isUser)}</div>
                ${metaHTML}
            </div>
            ${isUser ? `<div class="msg-avatar usr">U</div>` : ''}
        </div>
    `;

    messages.appendChild(row);
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
async function send() {
    if (isLoading && !currentChatId && !currentSession.sessionId) return;
    const text = promptEl.value.trim();
    if (!text) return;

    promptEl.value = '';
    resizeTextarea();
    sendBtn.disabled = true;
    isLoading = true;
    welcome.style.display = 'none';

    appendBubble('user', text);
    showLoading();

    try {
        const payload = {
            message: text,
            session_id: currentSession.sessionId,
            file_name: currentSession.filename,
            chat_id: currentChatId
        };
        const res = await fetch(`/chat`, {
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
        appendBubbleWithMeta('ai', data.response, data.sources || [], data.images || []);
        // Update token count
        const tokenCountEl = document.getElementById('tokenCount');
        if (tokenCountEl && data.tokens && data.tokens.total_tokens !== undefined) {
          tokenCountEl.textContent = data.tokens.total_tokens.toLocaleString() + ' tokens';
          tokenChip.style.display = 'flex';
        }
        if (data.chat_id) currentChatId = data.chat_id;
        console.log("Updated Current Chat ID:", currentChatId);

    } catch (err) {
        hideLoading();
        appendBubble('ai', `**Error:** Could not get an answer. \n\n${err.message}`);
    } finally {
        isLoading = false;
        sendBtn.disabled = promptEl.value.trim().length === 0 || (!currentSession.sessionId && !currentChatId);
        promptEl.focus();
    }
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

        uploadStatus.textContent = `✓ ${file.name} uploaded`;
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
                document.getElementById('processingRow')?.remove();
                uploadStatus.textContent = `✅ ${filename} ready!`;
                uploadStatus.className = 'upload-status success';
                welcome.style.display = 'none';
                promptEl.disabled = false;
                promptEl.placeholder = `Ask questions about ${filename}`;
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


/* ── CONTENT RENDERER ── */
function renderContent(text, isUser) {
    if (isUser) return esc(text).replace(/\n/g, '<br>');
    let h = esc(text);
    h = h.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, c) => `<pre><code>${c.trim()}</code></pre>`);
    h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
    h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
    h = h.replace(/\n/g, '<br>');
    return h;
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
    document.getElementById('sidebarClose').addEventListener('click', () => setSidebarState(false));
    document.getElementById('sidebarOpen').addEventListener('click', () => setSidebarState(!sidebarOpen));
    overlay.addEventListener('click', () => setSidebarState(false));
    document.getElementById('newChatIcon').addEventListener('click', newChat);
    document.getElementById('topNewChat').addEventListener('click', newChat);
    clearHistoryBtn.addEventListener('click', clearCurrentHistory);
    sendBtn.addEventListener('click', send);
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', uploadFile);

    promptEl.addEventListener('input', () => {
        resizeTextarea();
        sendBtn.disabled = !promptEl.value.trim() || isLoading || !currentSession.sessionId;
    });
    promptEl.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) send();
        }
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth > 640) overlay.classList.remove('show');
    });

    // Event delegation for chat clicks (handles dynamic re-renders)
    historyContainer.addEventListener('click', (e) => {
      // Delete button handler
      if (e.target.classList.contains('delete-chat-btn')) {
        const chatItem = e.target.closest('.chat-item');
        if (chatItem && chatItem.dataset.chatId) {
          e.stopPropagation();
          e.preventDefault();
          deleteChat(chatItem.dataset.chatId);
          return;
        }
      }
      // Chat select handler
      const chatItem = e.target.closest('.chat-item');
      if (chatItem && chatItem.dataset.chatId) {
        e.stopPropagation();
        loadChat(chatItem.dataset.chatId);
      }
    });
}

async function loadChats() {
    try {
        const res = await fetch('/chats');
        if (!res.ok) return;
        const data = await res.json();
        console.log("📦 Chats loaded:", data.chats ? data.chats.length : 0, data.chats);
        chats = data.chats || [];
        console.log("📦 Rendering", chats.length, "chats:", chats);
        // Render chat items
        const chatItems = chats.map(chat => {
            const div = document.createElement('div');
            div.className = 'history-item chat-item' + (chat.chat_id === currentChatId ? ' active' : '');
            div.dataset.chatId = chat.chat_id;
            div.innerHTML = `
                <div class="history-title">
                  ${esc(chat.title)}
                  <button class="delete-chat-btn" title="Delete chat">🗑</button>
                </div>
                <div class="history-meta">
                    <span class="msg-count">${chat.message_count || 0} msgs</span>
                    <span class="last-msg">${new Date(chat.timestamp * 1000).toLocaleDateString()}</span>
                </div>
            `;
            div.addEventListener('click', () => loadChat(chat.chat_id));
            return div;
        });
        const sessionSection = document.createElement('div');
        sessionSection.className = 'sb-section';
        const sessionItems = allSessions.map(session => {
            const div = document.createElement('div');
            div.className = 'history-item session-item' + (session.session_id === currentSession.sessionId ? ' active' : '');
            div.dataset.sessionId = session.session_id;
            div.innerHTML = `
                <div class="history-title">${esc(session.filename)}</div>
                <div class="history-meta">
                    <span class="msg-count">${session.message_count || 0} msgs</span>
                    <span class="last-msg">${new Date(session.created_at * 1000).toLocaleDateString()}</span>
                </div>
            `;
            div.addEventListener('click', () => loadSessionHistory(session.session_id));
            return div;
        });
        sessionSection.innerHTML = '<div class="sb-section-label">Sessions</div>' + sessionItems.map(item => item.outerHTML).join('');
        historyContainer.innerHTML = `
            <div class="sb-section">
                <div class="sb-section-label">Chats</div>
                ${chatItems.map(item => item.outerHTML).join('')}
            </div>
            ${sessionSection.outerHTML}
        `;

        // REMOVED auto-select: New chats stay fresh, no jump to old chats
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
        // Render sessions (now after chats)
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
        const stats = { message_count: data.chat.messages.length, total_tokens: 0 };
        sbStats.innerHTML = `
            <span>${stats.message_count} messages</span>
            <span>0 tokens</span>
        `;
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

async function deleteChat(chat_id) {
  if (!confirm('Delete this chat? This cannot be undone.')) return;
  try {
    const res = await fetch(`/chat/${chat_id}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error(await res.text());
    
    if (currentChatId === chat_id) {
      newChat();
    }
    await loadChats();
    console.log('Deleted chat:', chat_id);
  } catch (e) {
    console.error('Delete chat error:', e);
  }
}
