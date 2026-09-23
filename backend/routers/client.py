import time
import base64
import json
import urllib.parse
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response, Request, Header
from fastapi.responses import PlainTextResponse
import threading
from database import get_db, kick_hy2_user, get_hy2_online_users
from models import TokenActivateReq, TokenReportReq, Hy2AuthReq
from config import notify_token_update, HYSTERIA_SERVER, HYSTERIA_PORT, HYSTERIA_SNI, ADMIN_BYPASS_TOKEN
from core.security import encrypt_aes_cbc_pkcs7, load_server_keys
from core.dependencies import log_audit, resolve_ip_domain_cached
from services.billing_service import check_device_subscription
from services.xray_service import generate_vless_reality_uri

router = APIRouter()

# In-memory tracking for multi-device thrashing detection: token -> list of (timestamp, ip)
_token_ip_history = {}
_token_ip_history_lock = threading.Lock()

def record_and_check_ip_thrashing(token: str, client_ip: str) -> bool:
    """
    Detects if 2+ distinct IPs are actively alternating and competing for the same token
    within a short window (60s). Returns True if rapid concurrent thrashing is detected.
    """
    now = time.time()
    with _token_ip_history_lock:
        history = _token_ip_history.setdefault(token, [])
        # Clean older than 60s
        history = [entry for entry in history if now - entry[0] < 60]
        history.append((now, client_ip))
        _token_ip_history[token] = history

        if len(history) >= 4:
            switches = 0
            for i in range(1, len(history)):
                if history[i][1] != history[i-1][1]:
                    switches += 1
            if switches >= 3:
                return True
    return False

def generate_windows_cmd_installer(user_token: str) -> str:
    return f"""@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Tabis VPN // Fast Installer
color 0A

echo ========================================================
echo         TABIS VPN // WINDOWS FAST INSTALLER
echo ========================================================
echo.

set "TOKEN={user_token}"

if "!TOKEN!"=="" (
    echo Пожалуйста, введите ваш код устройства из Личного кабинета tabisvpn.site/profile:
    set /p "TOKEN=Код доступа: "
)
if "!TOKEN!"=="" set "TOKEN="

echo [1/4] Настройка папки приложения...
set "APP_DIR=%ProgramData%\\TabisVPN"
if not exist "%APP_DIR%" mkdir "%APP_DIR%" >nul 2>&1

echo [2/4] Загрузка конфигурации для ключа !TOKEN!...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://tabisvpn.site/api/v1/client-config/windows?token=!TOKEN!', '%APP_DIR%\\config.yaml')"

if not exist "%APP_DIR%\\hysteria.exe" (
    echo [3/4] Загрузка сетевого ядра Hysteria 2...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://github.com/apernet/hysteria/releases/latest/download/hysteria-windows-amd64.exe', '%APP_DIR%\\hysteria.exe')"
) else (
    echo [3/4] Сетевое ядро уже установлено.
)

echo [4/4] Загрузка скрипта управления и создание ярлыка...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://tabisvpn.site/api/v1/windows-launcher', '%APP_DIR%\\run-vpn.cmd')"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -ComObject WScript.Shell; $desktop = [System.Environment]::GetFolderPath('Desktop'); $shortcut = $WshShell.CreateShortcut($desktop + '\\Tabis VPN.lnk'); $shortcut.TargetPath = '%APP_DIR%\\run-vpn.cmd'; $shortcut.WorkingDirectory = '%APP_DIR%'; $shortcut.IconLocation = '%SystemRoot%\\System32\\shell32.dll,14'; $shortcut.Description = 'Tabis VPN Launcher'; $shortcut.Save()"

echo.
echo ========================================================
echo   [УСПЕХ] Установка Tabis VPN завершена!
echo   Ярлык «Tabis VPN» создан на вашем Рабочем столе.
echo ========================================================
echo.
echo Запуск туннеля...
start "" "%APP_DIR%\\run-vpn.cmd"
timeout /t 3 >nul
exit
"""

@router.post("/api/v1/auth/activate")
def activate_token(req: TokenActivateReq, request: Request):
    """Called by Tabis VPN Android app on first launch or verification."""
    clean_token = req.token.strip().upper()
    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "unknown")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Код доступа не найден")
        
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Check tariff and subscription expiry from user_devices
        ud = conn.execute("SELECT * FROM user_devices WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if ud:
            check_device_subscription(ud["id"], conn)
            ud = conn.execute("SELECT * FROM user_devices WHERE id = ?", (ud["id"],)).fetchone()
            today_str = date.today().isoformat()
            if not ud or not ud["is_active"] or not ud["subscription_expires_at"] or ud["subscription_expires_at"] < today_str:
                raise HTTPException(
                    status_code=403, 
                    detail="Подписка на устройство истекла или не активна. Пополните баланс в личном кабинете https://tabisvpn.site/profile"
                )

            plan = ud["tariff_plan"] or "base"
            if plan == "base":
                LIMIT_100GB = 100 * 1024 * 1024 * 1024
                traffic_used = ud["month_traffic_bytes"] or 0
                if traffic_used >= LIMIT_100GB:
                    raise HTTPException(
                        status_code=403,
                        detail="Месячный лимит трафика (100 ГБ) исчерпан. Смените тариф на Премиум в личном кабинете https://tabisvpn.site/profile"
                    )

        if not row["is_active"]:
            raise HTTPException(status_code=403, detail="Ключ доступа заблокирован администратором")

        if not row["device_id"]:
            conn.execute("""
                UPDATE tokens 
                SET device_id = ?, device_model = ?, last_ip = ?, last_seen_at = ?
                WHERE UPPER(token) = ?
            """, (req.device_id, req.device_model, client_ip, now_str, clean_token))
            conn.commit()
            return {"status": "ok", "message": "Устройство успешно привязано"}

        if row["device_id"] != req.device_id:
            raise HTTPException(
                status_code=403, 
                detail="Код доступа уже привязан к другому устройству. Обратитесь к администратору для сброса привязки."
            )

        conn.execute("""
            UPDATE tokens SET last_ip = ?, last_seen_at = ?, device_model = ?
            WHERE UPPER(token) = ?
        """, (client_ip, now_str, req.device_model, clean_token))
        conn.commit()
        return {"status": "ok", "message": "Устройство верифицировано"}

@router.get("/api/v1/servers")
def get_servers(
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None)
):
    """Returns AES-256-CBC encrypted server keys matching TabisSecurityManager.kt in Android app."""
    auth_token = x_auth_token or x_api_key or token
    if not auth_token and authorization:
        if authorization.startswith("Bearer "):
            auth_token = authorization[7:].strip()
        else:
            auth_token = authorization.strip()

    if not auth_token:
        raise HTTPException(status_code=401, detail="Отсутствует заголовок авторизации")
    
    clean_token = auth_token.strip()
    upper_token = clean_token.upper()

    is_family_key = bool(ADMIN_BYPASS_TOKEN and (clean_token == ADMIN_BYPASS_TOKEN or upper_token == ADMIN_BYPASS_TOKEN.upper()))

    if not is_family_key:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (upper_token,)).fetchone()
            if not row:
                raise HTTPException(status_code=401, detail="Недействительный ключ доступа")
            
            ud = conn.execute("SELECT * FROM user_devices WHERE UPPER(token) = ?", (upper_token,)).fetchone()
            if ud:
                check_device_subscription(ud["id"], conn)
                ud = conn.execute("SELECT * FROM user_devices WHERE id = ?", (ud["id"],)).fetchone()
                today_str = date.today().isoformat()
                if not ud or not ud["is_active"] or not ud["subscription_expires_at"] or ud["subscription_expires_at"] < today_str:
                    raise HTTPException(status_code=403, detail="Подписка на устройство истекла. Пополните баланс в личном кабинете.")

            if not row["is_active"]:
                raise HTTPException(status_code=403, detail="Ключ доступа заблокирован администратором")

    raw_keys = load_server_keys()
    if not raw_keys:
        raise HTTPException(status_code=503, detail="Список серверов временно пуст")

    customized_keys = []
    for k in raw_keys:
        if k.startswith("hy2://") and not is_family_key:
            try:
                base_part, rest = k.split("@", 1)
                customized_keys.append(f"hy2://{upper_token}@{rest}")
            except Exception:
                customized_keys.append(k)
        else:
            customized_keys.append(k)

    # Encrypt each key individually for Android TabisSecurityManager.kt
    encrypted_keys = [encrypt_aes_cbc_pkcs7(k) for k in customized_keys]
    
    # Also provide encrypted full payload for newer / desktop clients
    payload = json.dumps(customized_keys)
    encrypted_data = encrypt_aes_cbc_pkcs7(payload)

    return {
        "status": "ok",
        "count": len(customized_keys),
        "servers": encrypted_keys,
        "data": encrypted_data
    }

@router.get("/api/v1/subscription")
@router.get("/api/v1/sub")
def get_subscription_profile(token: str = Query(...), request: Request = None):
    """Standard base64 subscription format for iOS / v2rayTun / Clash clients."""
    clean_token = token.strip().upper()
    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request and request.client else "unknown")
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    total_limit_bytes = 0
    expire_ts = 0

    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Код доступа не найден")

        ud = conn.execute("SELECT * FROM user_devices WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if ud:
            check_device_subscription(ud["id"], conn)
            ud = conn.execute("SELECT * FROM user_devices WHERE id = ?", (ud["id"],)).fetchone()
            today_str = date.today().isoformat()
            if not ud or not ud["is_active"] or not ud["subscription_expires_at"] or ud["subscription_expires_at"] < today_str:
                raise HTTPException(
                    status_code=403, 
                    detail="Подписка на устройство истекла или не активна. Пополните баланс в личном кабинете https://tabisvpn.site/profile"
                )

            plan = ud["tariff_plan"] or "base"
            if plan == "base":
                LIMIT_100GB = 100 * 1024 * 1024 * 1024
                total_limit_bytes = LIMIT_100GB
                traffic_used = ud["month_traffic_bytes"] or 0
                if traffic_used >= LIMIT_100GB:
                    raise HTTPException(
                        status_code=403,
                        detail="Месячный лимит трафика (100 ГБ) исчерпан. Смените тариф на Премиум в личном кабинете https://tabisvpn.site/profile"
                    )

            if ud["subscription_expires_at"]:
                try:
                    exp_dt = datetime.fromisoformat(ud["subscription_expires_at"])
                    expire_ts = int(exp_dt.timestamp())
                except Exception:
                    pass

        if not row["is_active"]:
            raise HTTPException(status_code=403, detail="Ключ доступа заблокирован администратором")

        conn.execute("UPDATE tokens SET last_ip = ?, last_seen_at = ? WHERE token = ?",
                     (client_ip, now_str, row["token"]))
        conn.commit()

    user_label = row["label"] or "Tabis User"
    safe_label = f"Tabis VPN ({user_label})"
    encoded_label = urllib.parse.quote(safe_label)
    
    hy2_uri = f"hy2://{clean_token}@{HYSTERIA_SERVER}:{HYSTERIA_PORT}?sni={HYSTERIA_SNI}&insecure=0#{encoded_label}"
    vless_uri = generate_vless_reality_uri(clean_token, f"🇸🇪 Швеция (VLESS Reality - iOS) - {user_label}")

    # Standard multi-protocol profile: VLESS Reality (primary for iOS) + Hysteria 2
    sub_text = f"{vless_uri}\n{hy2_uri}\n"
    b64_content = base64.b64encode(sub_text.encode('utf-8')).decode('utf-8')
    
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Subscription-Userinfo": f"upload={row['traffic_up']}; download={row['traffic_down']}; total={total_limit_bytes}; expire={expire_ts}",
        "Profile-Update-Interval": "1"
    }
    return Response(content=b64_content, headers=headers)

@router.get("/api/v1/client/vless-uri")
def get_client_vless_uri(token: str = Query(...)):
    """Returns single direct VLESS Reality URI for the given token."""
    clean_token = token.strip().upper()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Код доступа не найден")
        
        ud = conn.execute("SELECT * FROM user_devices WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if ud:
            check_device_subscription(ud["id"], conn)
            ud = conn.execute("SELECT * FROM user_devices WHERE id = ?", (ud["id"],)).fetchone()
            today_str = date.today().isoformat()
            if not ud or not ud["is_active"] or not ud["subscription_expires_at"] or ud["subscription_expires_at"] < today_str:
                raise HTTPException(status_code=403, detail="Подписка на устройство истекла")

    label = (row["label"] or "iOS") if row else "iOS"
    uri = generate_vless_reality_uri(clean_token, f"Tabis VPN (iOS) - {label}")
    return {"status": "ok", "token": clean_token, "vless_uri": uri}

@router.post("/api/v1/report-traffic")
def report_traffic(req: TokenReportReq):
    """App reports traffic usage in bytes periodically."""
    today_str = date.today().isoformat()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    total_bytes = req.bytes_up + req.bytes_down

    with get_db() as conn:
        conn.execute("""
            UPDATE tokens 
            SET traffic_up = traffic_up + ?, 
                traffic_down = traffic_down + ?, 
                traffic_today_up = CASE WHEN last_reset_day = ? THEN traffic_today_up + ? ELSE ? END,
                traffic_today_down = CASE WHEN last_reset_day = ? THEN traffic_today_down + ? ELSE ? END,
                last_reset_day = ?,
                last_seen_at = ?
            WHERE token = ? AND device_id = ?
        """, (
            req.bytes_up, req.bytes_down,
            today_str, req.bytes_up, req.bytes_up,
            today_str, req.bytes_down, req.bytes_down,
            today_str, now_str, req.token, req.device_id
        ))

        # Accumulate to device and user monthly traffic and enforce 100 GB limit
        udev = conn.execute("SELECT * FROM user_devices WHERE UPPER(token) = ?", (req.token.upper(),)).fetchone()
        if udev:
            conn.execute("UPDATE user_devices SET month_traffic_bytes = month_traffic_bytes + ? WHERE id = ?", (total_bytes, udev["id"]))
            conn.execute("UPDATE users SET month_traffic_bytes = month_traffic_bytes + ? WHERE id = ?", (total_bytes, udev["user_id"]))
            plan = udev["tariff_plan"] or "base"
            if plan == "base":
                LIMIT_100GB = 100 * 1024 * 1024 * 1024
                cur_traffic = (udev["month_traffic_bytes"] or 0) + total_bytes
                if cur_traffic >= LIMIT_100GB:
                    kick_hy2_user(req.token)

        conn.commit()
    return {"status": "ok"}

@router.post("/api/v1/hy2/auth")
def hysteria2_http_auth(req: Hy2AuthReq):
    """
    HTTP Auth webhook called directly by Hysteria 2 server core on client handshake.
    Receives: { "addr": "client_ip:port", "auth": "TOKEN_OR_PASS", "tx": 0 }
    Returns: { "ok": true, "id": "TOKEN" } or { "ok": false, "id": "" }
    """
    raw_auth = (req.auth or "").strip()
    clean_token = raw_auth.upper()

    # Master maintenance key bypass
    if ADMIN_BYPASS_TOKEN and (raw_auth == ADMIN_BYPASS_TOKEN or clean_token == ADMIN_BYPASS_TOKEN.upper()):
        return {"ok": True, "id": "admin_master"}

    client_ip = req.addr.split(':')[0] if req.addr else ""
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            return {"ok": False, "id": ""}
        
        # Check if banned/blocked by admin
        if not row["is_active"]:
            return {"ok": False, "id": ""}

        # Subscription check & Shaping under per-device 2-tier model
        user_dev = conn.execute("SELECT * FROM user_devices WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        tx_limit = 0
        rx_limit = 0
        if user_dev:
            check_device_subscription(user_dev["id"], conn)
            ud = conn.execute("SELECT * FROM user_devices WHERE id = ?", (user_dev["id"],)).fetchone()
            today_str = date.today().isoformat()
            if not ud or not ud["is_active"] or not ud["subscription_expires_at"] or ud["subscription_expires_at"] < today_str:
                print(f"[HY2 AUTH REJECTED] Inactive/expired device for {clean_token}: dev #{user_dev['id']}")
                return {"ok": False, "id": ""}

            plan = ud["tariff_plan"] or "base"
            if plan == "base":
                LIMIT_100GB = 100 * 1024 * 1024 * 1024
                if (ud["month_traffic_bytes"] or 0) >= LIMIT_100GB:
                    print(f"[HY2 AUTH REJECTED] 100GB device traffic limit exceeded for {clean_token}")
                    return {"ok": False, "id": ""}
                # Server-side shaping to 10 Mbps (1,250,000 bytes/sec)
                tx_limit = 1250000
                rx_limit = 1250000

        # === 1 DEVICE PER KEY ENFORCEMENT ===
        # A. Detect concurrent alternating IP thrashing (two devices actively trying to share 1 key)
        if record_and_check_ip_thrashing(clean_token, client_ip):
            print(f"[HY2 MULTI-DEVICE DETECTED] Token {clean_token} sharing violation: alternating IPs {client_ip}. Enforcing 1-device limit.")
            kick_hy2_user(clean_token)
            return {"ok": False, "id": ""}

        # B. Enforce single active session: kick any previous active session if connecting from another IP or if already online
        last_ip = row["last_ip"]
        online_map = get_hy2_online_users()
        is_already_online = online_map.get(clean_token, 0) > 0

        if is_already_online:
            # Token already has a session. Kick it so only the new device session survives.
            kick_hy2_user(clean_token)
            if last_ip and last_ip != client_ip:
                print(f"[HY2 1-DEVICE POLICY] Kicked old session on IP {last_ip} for {clean_token}; new session starting from {client_ip}")

        # Update last seen and last IP in SQLite
        conn.execute("UPDATE tokens SET last_ip = ?, last_seen_at = ? WHERE token = ?",
                     (client_ip, now_str, row["token"]))
        conn.commit()

    # Log real VPN connection with user binding and reverse DNS
    try:
        resolved_host = resolve_ip_domain_cached(client_ip)
        associated_uid = user_dev["user_id"] if user_dev else None
        dev_name = user_dev["device_name"] if user_dev else (row["label"] or "VPN Ключ")
        log_audit(
            action="VPN_CONNECT",
            target=clean_token,
            details=f"Подключение устройства: {dev_name} (Hysteria 2 / QUIC)",
            ip=client_ip,
            client_ip=client_ip,
            user_id=associated_uid,
            dest_ip=HYSTERIA_SERVER,
            dest_domain=HYSTERIA_SNI
        )
    except Exception as log_err:
        print(f"[HY2 AUDIT LOG ERROR] {log_err}")

    notify_token_update("user_connect")
    if tx_limit > 0 and rx_limit > 0:
        return {"ok": True, "id": row["token"], "tx": tx_limit, "rx": rx_limit}
    return {"ok": True, "id": row["token"]}

@router.get("/api/v1/app/version")
def get_app_version():
    """Client in-app auto-update checker."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM app_release WHERE id = 1").fetchone()
        if not row:
            return {
                "version_code": 4000754,
                "version_name": "2.5.1",
                "changelog": "Обновление v2.5.1: улучшен интерфейс чата поддержки, устранено перекрытие клавиатурой и панелью навигации",
                "download_url": "https://tabisvpn.site/downloads/TabisVPN.apk",
                "updated_at": "2026-09-22 00:00:00"
            }
        return {
            "version_code": row["version_code"],
            "version_name": row["version_name"],
            "changelog": row["changelog"] or "",
            "download_url": row["download_url"],
            "updated_at": row["updated_at"]
        }

@router.get("/api/v1/app/download")
def download_android_apk():
    """
    Direct reliable APK download endpoint for mobile clients and web browsers.
    Redirects to the direct VPS Nginx download distribution (/downloads/TabisVPN.apk)
    with safe fallback to official GitHub release.
    """
    import os
    from fastapi.responses import RedirectResponse

    local_apk = "/var/www/tabisvpn/downloads/TabisVPN.apk"
    if os.path.exists(local_apk):
        return RedirectResponse(url="https://tabisvpn.site/downloads/TabisVPN.apk", status_code=302)

    try:
        with get_db() as conn:
            row = conn.execute("SELECT download_url FROM app_release WHERE id = 1").fetchone()
            if row and row["download_url"]:
                return RedirectResponse(url=row["download_url"], status_code=302)
    except Exception:
        pass

    return RedirectResponse(url="https://tabisvpn.site/downloads/TabisVPN.apk", status_code=302)

@router.get("/api/v1/windows-launcher")
def get_windows_launcher():
    launcher_cmd = """@echo off
chcp 65001 >nul
title Tabis VPN // Подключено
color 0B

echo ========================================================
echo            TABIS VPN // ПОДКЛЮЧЕНИЕ АКТИВНО
echo ========================================================
echo.
echo Запуск туннеля Hysteria 2...
start /B "" "%ProgramData%\\TabisVPN\\hysteria.exe" client -c "%ProgramData%\\TabisVPN\\config.yaml"

echo Включение системного прокси...
reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f >nul
reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyServer /t REG_SZ /d "127.0.0.1:10809" /f >nul

echo.
echo --------------------------------------------------------
echo [УСПЕХ] Tabis VPN подключен!
echo Шифрование сетевого трафика активно. Личные данные защищены.
echo Скоростной туннель и оптимизация соединения включены.
echo.
echo НАЖМИТЕ ЛЮБУЮ КЛАВИШУ, ЧТОБЫ ОТКЛЮЧИТЬ VPN...
echo --------------------------------------------------------
pause >nul

echo.
echo Отключение VPN...
taskkill /f /im hysteria.exe >nul 2>&1
reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul
echo VPN отключен.
timeout /t 2 >nul
exit
"""
    return PlainTextResponse(launcher_cmd, media_type="text/plain; charset=utf-8")

@router.get("/api/v1/windows-setup.cmd")
@router.get("/api/v1/windows-setup")
def get_windows_setup_file(token: Optional[str] = Query(None)):
    user_token = (token or "").strip().upper()
    cmd_content = generate_windows_cmd_installer(user_token)
    headers = {
        "Content-Disposition": 'attachment; filename="tabis-vpn-setup.cmd"',
        "Content-Type": "application/octet-stream"
    }
    return Response(content=cmd_content.encode('utf-8'), media_type="application/octet-stream", headers=headers)

@router.get("/api/v1/windows-setup-ps1")
def get_windows_setup_ps1(token: Optional[str] = Query(None)):
    user_token = (token or "").strip().upper()
    ps_content = f"""# Tabis VPN Fast Setup Script for Windows
$ErrorActionPreference = 'Stop'
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   TABIS VPN // WINDOWS FAST INSTALLER   " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan

$Token = "{user_token}"
$InstallDir = "$env:ProgramData\\TabisVPN"
if (!(Test-Path $InstallDir)) {{
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}}

Write-Host "[1/3] Загрузка персональной конфигурации..." -ForegroundColor Yellow
$ConfigUrl = "https://tabisvpn.site/api/v1/client-config/windows?token=$Token"
(New-Object Net.WebClient).DownloadFile($ConfigUrl, "$InstallDir\\config.yaml")

Write-Host "[2/3] Загрузка ядра Hysteria 2..." -ForegroundColor Yellow
$CorePath = "$InstallDir\\hysteria.exe"
if (!(Test-Path $CorePath)) {{
    $CoreUrl = "https://github.com/apernet/hysteria/releases/latest/download/hysteria-windows-amd64.exe"
    (New-Object Net.WebClient).DownloadFile($CoreUrl, $CorePath)
}}

Write-Host "[3/3] Загрузка лаунчера и создание ярлыка..." -ForegroundColor Yellow
$LauncherUrl = "https://tabisvpn.site/api/v1/windows-launcher"
(New-Object Net.WebClient).DownloadFile($LauncherUrl, "$InstallDir\\run-vpn.cmd")

$Desktop = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$Desktop\\Tabis VPN.lnk")
$Shortcut.TargetPath = "$InstallDir\\run-vpn.cmd"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.IconLocation = "$env:SystemRoot\\System32\\shell32.dll,14"
$Shortcut.Description = "Запуск Tabis VPN"
$Shortcut.Save()

Write-Host ""
Write-Host "УСПЕШНО НАСТРОЕНО! Ярлык 'Tabis VPN' создан на рабочем столе." -ForegroundColor Green
Write-Host "Запуск туннеля..." -ForegroundColor Cyan
Start-Process -FilePath "$InstallDir\\run-vpn.cmd"
"""
    return PlainTextResponse(ps_content, media_type="text/plain; charset=utf-8")

@router.get("/api/v1/client-config/windows")
def get_windows_config(token: str = Query(...)):
    clean_token = token.strip().upper()
    yaml_config = f"""server: {HYSTERIA_SERVER}:{HYSTERIA_PORT}
auth: {clean_token}
tls:
  sni: {HYSTERIA_SNI}
  insecure: false
quic:
  initStreamReceiveWindow: 8388608
  maxStreamReceiveWindow: 8388608
  initConnReceiveWindow: 20971520
  maxConnReceiveWindow: 20971520
socks5:
  listen: 127.0.0.1:10808
http:
  listen: 127.0.0.1:10809
bandwidth:
  up: 300 mbps
  down: 300 mbps
"""
    return PlainTextResponse(yaml_config)

@router.post("/api/v1/client/report")
def report_traffic(req: TokenReportReq):
    clean_token = req.token.strip().upper()
    today_str = date.today().isoformat()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Код доступа не найден")

        last_reset = row["last_reset_day"]
        new_today_up = (row["traffic_today_up"] or 0) + req.bytes_up
        new_today_down = (row["traffic_today_down"] or 0) + req.bytes_down

        if last_reset != today_str:
            new_today_up = req.bytes_up
            new_today_down = req.bytes_down

        conn.execute("""
            UPDATE tokens 
            SET traffic_up = traffic_up + ?,
                traffic_down = traffic_down + ?,
                traffic_today_up = ?,
                traffic_today_down = ?,
                last_reset_day = ?,
                last_seen_at = ?
            WHERE UPPER(token) = ?
        """, (req.bytes_up, req.bytes_down, new_today_up, new_today_down, today_str, now_str, clean_token))

        ud = conn.execute("SELECT id, month_traffic_bytes, tariff_plan FROM user_devices WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if ud:
            conn.execute("""
                UPDATE user_devices 
                SET month_traffic_bytes = month_traffic_bytes + ?
                WHERE id = ?
            """, (req.bytes_up + req.bytes_down, ud["id"]))

        conn.commit()

    return {"status": "ok"}

@router.post("/api/v1/client/hy2-auth")
def hysteria2_auth(req: Hy2AuthReq):
    clean_token = (req.auth or "").strip().upper()
    if not clean_token:
        return Response(content="unauthorized", status_code=401)

    today_str = date.today().isoformat()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            return Response(content="user not found", status_code=401)

        ud = conn.execute("SELECT * FROM user_devices WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if ud:
            check_device_subscription(ud["id"], conn)
            ud = conn.execute("SELECT * FROM user_devices WHERE id = ?", (ud["id"],)).fetchone()
            if not ud or not ud["is_active"] or not ud["subscription_expires_at"] or ud["subscription_expires_at"] < today_str:
                return Response(content="subscription expired", status_code=403)

            plan = ud["tariff_plan"] or "base"
            if plan == "base":
                LIMIT_100GB = 100 * 1024 * 1024 * 1024
                traffic_used = ud["month_traffic_bytes"] or 0
                if traffic_used >= LIMIT_100GB:
                    return Response(content="monthly limit exceeded", status_code=403)

        if not row["is_active"]:
            return Response(content="token disabled", status_code=403)

    return Response(content="ok", status_code=200)
