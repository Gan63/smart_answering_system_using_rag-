'use strict';

/* ── CONFIG ── */
const API_BASE_URL = 'http://localhost:8000';

/* ── STATE ── */
let currentSession = {
    sessionId: null,
    filename: null
};
let isLoading = false;
let sidebarOpen = true;

/* ── DOM ── */
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('overlay');
const welcome = document.getElementById('welcome');
const messages = document.getElementById('messages');
const thread = document.getElementById('thread');
const promptEl = document.getElementById('prompt');
const sendBtn = document.getElementById('sendBtn');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadStatus = document.getElementById('uploadStatus');
const uploadMessage = document.getElementById('uploadMessage');

/* ── INIT ── */
bindEvents();
setSidebarState(window.innerWidth > 640);

/* ── NEW CHAT ── */
function newChat() {
    window.location.reload();
}

/* ── RENDER MESSAGES ── */
function appendBubble(role, content) {
    const row = document.createElement('div');
    row.className = `msg-row ${role}`;
    const isUser = role === 'user';

    row.innerHTML = `
        <div class="msg-inner">
            ${!isUser ? `<div class="msg-avatar ai">R</div>` : ''}
            <div class="msg-content-wrap" style="flex:1;min-width:0">
                <div class="msg-bubble">${renderContent(content, isUser)}</div>
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
    if (isLoading || !currentSession.sessionId) return;
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
        const res = await fetch(`${API_BASE_URL}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: text, session_id: currentSession.sessionId }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);

        const data = await res.json();
        hideLoading();
        appendBubble('ai', data.answer);

    } catch (err) {
        hideLoading();
        appendBubble('ai', `**Error:** Could not get an answer. \n\n${err.message}`);
    } finally {
        isLoading = false;
        sendBtn.disabled = promptEl.value.trim().length === 0 || !currentSession.sessionId;
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
        const res = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData,
        });
        clearInterval(ticker);
        bar.style.width = '100%';
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        currentSession.sessionId = data.session_id;
        currentSession.filename = data.filename;

        uploadStatus.textContent = `✓ ${file.name} uploaded`;
        uploadStatus.className = 'upload-status success';
        
        if (uploadMessage) {
            uploadMessage.textContent = data.message;
            uploadMessage.style.display = 'block';
        }
        uploadMessage.style.display = 'block';
        
        welcome.style.display = 'none';
        promptEl.disabled = false;
        promptEl.placeholder = `Ask questions about ${currentSession.filename}`;

        setTimeout(() => { wrap.style.display = 'none'; }, 1200);
    } catch (err) {
        clearInterval(ticker);
        wrap.style.display = 'none';
        uploadStatus.textContent = `Upload failed: ${err.message}`;
        uploadStatus.className = 'upload-status error';
    } finally {
        uploadBtn.disabled = false;
        fileInput.value = '';
    }
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
}
