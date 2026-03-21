'use strict';

let currentSession = { sessionId: null, filename: null };
let currentChatId = null;
let isLoading = false;
let sidebarOpen = true;
let chats = [];
let allSessions = [];

// DOM elements
const historyContainer = document.getElementById('historyContainer');
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('overlay');
const welcome = document.getElementById('welcome');
const messages = document.getElementById('messages');
const thread = document.getElementById('thread');
const promptEl = document.getElementById('prompt');
const sendBtn = document.getElementById('sendBtn');
const tokenChip = document.getElementById('tokenChip');
const tokenCountEl = document.getElementById('tokenCount');
const modelLabel = document.getElementById('modelLabel');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');

// NO SHARED MESSAGES ARRAY - FRESH LOADS ONLY

let uploadedFileName = null;
let currentSessionId = null;

// ===== UPLOAD FUNCTION =====
async function uploadFile() {
  const file = fileInput.files[0];
  if (!file) return console.log("No file selected");

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/upload', {
      method: 'POST',
      body: formData
    });
    
    if (!res.ok) throw new Error(await res.text());
    
    const data = await res.json();
    uploadedFileName = data.filename;
    currentSessionId = data.session_id;
    
    console.log("Uploaded:", uploadedFileName);
    currentSession.filename = uploadedFileName;
    currentSession.sessionId = currentSessionId;
    
    promptEl.disabled = false;
    promptEl.placeholder = `Ask about ${uploadedFileName}`;
    modelLabel.textContent = `📄 ${uploadedFileName}`;
    
    // Add success notification at top of chat
    appendBubble('ai', `✅ Successfully uploaded and processed: <strong>${uploadedFileName}</strong>.<br><br>Ready for your questions!`);
    
    welcome.style.display = 'none';
    
    newChat();  // Enable chat with new file context
  } catch (e) {
    console.error('Upload failed:', e);
  }
}

// ===== REQUIRED FUNCTIONS =====
async function newChat() {
    currentChatId = null;
    messages.innerHTML = '';
    promptEl.value = '';
    welcome.style.display = currentSession.sessionId ? 'none' : 'flex';
    promptEl.disabled = !currentSession.sessionId;
    promptEl.placeholder = currentSession.sessionId ? 'New chat (RAG enabled)...' : 'Upload document first';
    modelLabel.textContent = 'New Chat';
    tokenChip.style.display = 'none';
    await loadChats();  // Refresh sidebar
}

async function loadChats() {
    try {
        const res = await fetch('/chats');
        if (!res.ok) return;
        const data = await res.json();
        chats = data.chats || [];
        renderSidebar();
    } catch (e) {
        console.error('Load chats error:', e);
    }
}

async function selectChat(chat_id) {
    currentChatId = chat_id;
    await loadChat(chat_id);
    highlightActiveChat(chat_id);
}

async function loadChat(chatId) {
    if (isLoading) return;
    try {
        const res = await fetch(`/chat/${chatId}`);
        if (!res.ok) throw new Error('Chat not found');
        const data = await res.json();
        const chat = data.chat;
        
        messages.innerHTML = '';
        welcome.style.display = 'none';
        promptEl.disabled = false;
        modelLabel.textContent = chat.title;
        
        chat.messages.forEach(msg => {
            appendBubble(msg.role === 'user' ? 'user' : 'ai', msg.content);
        });
        scrollBottom();
        
        updateTokenDisplay(chat.messages.length * 10);  // Approximate
    } catch (e) {
        console.error('Load chat error:', e);
        appendBubble('ai', '**Error:** Chat not found');
    }
}

async function sendMessage() {
    const message = promptEl.value.trim();
    if (!message || isLoading) return;
    
    promptEl.value = '';
    sendBtn.disabled = true;
    isLoading = true;
    
    appendBubble('user', message);
    showLoading();
    
    try {
        const payload = {
            chat_id: currentChatId,
            message: message,
            session_id: currentSession.sessionId,
            file_name: currentSession.filename
        };
        
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        
        // FRESH RELOAD - NO LOCAL STATE
        if (data.chat_id) {
            await loadChat(data.chat_id);
            await loadChats();  // Sync sidebar
        }
        
        updateTokenDisplay(data.tokens);
        
    } catch (err) {
        hideLoading();
        appendBubble('ai', `**Error:** ${err.message}`);
    } finally {
        isLoading = false;
        sendBtn.disabled = true;
        promptEl.focus();
    }
}

async function deleteChat(chat_id) {
    if (!confirm('Delete this chat?')) return;
    try {
        const res = await fetch(`/chat/${chat_id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(await res.text());
        if (currentChatId === chat_id) newChat();
        await loadChats();
    } catch (e) {
        console.error('Delete error:', e);
    }
}

// ===== UI HELPERS =====
function renderSidebar() {
    const chatSection = document.createElement('div');
    chatSection.innerHTML = '<div class="sb-section-label">Chats</div>';
    
    chats.forEach(chat => {
        const item = document.createElement('div');
        item.className = `history-item chat-item ${chat.chat_id === currentChatId ? 'active' : ''}`;
        item.dataset.chatId = chat.chat_id;
        item.innerHTML = `
            <div class="history-title">
                ${escapeHtml(chat.title)}
                <button class="delete-chat-btn" title="Delete">🗑</button>
            </div>
            <div class="history-meta">
                <span>${chat.message_count} msgs</span>
                <span>${new Date(chat.timestamp * 1000).toLocaleDateString()}</span>
            </div>
        `;
        item.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-chat-btn')) {
                deleteChat(chat.chat_id);
            } else {
                selectChat(chat.chat_id);
            }
        });
        chatSection.appendChild(item);
    });
    
    historyContainer.innerHTML = chatSection.outerHTML;
}

function appendBubble(role, content) {
    const row = document.createElement('div');
    row.className = `msg-row ${role}`;
    if (role === 'ai' && content.includes('✅ Successfully uploaded')) {
      row.querySelector('.msg-bubble').classList.add('success-upload');
    const isUser = role === 'user';
    row.innerHTML = `
        <div class="msg-inner">
            ${!isUser ? '<div class="msg-avatar ai">R</div>' : ''}
            <div class="msg-bubble">${renderContent(content, isUser)}</div>
            ${isUser ? '<div class="msg-avatar usr">U</div>' : ''}
        </div>
    `;
    messages.appendChild(row);
    scrollBottom();
}

function showLoading() {
    const row = document.createElement('div');
    row.id = 'loadingRow';
    row.className = 'msg-row ai';
    row.innerHTML = `
        <div class="msg-inner">
            <div class="msg-avatar ai">R</div>
            <div class="msg-bubble">
                <div class="loading-dots"><span></span><span></span><span></span></div>
            </div>
        </div>`;
    messages.appendChild(row);
    scrollBottom();
}

function hideLoading() {
    document.getElementById('loadingRow')?.remove();
}

function updateTokenDisplay(tokens) {
    if (tokenCountEl) {
        tokenCountEl.textContent = `${tokens} tokens`;
        tokenChip.style.display = 'flex';
    }
}

function highlightActiveChat(chatId) {
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.toggle('active', item.dataset.chatId === chatId);
    });
}

function renderContent(text, isUser) {
    let html = escapeHtml(text).replace(/\n/g, '<br>');
    if (!isUser) {
        html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
                  .replace(/`([^`]+)`/g, '<code>$1</code>')
                  .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    }
    return html;
}

function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

function scrollBottom() {
    thread.scrollTop = thread.scrollHeight;
}

// ===== INIT & EVENTS =====
function init() {
    bindEvents();
    setSidebarState(window.innerWidth > 640);
    loadChats();
}

function bindEvents() {
    document.getElementById('newChatIcon').addEventListener('click', newChat);
    document.getElementById('topNewChat')?.addEventListener('click', newChat);
    sendBtn.addEventListener('click', sendMessage);
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', uploadFile);
    
    promptEl.addEventListener('input', () => {
        sendBtn.disabled = !promptEl.value.trim() || isLoading;
        resizeTextarea();
    });
    
    promptEl.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Sidebar toggle
    document.getElementById('sidebarOpen').addEventListener('click', () => setSidebarState(true));
    document.getElementById('sidebarClose').addEventListener('click', () => setSidebarState(false));
    overlay.addEventListener('click', () => setSidebarState(false));
    
    // Dynamic sidebar clicks (delegated)
    historyContainer.addEventListener('click', e => {
        const chatItem = e.target.closest('.chat-item');
        if (chatItem) {
            if (e.target.classList.contains('delete-chat-btn')) {
                deleteChat(chatItem.dataset.chatId);
            } else {
                selectChat(chatItem.dataset.chatId);
            }
        }
    });
}

function setSidebarState(open) {
    sidebarOpen = open;
    sidebar.classList.toggle('hidden', !open);
    overlay.classList.toggle('show', open && window.innerWidth <= 640);
}

function resizeTextarea() {
    promptEl.style.height = 'auto';
    promptEl.style.height = Math.min(promptEl.scrollHeight, 200) + 'px';
}

init();

