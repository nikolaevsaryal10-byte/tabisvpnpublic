const { createApp, ref, computed, onMounted, nextTick } = Vue;

  createApp({
    setup() {
      // AUTH STATE
      const authToken = ref(localStorage.getItem('tabis_admin_token') || '');
      const isAuthenticated = computed(() => !!authToken.value);
      const loginForm = ref({ username: '', password: '' });
      const loginLoading = ref(false);
      const loginError = ref('');

      // NAVIGATION
      const currentView = ref('dashboard');
      const isMobileMenuOpen = ref(false);
      const isRefreshing = ref(false);

      const navItems = [
        { id: 'dashboard', title: 'Дашборд & Мониторинг', icon: '📊' },
        { id: 'access', title: 'Аккаунты & Пользователи', icon: '👥' },
        { id: 'traffic', title: 'Логи трафика', icon: '🌐' },
        { id: 'support', title: 'Чат поддержки', icon: '💬' },
        { id: 'reviews', title: 'Модерация отзывов', icon: '⭐' },
        { id: 'server', title: 'Сервер & Службы', icon: '⚙️' },
        { id: 'vault', title: 'Заметки & Блокнот', icon: '🔐' },
        { id: 'audit', title: 'Аудит & Релизы', icon: '🛡️' },
      ];

      const currentViewTitle = computed(() => {
        const f = navItems.find(i => i.id === currentView.value);
        return f ? f.title : 'Управление';
      });

      // TOASTS
      const toasts = ref([]);
      function showToast(text, type = 'info') {
        const id = Date.now() + Math.random();
        const icons = { success: '✓', error: '✕', warning: '⚠️', info: 'ℹ️' };
        toasts.value.push({ id, text, type, icon: icons[type] || 'ℹ️' });
        setTimeout(() => {
          toasts.value = toasts.value.filter(t => t.id !== id);
        }, 4000);
      }

      // SAFE API CLIENT
      async function api(url, method = 'GET', body = null) {
        try {
          const options = {
            method,
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${authToken.value}`
            }
          };
          if (body && method !== 'GET') {
            options.body = JSON.stringify(body);
          }

          const res = await fetch(url, options);
          if (res.status === 401) {
            authToken.value = '';
            localStorage.removeItem('tabis_admin_token');
            showToast('Сессия истекла. Войдите снова.', 'warning');
            return null;
          }

          const data = await res.json();
          if (!res.ok) {
            showToast(data.detail || data.error || 'Ошибка запроса', 'error');
            return null;
          }
          return data;
        } catch (err) {
          console.error('API Network Error:', err);
          showToast('Ошибка сети / связи с сервером', 'error');
          return null;
        }
      }

      // LOGIN / LOGOUT
      async function submitLogin() {
        loginLoading.value = true;
        loginError.value = '';
        try {
          const res = await fetch('/api/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: (loginForm.value.username || '').trim(),
              password: loginForm.value.password || ''
            })
          });
          const data = await res.json();
          if (res.ok && data.token) {
            authToken.value = data.token;
            localStorage.setItem('tabis_admin_token', data.token);
            showToast('Успешный вход в систему!', 'success');
            initApp();
          } else {
            const msg = data.detail || 'Неверный логин или пароль';
            loginError.value = msg;
            showToast(msg, 'error');
          }
        } catch (e) {
          loginError.value = 'Не удалось подключиться к серверу';
          showToast('Не удалось подключиться к серверу', 'error');
        } finally {
          loginLoading.value = false;
        }
      }

      function logout() {
        authToken.value = '';
        localStorage.removeItem('tabis_admin_token');
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
      }

      // METRICS & CHARTS
      const metrics = ref({});
      const chartInstances = {};
      let eventSource = null;
      const sseConnected = ref(false);

      function initCharts() {
        const commonOptions = {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: { 
            legend: { display: false },
            tooltip: {
              mode: 'index',
              intersect: false,
              backgroundColor: '#12161f',
              borderColor: 'rgba(255,255,255,0.15)',
              borderWidth: 1,
              titleColor: '#fff',
              bodyColor: '#e2e8f0',
              padding: 8,
              displayColors: true
            }
          },
          interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false
          },
          elements: {
            line: {
              borderWidth: 1.5,
              tension: 0.25
            },
            point: {
              radius: 0,
              hoverRadius: 4,
              hitRadius: 10
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255,255,255,0.03)' },
              ticks: { color: '#8492A6', font: { family: 'JetBrains Mono', size: 10 }, maxTicksLimit: 6 }
            },
            y: {
              grid: { color: 'rgba(255,255,255,0.04)' },
              ticks: { color: '#8492A6', font: { family: 'JetBrains Mono', size: 10 } }
            }
          }
        };

        const ctxCpu = document.getElementById('chartCpuRam');
        if (ctxCpu && !chartInstances.cpu) {
          chartInstances.cpu = new Chart(ctxCpu, {
            type: 'line',
            data: {
              labels: [],
              datasets: [
                { label: 'CPU %', borderColor: '#00E599', backgroundColor: 'rgba(0,229,153,0.06)', fill: true, tension: 0.25, borderWidth: 1.5, pointRadius: 0, data: [] },
                { label: 'RAM %', borderColor: '#3B82F6', backgroundColor: 'rgba(59,130,246,0.06)', fill: true, tension: 0.25, borderWidth: 1.5, pointRadius: 0, data: [] }
              ]
            },
            options: commonOptions
          });
        }

        const ctxSpeed = document.getElementById('chartSpeed');
        if (ctxSpeed && !chartInstances.speed) {
          chartInstances.speed = new Chart(ctxSpeed, {
            type: 'line',
            data: {
              labels: [],
              datasets: [
                { label: 'Rx (Mbps)', borderColor: '#00E599', tension: 0.25, borderWidth: 1.5, pointRadius: 0, data: [] },
                { label: 'Tx (Mbps)', borderColor: '#3B82F6', tension: 0.25, borderWidth: 1.5, pointRadius: 0, data: [] }
              ]
            },
            options: commonOptions
          });
        }

        const ctxTraffic = document.getElementById('chartTraffic');
        if (ctxTraffic && !chartInstances.traffic) {
          chartInstances.traffic = new Chart(ctxTraffic, {
            type: 'line',
            data: {
              labels: [],
              datasets: [
                { label: 'Входящий (MB)', borderColor: '#00E599', tension: 0.25, borderWidth: 1.5, pointRadius: 0, data: [] },
                { label: 'Исходящий (MB)', borderColor: '#F59E0B', tension: 0.25, borderWidth: 1.5, pointRadius: 0, data: [] }
              ]
            },
            options: commonOptions
          });
        }

        const ctxUsers = document.getElementById('chartUsers');
        if (ctxUsers && !chartInstances.users) {
          chartInstances.users = new Chart(ctxUsers, {
            type: 'line',
            data: {
              labels: [],
              datasets: [
                { label: 'Онлайн', borderColor: '#00E599', backgroundColor: 'rgba(0,229,153,0.08)', fill: true, tension: 0.25, borderWidth: 1.5, pointRadius: 0, data: [] }
              ]
            },
            options: commonOptions
          });
        }
      }

      async function fetchMetrics() {
        const [curr, hist] = await Promise.all([
          api('/api/admin/metrics/current'),
          api('/api/admin/metrics/history?range_hours=24')
        ]);

        if (curr) metrics.value = curr;

        if (hist && Array.isArray(hist) && hist.length > 0) {
          const points = [...hist];
          if (curr && curr.timestamp) {
            const lastTs = points[points.length - 1].timestamp;
            if (curr.timestamp - lastTs >= 20) {
              points.push({
                timestamp: curr.timestamp,
                cpu_percent: curr.cpu_percent,
                ram_percent: curr.ram_percent,
                traffic_today_rx: curr.users?.traffic_today_down_bytes || 0,
                traffic_today_tx: curr.users?.traffic_today_up_bytes || 0,
                net_rx_mbps: curr.net_rx_mbps,
                net_tx_mbps: curr.net_tx_mbps,
                active_users: curr.users?.online_now || 0
              });
            }
          }

          const labels = points.map(p => {
            const d = new Date(p.timestamp * 1000);
            return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
          });

          if (chartInstances.cpu) {
            chartInstances.cpu.data.labels = labels;
            chartInstances.cpu.data.datasets[0].data = points.map(p => p.cpu_percent);
            chartInstances.cpu.data.datasets[1].data = points.map(p => p.ram_percent);
            chartInstances.cpu.update('none');
          }

          if (chartInstances.speed) {
            chartInstances.speed.data.labels = labels;
            chartInstances.speed.data.datasets[0].data = points.map(p => p.net_rx_mbps);
            chartInstances.speed.data.datasets[1].data = points.map(p => p.net_tx_mbps);
            chartInstances.speed.update('none');
          }

          if (chartInstances.traffic) {
            chartInstances.traffic.data.labels = labels;
            chartInstances.traffic.data.datasets[0].data = points.map(p => (p.traffic_today_rx / (1024*1024)).toFixed(1));
            chartInstances.traffic.data.datasets[1].data = points.map(p => (p.traffic_today_tx / (1024*1024)).toFixed(1));
            chartInstances.traffic.update('none');
          }

          if (chartInstances.users) {
            chartInstances.users.data.labels = labels;
            chartInstances.users.data.datasets[0].data = points.map(p => p.active_users);
            chartInstances.users.update('none');
          }
        }
      }

      function startSse() {
        if (!authToken.value) return;
        if (eventSource) eventSource.close();

        eventSource = new EventSource('/api/admin/events?token=' + encodeURIComponent(authToken.value));
        
        eventSource.onopen = () => {
          sseConnected.value = true;
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'metrics' && data.payload) {
              metrics.value = data.payload;
            } else if (data.type === 'support_message') {
              loadSupportDialogs(true);
              if (activeSupportDialog.value) {
                loadSupportMessages(activeSupportDialog.value.id, false);
              }
            } else if (data.type?.startsWith('token_') || data.type?.startsWith('user_') || data.type?.startsWith('device_')) {
              loadUsers(false);
            }
          } catch (e) {
            console.warn('SSE Parse error:', e);
          }
        };

        eventSource.onerror = () => {
          sseConnected.value = false;
        };
      }

      // USERS & DEVICES STATE & FILTERS
      const users = ref([]);
      const expandedUserIds = ref([]);
      const userSearchQuery = ref('');
      const userFilter = ref('all');
      const userSortBy = ref('created_desc');
      const pageSize = ref(15);
      const currentPage = ref(1);

      const countActiveUsers = computed(() => users.value.filter(u => u.balance > 0).length);
      const countZeroUsers = computed(() => users.value.filter(u => u.balance <= 0).length);
      const countWithDevices = computed(() => users.value.filter(u => u.devices && u.devices.length > 0).length);
      const countOnlineUsers = computed(() => users.value.filter(u => u.online_devices > 0).length);

      const filteredUsers = computed(() => {
        let list = users.value;
        const q = userSearchQuery.value.trim().toLowerCase();

        // 1. Search filter
        if (q) {
          list = list.filter(u => {
            const inEmail = u.email && u.email.toLowerCase().includes(q);
            const inNick = u.nickname && u.nickname.toLowerCase().includes(q);
            const inCode = u.user_code && u.user_code.toLowerCase().includes(q);
            const inDevices = u.devices && u.devices.some(d => 
              (d.device_name && d.device_name.toLowerCase().includes(q)) ||
              (d.token && d.token.toLowerCase().includes(q)) ||
              (d.last_ip && d.last_ip.toLowerCase().includes(q)) ||
              (d.device_model && d.device_model.toLowerCase().includes(q))
            );
            return inEmail || inNick || inCode || inDevices;
          });
        }

        // 2. Status Filter
        if (userFilter.value === 'active') {
          list = list.filter(u => u.balance > 0);
        } else if (userFilter.value === 'zero') {
          list = list.filter(u => u.balance <= 0);
        } else if (userFilter.value === 'with_devices') {
          list = list.filter(u => u.devices && u.devices.length > 0);
        } else if (userFilter.value === 'online') {
          list = list.filter(u => u.online_devices > 0);
        }

        // 3. Sort
        list = [...list].sort((a, b) => {
          if (userSortBy.value === 'balance_desc') {
            return (b.balance || 0) - (a.balance || 0);
          } else if (userSortBy.value === 'devices_desc') {
            return (b.devices ? b.devices.length : 0) - (a.devices ? a.devices.length : 0);
          } else if (userSortBy.value === 'traffic_desc') {
            return (b.total_traffic_today_bytes || 0) - (a.total_traffic_today_bytes || 0);
          } else if (userSortBy.value === 'nickname_asc') {
            return (a.nickname || a.email || '').localeCompare(b.nickname || b.email || '');
          }
          return (b.created_at || '').localeCompare(a.created_at || '');
        });

        return list;
      });

      const totalPages = computed(() => Math.max(1, Math.ceil(filteredUsers.value.length / pageSize.value)));

      const paginatedUsers = computed(() => {
        const start = (currentPage.value - 1) * pageSize.value;
        return filteredUsers.value.slice(start, start + pageSize.value);
      });

      function setUserFilter(f) {
        userFilter.value = f;
        currentPage.value = 1;
      }

      function toggleUserExpand(userId) {
        const idx = expandedUserIds.value.indexOf(userId);
        if (idx >= 0) {
          expandedUserIds.value.splice(idx, 1);
        } else {
          expandedUserIds.value.push(userId);
        }
      }

      async function loadUsers(showLoadingToast = false) {
        const res = await api('/api/admin/users');
        if (res && Array.isArray(res)) {
          users.value = res;
          // Expand first user if none expanded yet
          if (expandedUserIds.value.length === 0 && res.length > 0) {
            expandedUserIds.value.push(res[0].id);
          }
          if (showLoadingToast) showToast('Список пользователей обновлен', 'info');
        }
      }

      // USER ACTIONS
      const customBalanceUser = ref(null);
      const customBalanceAmount = ref(60);

      function openCustomBalanceModal(u) {
        customBalanceUser.value = u;
        customBalanceAmount.value = u.balance || 0;
      }

      async function saveCustomBalance() {
        if (!customBalanceUser.value) return;
        const u = customBalanceUser.value;
        const res = await api(`/api/admin/users/${u.id}/balance`, 'POST', {
          amount: parseInt(customBalanceAmount.value) || 0,
          mode: 'set'
        });
        if (res && res.status === 'ok') {
          showToast(`Баланс ${u.email} установлен: ${res.new_balance} ₽`, 'success');
          customBalanceUser.value = null;
          await loadUsers();
        }
      }

      async function adjustUserBalance(u, delta) {
        const res = await api(`/api/admin/users/${u.id}/balance`, 'POST', {
          amount: delta,
          mode: 'delta'
        });
        if (res && res.status === 'ok') {
          showToast(`Баланс ${u.email}: ${delta > 0 ? '+' : ''}${delta} ₽ (Итого: ${res.new_balance} ₽)`, 'info');
          await loadUsers();
        }
      }

      async function deleteUserAccount(u) {
        if (!confirm(`ВНИМАНИЕ: Вы действительно хотите безвозвратно удалить аккаунт ${u.email} (${u.nickname}) со всеми подключенными ключами (${u.devices ? u.devices.length : 0} устр.)?`)) {
          return;
        }
        const res = await api(`/api/admin/users/${u.id}`, 'DELETE');
        if (res && res.status === 'ok') {
          showToast(`Аккаунт ${u.email} удален`, 'info');
          await loadUsers();
        }
      }

      // DEVICE ACTIONS
      async function toggleDeviceActive(device) {
        const res = await api(`/api/admin/devices/${device.id}/toggle`, 'POST');
        if (res && res.status === 'ok') {
          showToast(`Устройство ${device.device_name} ${res.is_active ? 'включено' : 'отключено'}`, 'info');
          await loadUsers();
        }
      }

      async function resetDeviceBinding(device) {
        if (!confirm(`Сбросить аппаратную привязку для устройства ${device.device_name} (${device.token})?`)) return;
        const res = await api(`/api/admin/devices/${device.id}/reset`, 'POST');
        if (res && res.status === 'ok') {
          showToast('Привязка к аппаратному ID сброшена', 'success');
          await loadUsers();
        }
      }

      async function updateDeviceSpeedLimit(device, limitVal) {
        const res = await api(`/api/admin/devices/${device.id}/speed-limit`, 'POST', {
          speed_limit_mbps: parseInt(limitVal) || 0
        });
        if (res && res.status === 'ok') {
          showToast(`Лимит скорости для ${device.device_name} обновлен`, 'success');
          await loadUsers();
        }
      }

      async function deleteDevice(device) {
        if (!confirm(`Удалить устройство ${device.device_name} (ключ ${device.token})?`)) return;
        const res = await api(`/api/admin/devices/${device.id}`, 'DELETE');
        if (res && res.status === 'ok') {
          showToast(`Устройство ${device.device_name} удалено`, 'info');
          await loadUsers();
        }
      }

      // SERVICES & LOGS
      const logService = ref('hysteria');
      const systemLogs = ref('');

      async function controlService(svc, action) {
        showToast(`Выполняется ${action} для ${svc}...`, 'info');
        const res = await api(`/api/admin/services/${svc}/${action}`, 'POST');
        if (res && res.status === 'ok') {
          showToast(`Служба ${svc}: ${action} успешно`, 'success');
          fetchMetrics();
        }
      }

      async function confirmRebootVps() {
        if (!confirm('ВНИМАНИЕ: Вы действительно хотите перезагрузить весь сервер VPS? Все соединения прервутся.')) return;
        const res = await api('/api/admin/reboot', 'POST');
        if (res) {
          showToast('Сервер перезагружается... Страница перезагрузится через 45 сек.', 'warning');
          setTimeout(() => location.reload(), 45000);
        }
      }

      async function fetchLogs() {
        systemLogs.value = 'Получение логов...';
        const res = await api(`/api/admin/logs?service=${logService.value}&lines=100`);
        if (res && res.logs) {
          systemLogs.value = res.logs;
        } else {
          systemLogs.value = 'Логи пусты или служба недоступна.';
        }
      }

      // VAULT NOTES
      const vaultNotes = ref('');
      const isSavingNotes = ref(false);

      async function loadVaultNotes() {
        const res = await api('/api/admin/notes');
        if (res && typeof res.notes === 'string') {
          vaultNotes.value = res.notes;
        }
      }

      async function saveVaultNotes() {
        isSavingNotes.value = true;
        const res = await api('/api/admin/notes', 'POST', { notes: vaultNotes.value });
        isSavingNotes.value = false;
        if (res && res.status === 'ok') {
          showToast('Заметки успешно сохранены', 'success');
        }
      }

      // SUPPORT CHAT
      const supportDialogs = ref([]);
      const activeSupportDialog = ref(null);
      const activeSupportMessages = ref([]);
      const activeSupportLoading = ref(false);
      const supportReplyText = ref('');
      const isSendingSupportReply = ref(false);
      const supportFilter = ref('all');
      const supportSearchQuery = ref('');

      const quickReplies = [
        'Здравствуйте! Чем можем вам помочь?',
        'Уточните, пожалуйста, модель устройства и код из профиля.',
        'Подписка активна, попробуйте перезапустить соединение.',
        'Проблема успешно решена. Приятного пользования!'
      ];

      const supportUnreadTotal = computed(() => {
        return supportDialogs.value.reduce((sum, d) => sum + (d.unread_admin || 0), 0);
      });

      const filteredSupportDialogs = computed(() => {
        let list = supportDialogs.value;
        const q = supportSearchQuery.value.trim().toLowerCase();
        if (q) {
          list = list.filter(d => {
            const inName = d.client_name && d.client_name.toLowerCase().includes(q);
            const inEmail = d.user_email && d.user_email.toLowerCase().includes(q);
            const inCode = d.user_code && d.user_code.toLowerCase().includes(q);
            const inIp = d.client_ip && d.client_ip.toLowerCase().includes(q);
            const inMsg = d.last_message && d.last_message.toLowerCase().includes(q);
            const inGuest = d.guest_id && d.guest_id.toLowerCase().includes(q);
            return inName || inEmail || inCode || inIp || inMsg || inGuest;
          });
        }
        if (supportFilter.value === 'unread') {
          list = list.filter(d => d.unread_admin > 0);
        } else if (supportFilter.value === 'open') {
          list = list.filter(d => d.status === 'open');
        } else if (supportFilter.value === 'closed') {
          list = list.filter(d => d.status === 'closed');
        }
        return list;
      });

      function formatSupportTime(ts) {
        if (!ts) return '';
        try {
          const d = new Date(ts.endsWith('Z') ? ts : ts + 'Z');
          if (isNaN(d.getTime())) return ts;
          const now = new Date();
          const isToday = d.toDateString() === now.toDateString();
          if (isToday) {
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
          }
          return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
          return ts;
        }
      }

      function scrollSupportChatBottom() {
        nextTick(() => {
          const el = document.getElementById('supportMessagesContainer');
          if (el) el.scrollTop = el.scrollHeight;
        });
      }

      async function loadSupportDialogs(silent = false) {
        try {
          const res = await api('/api/admin/support/dialogs');
          if (res && res.dialogs) {
            supportDialogs.value = res.dialogs;
            if (activeSupportDialog.value) {
              const updated = res.dialogs.find(d => d.id === activeSupportDialog.value.id);
              if (updated) {
                activeSupportDialog.value = { ...activeSupportDialog.value, ...updated };
              }
            }
          }
        } catch (e) {
          if (!silent) showToast('Не удалось загрузить диалоги поддержки', 'error');
        }
      }

      async function selectSupportDialog(dlg) {
        activeSupportDialog.value = dlg;
        await loadSupportMessages(dlg.id, true);
        dlg.unread_admin = 0;
      }

      async function loadSupportMessages(dialogId, showLoading = true) {
        if (showLoading) activeSupportLoading.value = true;
        try {
          const res = await api(`/api/admin/support/dialogs/${dialogId}/messages`);
          if (res && res.messages) {
            activeSupportMessages.value = res.messages;
            if (res.dialog && activeSupportDialog.value && activeSupportDialog.value.id === dialogId) {
              activeSupportDialog.value = { ...activeSupportDialog.value, ...res.dialog };
            }
            scrollSupportChatBottom();
          }
        } catch (e) {
          showToast('Ошибка загрузки сообщений', 'error');
        } finally {
          if (showLoading) activeSupportLoading.value = false;
        }
      }

      async function sendSupportReply() {
        const text = supportReplyText.value.trim();
        if (!text || !activeSupportDialog.value || isSendingSupportReply.value) return;

        isSendingSupportReply.value = true;
        try {
          const res = await api(`/api/admin/support/dialogs/${activeSupportDialog.value.id}/reply`, 'POST', {
            text: text,
            operator_name: 'Поддержка Tabis'
          });
          if (res && res.success) {
            supportReplyText.value = '';
            await loadSupportMessages(activeSupportDialog.value.id, false);
            await loadSupportDialogs(true);
            showToast('Ответ отправлен клиенту', 'success');
          }
        } catch (e) {
          showToast('Не удалось отправить ответ', 'error');
        } finally {
          isSendingSupportReply.value = false;
        }
      }

      function applyQuickReply(tmpl) {
        if (supportReplyText.value) {
          supportReplyText.value += ' ' + tmpl;
        } else {
          supportReplyText.value = tmpl;
        }
      }

      async function toggleSupportDialogStatus() {
        if (!activeSupportDialog.value) return;
        const newStatus = activeSupportDialog.value.status === 'open' ? 'closed' : 'open';
        const res = await api(`/api/admin/support/dialogs/${activeSupportDialog.value.id}/status`, 'POST', {
          status: newStatus
        });
        if (res && res.success) {
          activeSupportDialog.value.status = newStatus;
          const found = supportDialogs.value.find(d => d.id === activeSupportDialog.value.id);
          if (found) found.status = newStatus;
          showToast(newStatus === 'open' ? 'Диалог открыт' : 'Диалог закрыт', 'info');
        }
      }

      async function deleteSupportDialog(dlg) {
        if (!confirm(`Удалить диалог #${dlg.id} и всю историю переписки?`)) return;
        const res = await api(`/api/admin/support/dialogs/${dlg.id}`, 'DELETE');
        if (res && res.success) {
          showToast('Диалог удален', 'info');
          if (activeSupportDialog.value && activeSupportDialog.value.id === dlg.id) {
            activeSupportDialog.value = null;
            activeSupportMessages.value = [];
          }
          await loadSupportDialogs(true);
        }
      }

      // REVIEWS MODERATION
      const adminReviews = ref([]);

      async function loadAdminReviews() {
        const res = await api('/api/admin/reviews');
        if (res && res.reviews) {
          adminReviews.value = res.reviews;
        }
      }

      async function toggleApproveReview(rev) {
        const res = await api(`/api/admin/reviews/${rev.id}/approve`, 'POST');
        if (res && res.status === 'ok') {
          rev.approved = res.approved;
          showToast(res.approved ? 'Отзыв одобрен и опубликован!' : 'Отзыв скрыт с сайта', 'success');
        }
      }

      async function deleteAdminReview(rev) {
        if (!confirm(`Удалить отзыв #${rev.id} от ${rev.author_name}?`)) return;
        const res = await api(`/api/admin/reviews/${rev.id}`, 'DELETE');
        if (res && res.status === 'ok') {
          showToast('Отзыв удален', 'info');
          await loadAdminReviews();
        }
      }

      // AUDIT & RELEASES
      const auditLogs = ref([]);
      const appReleaseForm = ref({
        version_code: 747,
        version_name: '2.3.7',
        changelog: '',
        download_url: 'https://tabisvpn.site/TabisVPN.apk',
        updated_at: ''
      });
      const isSavingRelease = ref(false);

      async function loadAuditLogs() {
        const res = await api('/api/admin/audit-logs');
        if (res && Array.isArray(res)) {
          auditLogs.value = res;
        }
      }

      async function loadAppRelease() {
        const res = await api('/api/admin/app/release');
        if (res && res.version_code) {
          appReleaseForm.value = res;
        }
      }

      async function saveAppRelease() {
        isSavingRelease.value = true;
        const res = await api('/api/admin/app/release', 'POST', {
          version_code: appReleaseForm.value.version_code,
          version_name: appReleaseForm.value.version_name,
          changelog: appReleaseForm.value.changelog,
          download_url: appReleaseForm.value.download_url
        });
        isSavingRelease.value = false;
        if (res && res.status === 'ok') {
          showToast('Новая версия приложения успешно опубликована!', 'success');
          loadAppRelease();
          loadAuditLogs();
        }
      }

      async function downloadDbBackup() {
        showToast('Подготовка резервной копии...', 'info');
        try {
          const res = await fetch('/api/admin/backup/download', {
            headers: { 'Authorization': `Bearer ${authToken.value}` }
          });
          if (!res.ok) {
            showToast('Ошибка скачивания бэкапа', 'error');
            return;
          }
          const blob = await res.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `tabis_backup_${new Date().toISOString().slice(0,10)}.db`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(url);
          showToast('Резервная копия базы данных скачана!', 'success');
        } catch (e) {
          showToast('Сбой скачивания файла', 'error');
        }
      }

      // TRAFFIC AUDIT (180 DAYS)
      const trafficLogs = ref([]);
      const trafficStats = ref({});
      const trafficTotal = ref(0);
      const trafficPage = ref(1);
      const trafficLimit = ref(50);
      const trafficPages = ref(1);
      const trafficSearch = ref('');
      const trafficEventType = ref('all');
      const trafficPeriod = ref('180d');
      const trafficLoading = ref(false);

      async function loadTrafficStats() {
        const res = await api('/api/admin/traffic/stats');
        if (res && res.total_records !== undefined) {
          trafficStats.value = res;
        }
      }

      async function loadTrafficLogs(resetPage = false) {
        if (resetPage) trafficPage.value = 1;
        trafficLoading.value = true;
        try {
          const params = new URLSearchParams({
            page: trafficPage.value,
            limit: trafficLimit.value,
            period: trafficPeriod.value
          });
          if (trafficSearch.value.trim()) {
            params.append('search', trafficSearch.value.trim());
          }
          if (trafficEventType.value && trafficEventType.value !== 'all') {
            params.append('event_type', trafficEventType.value);
          }

          const res = await api(`/api/admin/traffic/logs?${params.toString()}`);
          if (res && res.logs) {
            trafficLogs.value = res.logs;
            trafficTotal.value = res.total;
            trafficPage.value = res.page;
            trafficPages.value = res.pages;
          }
        } finally {
          trafficLoading.value = false;
        }
      }

      function changeTrafficPage(newPage) {
        if (newPage < 1 || newPage > trafficPages.value) return;
        trafficPage.value = newPage;
        loadTrafficLogs(false);
      }

      function filterByDomain(domain) {
        trafficSearch.value = domain;
        trafficEventType.value = 'all';
        loadTrafficLogs(true);
      }

      async function exportTrafficCsv() {
        showToast('Формирование CSV архива...', 'info');
        try {
          const params = new URLSearchParams({
            period: trafficPeriod.value
          });
          if (trafficSearch.value.trim()) {
            params.append('search', trafficSearch.value.trim());
          }
          if (trafficEventType.value && trafficEventType.value !== 'all') {
            params.append('event_type', trafficEventType.value);
          }

          const res = await fetch(`/api/admin/traffic/export?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${authToken.value}` }
          });
          if (!res.ok) {
            showToast('Ошибка при скачивании CSV архива', 'error');
            return;
          }
          const blob = await res.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `tabis_traffic_audit_${new Date().toISOString().slice(0, 10)}.csv`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(url);
          showToast('CSV архив успешно скачан!', 'success');
        } catch (e) {
          showToast('Ошибка соединения при скачивании CSV', 'error');
        }
      }

      // HELPERS
      function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
      }

      function copyText(text, successMsg = 'Скопировано в буфер!') {
        if (!text) return;
        navigator.clipboard.writeText(text).then(() => {
          showToast(successMsg, 'success');
        }).catch(() => {
          showToast('Не удалось скопировать', 'error');
        });
      }

      function selectView(vId) {
        currentView.value = vId;
        isMobileMenuOpen.value = false;
        if (vId === 'traffic' && trafficLogs.value.length === 0) {
          loadTrafficLogs(true);
          loadTrafficStats();
        }
        refreshActiveView();
      }

      async function refreshActiveView() {
        isRefreshing.value = true;
        if (currentView.value === 'dashboard') {
          await fetchMetrics();
        } else if (currentView.value === 'access') {
          await loadUsers(true);
        } else if (currentView.value === 'traffic') {
          await Promise.all([loadTrafficLogs(), loadTrafficStats()]);
        } else if (currentView.value === 'support') {
          await loadSupportDialogs();
          if (activeSupportDialog.value) {
            await loadSupportMessages(activeSupportDialog.value.id, false);
          }
        } else if (currentView.value === 'server') {
          await fetchLogs();
        } else if (currentView.value === 'reviews') {
          await loadAdminReviews();
        } else if (currentView.value === 'vault') {
          await loadVaultNotes();
        } else if (currentView.value === 'audit') {
          await Promise.all([loadAuditLogs(), loadAppRelease()]);
        }
        setTimeout(() => { isRefreshing.value = false; }, 300);
      }

      function initApp() {
        nextTick(() => {
          initCharts();
          fetchMetrics();
          loadUsers();
          loadSupportDialogs(true);
          startSse();

          // Focus refresh
          document.addEventListener('visibilitychange', () => {
            if (!document.hidden && authToken.value) {
              if (currentView.value === 'dashboard') fetchMetrics();
              else if (currentView.value === 'access') loadUsers();
              else if (currentView.value === 'support') {
                loadSupportDialogs(true);
                if (activeSupportDialog.value) loadSupportMessages(activeSupportDialog.value.id, false);
              }
            }
          });

          // Heartbeat 60s
          setInterval(() => {
            if (authToken.value && !document.hidden && currentView.value === 'dashboard') {
              fetchMetrics();
            }
          }, 60000);
        });
      }

      onMounted(() => {
        if (authToken.value) {
          initApp();
        }
      });

      return {
        authToken,
        isAuthenticated,
        loginForm,
        loginLoading,
        loginError,
        submitLogin,
        logout,
        currentView,
        currentViewTitle,
        isMobileMenuOpen,
        isRefreshing,
        navItems,
        selectView,
        refreshActiveView,
        toasts,
        metrics,
        sseConnected,
        users,
        expandedUserIds,
        toggleUserExpand,
        userSearchQuery,
        userFilter,
        userSortBy,
        pageSize,
        currentPage,
        totalPages,
        filteredUsers,
        paginatedUsers,
        countActiveUsers,
        countZeroUsers,
        countWithDevices,
        countOnlineUsers,
        setUserFilter,
        customBalanceUser,
        customBalanceAmount,
        openCustomBalanceModal,
        saveCustomBalance,
        adjustUserBalance,
        deleteUserAccount,
        toggleDeviceActive,
        resetDeviceBinding,
        updateDeviceSpeedLimit,
        deleteDevice,
        loadUsers,
        logService,
        systemLogs,
        controlService,
        confirmRebootVps,
        fetchLogs,
        vaultNotes,
        isSavingNotes,
        saveVaultNotes,
        supportDialogs,
        activeSupportDialog,
        activeSupportMessages,
        activeSupportLoading,
        supportReplyText,
        isSendingSupportReply,
        supportFilter,
        supportSearchQuery,
        quickReplies,
        supportUnreadTotal,
        filteredSupportDialogs,
        formatSupportTime,
        loadSupportDialogs,
        selectSupportDialog,
        loadSupportMessages,
        sendSupportReply,
        applyQuickReply,
        toggleSupportDialogStatus,
        deleteSupportDialog,
        adminReviews,
        loadAdminReviews,
        toggleApproveReview,
        deleteAdminReview,
        auditLogs,
        appReleaseForm,
        isSavingRelease,
        loadAuditLogs,
        loadAppRelease,
        saveAppRelease,
        downloadDbBackup,
        trafficLogs,
        trafficStats,
        trafficTotal,
        trafficPage,
        trafficLimit,
        trafficPages,
        trafficSearch,
        trafficEventType,
        trafficPeriod,
        trafficLoading,
        loadTrafficLogs,
        loadTrafficStats,
        changeTrafficPage,
        filterByDomain,
        exportTrafficCsv,
        formatBytes,
        copyText
      };
    }
  }).mount('#app');
