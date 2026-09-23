# Tabis VPN Backend для VPS

Легковесный бэкенд для безопасной раздачи ключей VLESS Reality в мобильное приложение **Tabis VPN**.

---

## Как это работает
1. Вы храните ваши VLESS/VMess ссылки в простом файле `servers.txt` на сервере.
2. Приложение Tabis VPN при запуске (или по кнопке «Обновить») обращается к `GET /api/v1/servers`.
3. Бэкенд на лету шифрует ключи алгоритмом **AES-256-CBC**. Никто в сети (провайдеры, DPI, посторонние) не видит реальные адреса серверов и протоколы.
4. Приложение расшифровывает ключи и отображает их как **«Сервер #1»**, **«Сервер #2»** и т.д.
5. Если VPS временно недоступен или нет интернета — приложение продолжает работать на сохранённом кэше.

---

## Вариант 1: Запуск через Docker (Рекомендуемый)

1. Скопируйте папку `backend` на ваш VPS:
   ```bash
   scp -r backend user@YOUR_VPS_IP:/root/tabis-backend
   ```
2. Подключитесь к VPS и перейдите в папку:
   ```bash
   ssh user@YOUR_VPS_IP
   cd /root/tabis-backend
   ```
3. Запустите контейнер:
   ```bash
   docker compose up -d --build
   ```
4. Проверьте работоспособность:
   ```bash
   curl http://localhost:8080/health
   # Ответ: {"status":"ok","service":"tabis-vpn-backend"}
   ```

### Как добавлять или менять серверы:
Просто откройте файл `servers.txt` на VPS:
```bash
nano /root/tabis-backend/servers.txt
```
Вставьте новую ссылку `vless://...` с новой строки и сохраните (`Ctrl+O`, `Enter`, `Ctrl+X`).
Перезапускать контейнер не нужно — изменения применяются мгновенно!

---

## Вариант 2: Запуск без Docker (через systemd)

1. Установите Python и зависимости:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip
   pip3 install -r requirements.txt
   ```
2. Создайте системную службу `sudo nano /etc/systemd/system/tabis-backend.service`:
   ```ini
   [Unit]
   Description=Tabis VPN Backend
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/root/tabis-backend
   ExecStart=/usr/local/bin/uvicorn server:app --host 127.0.0.1 --port 8080
   Restart=always
   RestartSec=3

   [Install]
   WantedBy=multi-user.target
   ```
3. Запустите службу:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now tabis-backend
   ```

---

## Настройка домена и SSL (Nginx + Let's Encrypt)

Чтобы мобильное приложение могло безопасно обращаться к вашему бэкенду по HTTPS:

1. Установите Nginx и Certbot:
   ```bash
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```
2. Создайте конфигурацию сайта `sudo nano /etc/nginx/sites-available/tabis-vpn`:
   ```nginx
   server {
       server_name vpn.yourdomain.com; # Замените на ваш домен

       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
3. Активируйте сайт и выпустите бесплатный SSL:
   ```bash
   sudo ln -s /etc/nginx/sites-available/tabis-vpn /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d vpn.yourdomain.com
   ```
4. Теперь ваш бэкенд доступен по адресу:
   `https://vpn.yourdomain.com/api/v1/servers`
