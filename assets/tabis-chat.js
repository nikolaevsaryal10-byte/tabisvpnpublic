/**
 * Tabis VPN — Live Support Chat Widget
 * Operating Hours: 9:00 - 21:00
 */
(function() {
  if (window.__tabisChatInitialized) return;
  window.__tabisChatInitialized = true;

  // Initialize Session
  let sessionToken = localStorage.getItem('tabis_support_session');
  if (!sessionToken) {
    sessionToken = 'chat_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    localStorage.setItem('tabis_support_session', sessionToken);
  }

  let isOpen = false;
  let pollTimer = null;
  let lastMessageCount = 0;
  let isSending = false;

  // Audio chime (subtle synthetic beep using Web Audio API)
  function playNotificationSound() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.22);
    } catch (e) {}
  }

  // Inject Styles
  const styleEl = document.createElement('style');
  styleEl.textContent = `
    #tabis-chat-btn {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 54px;
      height: 54px;
      border-radius: 50%;
      background: #121416;
      color: #ffffff;
      border: 1px solid #2a2e35;
      box-shadow: 0 8px 24px rgba(0,0,0,0.35);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 99999;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      user-select: none;
    }
    #tabis-chat-btn:hover {
      transform: scale(1.06);
      background: #089aff;
      border-color: #089aff;
      box-shadow: 0 10px 28px rgba(8, 154, 255, 0.4);
    }
    #tabis-chat-badge {
      position: absolute;
      top: -3px;
      right: -3px;
      background: #ef4444;
      color: #fff;
      font-size: 11px;
      font-weight: 800;
      font-family: monospace;
      padding: 2px 6px;
      border-radius: 10px;
      border: 2px solid #121416;
      display: none;
    }
    #tabis-chat-window {
      position: fixed;
      bottom: 90px;
      right: 24px;
      width: 380px;
      max-width: calc(100vw - 32px);
      height: 540px;
      max-height: calc(100vh - 120px);
      background: #121416;
      color: #f3f4f6;
      border: 1px solid #282d36;
      border-radius: 12px;
      box-shadow: 0 16px 40px rgba(0,0,0,0.6);
      display: none;
      flex-direction: column;
      z-index: 99999;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      animation: tabisChatFadeIn 0.2s ease-out;
    }
    @keyframes tabisChatFadeIn {
      from { opacity: 0; transform: translateY(12px) scale(0.98); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    .tabis-chat-header {
      padding: 14px 16px;
      background: #0d0f12;
      border-bottom: 1px solid #242932;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .tabis-chat-title-box {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .tabis-chat-avatar {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: #089aff;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      font-weight: bold;
    }
    .tabis-chat-h1 {
      font-size: 14px;
      font-weight: 700;
      color: #fff;
      margin: 0;
      line-height: 1.2;
    }
    .tabis-chat-h2 {
      font-size: 11px;
      color: #089aff;
      font-family: monospace;
      margin: 2px 0 0 0;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .tabis-chat-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #10b981;
    }
    .tabis-chat-close {
      background: transparent;
      border: none;
      color: #9ca3af;
      font-size: 18px;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: 4px;
      line-height: 1;
    }
    .tabis-chat-close:hover {
      color: #fff;
      background: rgba(255,255,255,0.1);
    }
    .tabis-chat-schedule-notice {
      padding: 8px 14px;
      background: rgba(8, 154, 255, 0.08);
      border-bottom: 1px solid rgba(8, 154, 255, 0.15);
      font-size: 11px;
      font-family: monospace;
      color: #cbd5e1;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .tabis-chat-body {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: #121416;
    }
    .tabis-msg {
      max-width: 82%;
      padding: 10px 13px;
      border-radius: 10px;
      font-size: 13px;
      line-height: 1.45;
      word-break: break-word;
      position: relative;
    }
    .tabis-msg-user {
      align-self: flex-end;
      background: #089aff;
      color: #ffffff;
      border-bottom-right-radius: 2px;
    }
    .tabis-msg-admin {
      align-self: flex-start;
      background: #1e232b;
      color: #f3f4f6;
      border: 1px solid #2f3642;
      border-bottom-left-radius: 2px;
    }
    .tabis-msg-author {
      font-size: 10px;
      font-family: monospace;
      color: #38bdf8;
      margin-bottom: 3px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .tabis-msg-time {
      font-size: 9px;
      font-family: monospace;
      opacity: 0.7;
      margin-top: 4px;
      text-align: right;
    }
    .tabis-chat-footer {
      padding: 10px 12px;
      background: #0d0f12;
      border-top: 1px solid #242932;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .tabis-chat-input {
      flex: 1;
      background: #171b21;
      border: 1px solid #2c323d;
      color: #fff;
      padding: 9px 12px;
      border-radius: 8px;
      font-size: 13px;
      outline: none;
      font-family: inherit;
    }
    .tabis-chat-input:focus {
      border-color: #089aff;
    }
    .tabis-chat-send-btn {
      background: #089aff;
      border: none;
      color: #fff;
      width: 36px;
      height: 36px;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s;
    }
    .tabis-chat-send-btn:hover {
      background: #0085e0;
    }
    .tabis-chat-send-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  `;
  document.head.appendChild(styleEl);

  // Inject HTML Elements
  const container = document.createElement('div');
  container.id = 'tabis-chat-widget-root';
  container.innerHTML = `
    <button id="tabis-chat-btn" title="Поддержка Tabis VPN" aria-label="Чат поддержки">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
      </svg>
      <span id="tabis-chat-badge">0</span>
    </button>

    <div id="tabis-chat-window">
      <div class="tabis-chat-header">
        <div class="tabis-chat-title-box">
          <div class="tabis-chat-avatar">T</div>
          <div>
            <div class="tabis-chat-h1">Поддержка Tabis VPN</div>
            <div class="tabis-chat-h2"><span class="tabis-chat-dot"></span> Операторы на связи</div>
          </div>
        </div>
        <button class="tabis-chat-close" id="tabis-chat-close-btn" title="Закрыть">✕</button>
      </div>

      <div class="tabis-chat-schedule-notice">
        <span>🕒</span>
        <span>Поддержка работает с 9:00 до 21:00</span>
      </div>

      <div class="tabis-chat-body" id="tabis-chat-messages">
        <div class="tabis-msg tabis-msg-admin">
          <div class="tabis-msg-author">Поддержка Tabis</div>
          <div>Здравствуйте! Задайте любой вопрос по настройке, тарифам или оплате. Мы на связи с 9:00 до 21:00.</div>
        </div>
      </div>

      <form class="tabis-chat-footer" id="tabis-chat-form">
        <input type="text" id="tabis-chat-input" class="tabis-chat-input" placeholder="Напишите сообщение..." maxlength="3000" autocomplete="off">
        <button type="submit" id="tabis-chat-send-btn" class="tabis-chat-send-btn" title="Отправить">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </form>
    </div>
  `;
  document.body.appendChild(container);

  const chatBtn = document.getElementById('tabis-chat-btn');
  const chatWindow = document.getElementById('tabis-chat-window');
  const chatCloseBtn = document.getElementById('tabis-chat-close-btn');
  const chatForm = document.getElementById('tabis-chat-form');
  const chatInput = document.getElementById('tabis-chat-input');
  const chatMessages = document.getElementById('tabis-chat-messages');
  const chatBadge = document.getElementById('tabis-chat-badge');
  const sendBtn = document.getElementById('tabis-chat-send-btn');

  function toggleChat(open) {
    isOpen = (typeof open === 'boolean') ? open : !isOpen;
    if (isOpen) {
      chatWindow.style.display = 'flex';
      chatBadge.style.display = 'none';
      chatInput.focus();
      fetchHistory();
      startPolling(3000);
    } else {
      chatWindow.style.display = 'none';
      startPolling(15000);
    }
  }

  chatBtn.addEventListener('click', () => toggleChat());
  chatCloseBtn.addEventListener('click', () => toggleChat(false));

  function formatTime(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr.replace(' ', 'T') + 'Z');
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '';
    }
  }

  function renderMessages(msgs) {
    if (!msgs || msgs.length === 0) return;

    let html = `
      <div class="tabis-msg tabis-msg-admin">
        <div class="tabis-msg-author">Поддержка Tabis</div>
        <div>Здравствуйте! Задайте любой вопрос по настройке, тарифам или оплате. Мы на связи с 9:00 до 21:00.</div>
      </div>
    `;

    let unreadCount = 0;
    msgs.forEach(m => {
      const isUser = m.sender_type === 'user';
      if (!isUser && !m.is_read) unreadCount++;

      html += `
        <div class="tabis-msg ${isUser ? 'tabis-msg-user' : 'tabis-msg-admin'}">
          ${!isUser ? `<div class="tabis-msg-author">${m.sender_name || 'Оператор'}</div>` : ''}
          <div>${escapeHtml(m.text)}</div>
          <div class="tabis-msg-time">${formatTime(m.created_at)}</div>
        </div>
      `;
    });

    chatMessages.innerHTML = html;
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Check for new incoming admin message while window closed
    if (msgs.length > lastMessageCount) {
      if (lastMessageCount > 0 && msgs[msgs.length - 1].sender_type === 'admin') {
        playNotificationSound();
        if (!isOpen) {
          chatBadge.innerText = String(unreadCount || 1);
          chatBadge.style.display = 'block';
        }
      }
      lastMessageCount = msgs.length;
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML;
  }

  async function fetchHistory() {
    try {
      const res = await fetch(`/api/v1/support/history?session_token=${encodeURIComponent(sessionToken)}`);
      if (!res.ok) return;
      const data = await res.json();
      renderMessages(data.messages || []);
    } catch (e) {}
  }

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text || isSending) return;

    isSending = true;
    sendBtn.disabled = true;

    // Append optimistic user bubble immediately
    const tempDiv = document.createElement('div');
    tempDiv.className = 'tabis-msg tabis-msg-user';
    tempDiv.innerHTML = `<div>${escapeHtml(text)}</div><div class="tabis-msg-time">отправка...</div>`;
    chatMessages.appendChild(tempDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    chatInput.value = '';

    try {
      const userJwt = localStorage.getItem('tabis_user_token') || '';
      const headers = { 'Content-Type': 'application/json' };
      if (userJwt) headers['Authorization'] = `Bearer ${userJwt}`;

      const res = await fetch('/api/v1/support/message', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          session_token: sessionToken,
          message: text,
          page_url: window.location.pathname
        })
      });

      if (!res.ok) throw new Error('Ошибка отправки');
      const data = await res.json();
      if (data.session_token) {
        sessionToken = data.session_token;
        localStorage.setItem('tabis_support_session', sessionToken);
      }
      await fetchHistory();
    } catch (err) {
      tempDiv.querySelector('.tabis-msg-time').innerText = 'ошибка ✕';
      tempDiv.querySelector('.tabis-msg-time').style.color = '#fca5a5';
    } finally {
      isSending = false;
      sendBtn.disabled = false;
      chatInput.focus();
    }
  });

  function startPolling(interval) {
    clearInterval(pollTimer);
    pollTimer = setInterval(fetchHistory, interval);
  }

  // Initial fetch and start background low-frequency check
  fetchHistory();
  startPolling(15000);
})();
