import os
import io
import csv
import sys
import time
import secrets
import hashlib
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, Query, Response, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from database import get_db, kick_hy2_user
from config import (
    ADMIN_SESSIONS, ADMIN_SSE_SUBSCRIBERS, ALLOWED_FS_ROOTS, DB_PATH, notify_token_update
)
from models import (
    AdminLoginReq, AdminUserBalanceReq, AdminDeviceSpeedLimitReq,
    TokenGenerateReq, TokenLabelReq, TokenSpeedLimitReq, TokenUpdateReq,
    ServiceControlReq, FsWriteReq, VaultNotesReq, SupportAdminReplyReq, SupportStatusReq
)
from core.dependencies import (
    verify_admin, check_login_rate_limit, record_login_failure, record_login_success, log_audit
)
from core.security import generate_device_token
from services.metrics_service import probe
from services.billing_service import check_user_subscription

router = APIRouter()

# --- ADMIN AUTH & SSE ---

@router.post("/api/admin/login")
def admin_login(req: AdminLoginReq, request: Request):
    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "unknown")
    check_login_rate_limit(client_ip)

    with get_db() as conn:
        row = conn.execute("SELECT * FROM admins WHERE username = ?", (req.username,)).fetchone()
        if not row:
            record_login_failure(client_ip)
            log_audit("LOGIN_FAILED", req.username, "Неверный логин", client_ip)
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
        h = hashlib.sha256(req.password.encode('utf-8')).hexdigest()
        if row["password_hash"] != h:
            record_login_failure(client_ip)
            log_audit("LOGIN_FAILED", req.username, "Неверный пароль", client_ip)
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    record_login_success(client_ip)
    log_audit("LOGIN_SUCCESS", req.username, "Успешный вход в админ-панель", client_ip)

    session_token = secrets.token_hex(32)
    ADMIN_SESSIONS[session_token] = {
        "username": req.username,
        "expires": time.time() + 3600
    }
    return {"status": "ok", "token": session_token, "username": req.username}

@router.get("/api/admin/events")
async def sse_events(token: str = Query(...)):
    """Server-Sent Events stream for instant token updates across admin tabs."""
    session = ADMIN_SESSIONS.get(token)
    if not session or session["expires"] < time.time():
        raise HTTPException(status_code=401, detail="Сессия недействительна")

    queue = asyncio.Queue()
    ADMIN_SSE_SUBSCRIBERS.append(queue)

    async def event_generator():
        try:
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield f"data: {{\"type\": \"{event}\"}}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in ADMIN_SSE_SUBSCRIBERS:
                ADMIN_SSE_SUBSCRIBERS.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# --- METRICS & SYSTEM STATS ---

@router.get("/api/admin/metrics/current")
def get_current_metrics(admin: str = Depends(verify_admin)):
    instant = probe.sample()
    
    def run_cmd(cmd):
        try:
            return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
        except Exception:
            return ""

    disk_info = run_cmd("df -h / | awk 'NR==2{printf \"%s/%s (%s)\", $3,$2,$5}'")
    uptime_str = run_cmd("uptime -p")
    load_avg = run_cmd("uptime | awk -F'load average:' '{ print $2 }'").strip()

    hysteria_active = "active" in run_cmd("systemctl is-active hysteria-server")
    nginx_active = "active" in run_cmd("systemctl is-active nginx")
    backend_active = "active" in run_cmd("systemctl is-active tabis-backend")

    today_str = date.today().isoformat()
    now_ts = int(time.time())
    cutoff_dt = datetime.utcfromtimestamp(now_ts - 300).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        total_tokens = conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
        bound_tokens = conn.execute("SELECT COUNT(*) FROM tokens WHERE device_id IS NOT NULL").fetchone()[0]
        active_now = conn.execute("SELECT COUNT(*) FROM tokens WHERE is_active = 1 AND last_seen_at >= ?", (cutoff_dt,)).fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_devices = conn.execute("SELECT COUNT(*) FROM user_devices").fetchone()[0]
        total_up = conn.execute("SELECT SUM(traffic_up) FROM tokens").fetchone()[0] or 0
        total_down = conn.execute("SELECT SUM(traffic_down) FROM tokens").fetchone()[0] or 0
        today_up = conn.execute("SELECT SUM(traffic_today_up) FROM tokens WHERE last_reset_day = ?", (today_str,)).fetchone()[0] or 0
        today_down = conn.execute("SELECT SUM(traffic_today_down) FROM tokens WHERE last_reset_day = ?", (today_str,)).fetchone()[0] or 0

    return {
        "timestamp": instant["timestamp"],
        "cpu_percent": instant["cpu_percent"],
        "load_avg": load_avg,
        "ram_used_mb": instant["ram_used_mb"],
        "ram_total_mb": instant["ram_total_mb"],
        "ram_percent": instant["ram_percent"],
        "net_rx_mbps": instant["net_rx_mbps"],
        "net_tx_mbps": instant["net_tx_mbps"],
        "disk": disk_info,
        "uptime": uptime_str,
        "services": {
            "hysteria": hysteria_active,
            "nginx": nginx_active,
            "backend": backend_active
        },
        "users": {
            "total_users": total_users,
            "total": total_devices or total_tokens,
            "active_devices": bound_tokens,
            "online_now": active_now,
            "traffic_up_bytes": total_up,
            "traffic_down_bytes": total_down,
            "traffic_today_up_bytes": today_up,
            "traffic_today_down_bytes": today_down,
        }
    }

@router.get("/api/admin/metrics/history")
def get_metrics_history(range_hours: int = Query(24, ge=1, le=48), admin: str = Depends(verify_admin)):
    since_ts = int(time.time()) - (range_hours * 3600)
    with get_db() as conn:
        rows = conn.execute("""
            SELECT timestamp, cpu_percent, ram_used_mb, ram_total_mb, ram_percent, 
                   net_rx_mbps, net_tx_mbps, traffic_today_rx, traffic_today_tx, active_users
            FROM server_metrics
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since_ts,)).fetchall()
        return [dict(r) for r in rows]

@router.get("/api/admin/stats")
def system_stats(admin: str = Depends(verify_admin)):
    current = get_current_metrics(admin)
    return {
        "ram": f"{current['ram_used_mb']}/{current['ram_total_mb']} MB ({current['ram_percent']}%)",
        "disk": current["disk"],
        "cpu": current["load_avg"],
        "uptime": current["uptime"],
        "services": current["services"],
        "users": current["users"]
    }

# --- ACCESS & TOKENS ---

@router.get("/api/admin/tokens")
def list_tokens(admin: str = Depends(verify_admin)):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tokens ORDER BY created_at DESC").fetchall()
        result = []
        now = datetime.utcnow()
        for r in rows:
            d = dict(r)
            is_online = False
            if d.get("last_seen_at"):
                try:
                    last_seen_dt = datetime.fromisoformat(d["last_seen_at"])
                    if (now - last_seen_dt).total_seconds() < 300:
                        is_online = True
                except Exception:
                    pass
            d["is_online"] = is_online
            result.append(d)
        return result

@router.post("/api/admin/tokens/generate")
def generate_token(req: TokenGenerateReq, admin: str = Depends(verify_admin)):
    new_tok = generate_device_token()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    today_str = date.today().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO tokens (token, label, last_reset_day, created_at)
            VALUES (?, ?, ?, ?)
        """, (new_tok, req.label or "Новое устройство", today_str, now_str))
        conn.commit()

    log_audit("TOKEN_CREATE", new_tok, f"Создан ключ: {req.label}")
    notify_token_update()
    return {"status": "ok", "token": new_tok}

@router.patch("/api/admin/tokens/{token}")
def update_token(token: str, req: TokenUpdateReq, admin: str = Depends(verify_admin)):
    clean_token = token.strip().upper()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ключ доступа не найден")

        updates = []
        params = []
        if req.label is not None:
            updates.append("label = ?")
            params.append(req.label)
        if req.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if req.is_active else 0)
            if not req.is_active:
                kick_hy2_user(clean_token)
        if req.speed_limit_mbps is not None:
            updates.append("speed_limit_mbps = ?")
            params.append(req.speed_limit_mbps)

        if updates:
            params.append(clean_token)
            conn.execute(f"UPDATE tokens SET {', '.join(updates)} WHERE UPPER(token) = ?", tuple(params))
            conn.commit()

    log_audit("TOKEN_UPDATE", clean_token, f"Обновлен: {req.dict(exclude_none=True)}")
    notify_token_update()
    return {"status": "ok"}

@router.delete("/api/admin/tokens/{token}")
def delete_token(token: str, admin: str = Depends(verify_admin)):
    clean_token = token.strip().upper()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ключ доступа не найден")

        conn.execute("DELETE FROM tokens WHERE UPPER(token) = ?", (clean_token,))
        conn.execute("DELETE FROM user_devices WHERE UPPER(token) = ?", (clean_token,))
        conn.commit()

    kick_hy2_user(clean_token)
    log_audit("TOKEN_DELETE", clean_token, "Удален ключ доступа")
    notify_token_update()
    return {"status": "ok"}

@router.post("/api/admin/tokens/{token}/reset-binding")
def reset_binding(token: str, admin: str = Depends(verify_admin)):
    clean_token = token.strip().upper()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ключ доступа не найден")

        conn.execute("UPDATE tokens SET device_id = NULL, device_model = NULL WHERE UPPER(token) = ?", (clean_token,))
        conn.commit()

    kick_hy2_user(clean_token)
    log_audit("TOKEN_RESET_BINDING", clean_token, "Сброшена привязка к устройству")
    notify_token_update()
    return {"status": "ok", "message": "Привязка к устройству успешно сброшена"}

@router.patch("/api/admin/tokens/{token}/speed-limit")
def set_speed_limit(token: str, req: TokenSpeedLimitReq, admin: str = Depends(verify_admin)):
    clean_token = token.strip().upper()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE UPPER(token) = ?", (clean_token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ключ доступа не найден")

        conn.execute("UPDATE tokens SET speed_limit_mbps = ? WHERE UPPER(token) = ?", (req.speed_limit_mbps, clean_token))
        conn.commit()

    log_audit("TOKEN_SPEED_LIMIT", clean_token, f"Лимит скорости: {req.speed_limit_mbps} Мбит/с")
    notify_token_update()
    return {"status": "ok", "speed_limit_mbps": req.speed_limit_mbps}

# --- USERS & DEVICES ---

@router.get("/api/admin/users")
def admin_get_users(admin: str = Depends(verify_admin)):
    today_str = date.today().isoformat()
    now = datetime.utcnow()
    with get_db() as conn:
        users = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
        result = []
        for u in users:
            u_dict = dict(u)
            user_id = u["id"]
            devices_rows = conn.execute("""
                SELECT ud.*, t.last_ip, t.last_seen_at, t.traffic_up, t.traffic_down, 
                       t.traffic_today_up, t.traffic_today_down, t.last_reset_day,
                       t.device_model, t.speed_limit_mbps as token_speed_limit,
                       t.is_active as token_is_active
                FROM user_devices ud
                LEFT JOIN tokens t ON UPPER(t.token) = UPPER(ud.token)
                WHERE ud.user_id = ?
                ORDER BY ud.id ASC
            """, (user_id,)).fetchall()

            devices = []
            online_count = 0
            active_count = 0
            total_today_traffic = 0
            total_traffic_all = 0
            total_month_traffic = 0
            daily_expense_rub = 0

            for d in devices_rows:
                dev = dict(d)
                last_seen = dev.get("last_seen_at") or ""
                is_online = False
                if last_seen:
                    try:
                        seen_dt = datetime.fromisoformat(last_seen)
                        if (now - seen_dt).total_seconds() < 300:
                            is_online = True
                            online_count += 1
                    except Exception:
                        pass
                dev["is_online"] = is_online

                # Handle today's traffic reset if last_reset_day is not today
                traffic_today_up = dev.get("traffic_today_up") or 0
                traffic_today_down = dev.get("traffic_today_down") or 0
                if dev.get("last_reset_day") != today_str:
                    traffic_today_up = 0
                    traffic_today_down = 0

                dev["traffic_today_up"] = traffic_today_up
                dev["traffic_today_down"] = traffic_today_down
                today_bytes = traffic_today_up + traffic_today_down
                total_today_traffic += today_bytes
                dev["traffic_today_total"] = today_bytes

                traffic_up = dev.get("traffic_up") or 0
                traffic_down = dev.get("traffic_down") or 0
                dev["traffic_up"] = traffic_up
                dev["traffic_down"] = traffic_down
                traffic_total = traffic_up + traffic_down

                month_traffic = max(dev.get("month_traffic_bytes") or 0, traffic_total)
                dev["month_traffic_bytes"] = month_traffic
                dev["traffic_total"] = traffic_total
                total_traffic_all += traffic_total
                total_month_traffic += month_traffic

                plan = dev.get("tariff_plan") or "base"
                cost_day = 8 if plan == "premium" else 2
                dev["daily_cost_rub"] = cost_day
                dev["monthly_cost_rub"] = 240 if plan == "premium" else 60
                dev["tariff_name"] = "Премиум" if plan == "premium" else "Базовый"
                dev["traffic_limit_gb"] = 0 if plan == "premium" else 100
                dev["traffic_gb"] = round(month_traffic / (1024 * 1024 * 1024), 2)
                if month_traffic > 0 and dev["traffic_gb"] == 0.0:
                    dev["traffic_gb"] = 0.01

                is_dev_active = bool(dev.get("is_active") and dev.get("token_is_active", 1))
                dev["is_active"] = 1 if is_dev_active else 0
                if is_dev_active:
                    active_count += 1
                    daily_expense_rub += cost_day

                devices.append(dev)

            u_dict["devices"] = devices
            u_dict["total_devices"] = len(devices)
            u_dict["active_devices"] = active_count
            u_dict["online_devices"] = online_count
            u_dict["total_traffic_today_bytes"] = total_today_traffic
            u_dict["total_traffic_bytes"] = total_traffic_all
            u_dict["total_month_traffic_bytes"] = total_month_traffic
            u_dict["daily_expense_rub"] = daily_expense_rub
            result.append(u_dict)
        return result

@router.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin: str = Depends(verify_admin)):
    with get_db() as conn:
        u = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not u:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        dev_tokens = [r[0] for r in conn.execute("SELECT token FROM user_devices WHERE user_id = ?", (user_id,)).fetchall()]
        for tok in dev_tokens:
            conn.execute("DELETE FROM tokens WHERE token = ?", (tok,))
            kick_hy2_user(tok)
            
        conn.execute("DELETE FROM user_devices WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM payments WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM referral_logs WHERE referrer_id = ? OR referred_user_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        
    log_audit("USER_DELETE", u["email"], f"Удален аккаунт #{user_id}")
    notify_token_update()
    return {"status": "ok", "message": f"Пользователь {u['email']} и все устройства удалены"}

@router.post("/api/admin/users/{user_id}/balance")
def admin_update_user_balance(user_id: int, req: AdminUserBalanceReq, admin: str = Depends(verify_admin)):
    with get_db() as conn:
        u = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not u:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        old_bal = u["balance"] or 0
        new_bal = old_bal + req.amount if req.mode == "delta" else req.amount
        new_bal = max(0, new_bal)
        
        conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_bal, user_id))
        
        # Check and activate subscriptions for all user devices
        check_user_subscription(user_id, conn)
        
        # Sync active status to Hysteria 2 tokens
        devs = conn.execute("SELECT token, is_active FROM user_devices WHERE user_id = ?", (user_id,)).fetchall()
        for d in devs:
            conn.execute("UPDATE tokens SET is_active = ? WHERE token = ?", (d["is_active"], d["token"]))
            if not d["is_active"]:
                kick_hy2_user(d["token"])
                
        conn.commit()
        
    log_audit("BALANCE_CHANGE", u["email"], f"Баланс изменен с {old_bal} ₽ на {new_bal} ₽")
    notify_token_update()
    return {"status": "ok", "new_balance": new_bal}

@router.post("/api/admin/devices/{device_id}/speed-limit")
def admin_set_device_speed(device_id: int, req: AdminDeviceSpeedLimitReq, admin: str = Depends(verify_admin)):
    with get_db() as conn:
        dev = conn.execute("SELECT * FROM user_devices WHERE id = ?", (device_id,)).fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail="Устройство не найдено")
        
        conn.execute("UPDATE tokens SET speed_limit_mbps = ? WHERE token = ?", (req.speed_limit_mbps, dev["token"]))
        conn.commit()
    notify_token_update()
    return {"status": "ok", "speed_limit_mbps": req.speed_limit_mbps}

# --- SYSTEM SERVICES & LOGS ---

@router.post("/api/admin/service/control")
def service_control(req: ServiceControlReq, admin: str = Depends(verify_admin)):
    allowed_services = ["hysteria-server", "nginx", "tabis-backend", "system"]
    if req.service not in allowed_services:
        raise HTTPException(status_code=400, detail="Недопустимая служба")

    allowed_actions = ["start", "stop", "restart", "reboot"]
    if req.action not in allowed_actions:
        raise HTTPException(status_code=400, detail="Недопустимое действие")

    log_audit("SERVICE_CONTROL", req.service, f"Команда: {req.action}")

    if req.service == "system" and req.action == "reboot":
        def delayed_reboot():
            time.sleep(2)
            os.system("reboot")
        import threading
        threading.Thread(target=delayed_reboot, daemon=True).start()
        return {"status": "ok", "message": "Сервер перезагружается..."}

    cmd = f"systemctl {req.action} {req.service}"
    try:
        subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return {"status": "ok", "message": f"Команда '{req.action}' для {req.service} выполнена успешно"}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка выполнения команды: {e.output.decode('utf-8')}")

@router.get("/api/admin/service/logs")
def get_service_logs(service: str = Query("hysteria"), lines: int = Query(80, ge=10, le=500), admin: str = Depends(verify_admin)):
    service_map = {
        "hysteria": "hysteria-server",
        "nginx": "nginx",
        "backend": "tabis-backend"
    }
    unit = service_map.get(service)
    if not unit:
        raise HTTPException(status_code=400, detail="Неизвестная служба")

    cmd = f"journalctl -u {unit} -n {lines} --no-pager"
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8', errors='replace')
        return PlainTextResponse(out)
    except Exception as e:
        return PlainTextResponse(f"Не удалось прочитать логи службы {unit}: {e}")

# --- WEB FILE EXPLORER ---

@router.get("/api/admin/fs/list")
def fs_list(path: str = Query("/root/tabis-backend"), admin: str = Depends(verify_admin)):
    target = Path(path).resolve()
    if not any(target == root or root in target.parents for root in ALLOWED_FS_ROOTS):
        raise HTTPException(status_code=403, detail="Доступ к этому каталогу запрещен")

    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="Каталог не найден")

    items = []
    try:
        for entry in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            items.append({
                "name": entry.name,
                "path": str(entry.resolve()),
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else 0,
                "modified": datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения каталога: {e}")

    return {
        "current": str(target),
        "parent": str(target.parent) if any(target.parent == r or r in target.parent.parents for r in ALLOWED_FS_ROOTS) else None,
        "items": items
    }

@router.get("/api/admin/fs/read")
def fs_read(path: str = Query(...), admin: str = Depends(verify_admin)):
    target = Path(path).resolve()
    if not any(target == root or root in target.parents for root in ALLOWED_FS_ROOTS):
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    if not target.is_file():
        raise HTTPException(status_code=400, detail="Указанный путь не является файлом")

    if target.stat().st_size > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой для веб-редактора (> 2MB)")

    try:
        with open(target, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return {"path": str(target), "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения файла: {e}")

@router.post("/api/admin/fs/write")
def fs_write(req: FsWriteReq, admin: str = Depends(verify_admin)):
    target = Path(req.path).resolve()
    if not any(target == root or root in target.parents for root in ALLOWED_FS_ROOTS):
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    try:
        with open(target, 'w', encoding='utf-8') as f:
            f.write(req.content)
        log_audit("FILE_SAVE", str(target), "Файл сохранен через веб-редактор")
        return {"status": "ok", "message": "Файл успешно сохранен"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка записи: {e}")

# --- VAULT & NOTES ---

@router.get("/api/admin/vault/notes")
def get_vault_notes(key: str = Query("general"), admin: str = Depends(verify_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT content, updated_at FROM vault_notes WHERE key = ?", (key,)).fetchone()
        if not row:
            return {"key": key, "content": "", "updated_at": None}
        return {"key": key, "content": row["content"], "updated_at": row["updated_at"]}

@router.post("/api/admin/vault/notes")
def save_vault_notes(req: VaultNotesReq, key: str = Query("general"), admin: str = Depends(verify_admin)):
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute("""
            INSERT INTO vault_notes (key, content, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at
        """, (key, req.content, now_str))
        conn.commit()

    log_audit("VAULT_SAVE", key, "Заметка обновлена в блокноте администратора")
    return {"status": "ok", "updated_at": now_str}

# --- AUDIT LOGS & BACKUPS ---

@router.get("/api/admin/audit-logs")
def get_audit_logs(limit: int = Query(100, ge=10, le=500), admin: str = Depends(verify_admin)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, timestamp, user_id, action, target, details, client_ip, dest_ip, dest_domain, ip
            FROM audit_logs 
            ORDER BY id DESC 
            LIMIT ?
        """, (limit,)).fetchall()
        
        result = []
        for r in rows:
            d = dict(r)
            if d.get("user_id"):
                u = conn.execute("SELECT email, nickname FROM users WHERE id = ?", (d["user_id"],)).fetchone()
                if u:
                    d["user_email"] = u["email"]
                    d["user_nickname"] = u["nickname"]
            result.append(d)
        return result

@router.get("/api/admin/backup/download")
def download_database_backup(admin: str = Depends(verify_admin)):
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="База данных не найдена")

    log_audit("BACKUP_DOWNLOAD", "tabis.db", "Скачан файл резервной копии БД")
    with open(DB_PATH, "rb") as f:
        data = f.read()

    filename = f"tabis_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/octet-stream"
    }
    return Response(content=data, media_type="application/octet-stream", headers=headers)

# --- IN-APP RELEASE MANAGEMENT ---

@router.get("/api/admin/app/release")
def get_admin_app_release(admin: str = Depends(verify_admin)):
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
        return dict(row)

@router.post("/api/admin/app/release")
def save_admin_app_release(data: Dict[str, Any], admin: str = Depends(verify_admin)):
    vc = int(data.get("version_code", 1))
    vn = str(data.get("version_name", "1.0.0")).strip()
    cl = str(data.get("changelog", "")).strip()
    du = str(data.get("download_url", "")).strip()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    if not vn or not du:
        raise HTTPException(status_code=400, detail="version_name и download_url обязательны")

    with get_db() as conn:
        conn.execute("""
            INSERT INTO app_release (id, version_code, version_name, changelog, download_url, updated_at)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                version_code = excluded.version_code,
                version_name = excluded.version_name,
                changelog = excluded.changelog,
                download_url = excluded.download_url,
                updated_at = excluded.updated_at
        """, (vc, vn, cl, du, now_str))
        conn.commit()

    log_audit("APP_RELEASE_UPDATE", vn, f"Опубликована новая сборка {vc} ({vn})")
    return {"status": "ok", "version_code": vc, "version_name": vn, "updated_at": now_str}

# --- REVIEWS MODERATION ---

@router.get("/api/admin/reviews")
def admin_get_reviews(admin: str = Depends(verify_admin)):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT r.*, u.email as user_email 
            FROM reviews r
            LEFT JOIN users u ON u.id = r.user_id
            ORDER BY r.id DESC
        """).fetchall()
        return [dict(r) for r in rows]

@router.post("/api/admin/reviews/{review_id}/approve")
def admin_approve_review(review_id: int, approve: int = Query(1), admin: str = Depends(verify_admin)):
    with get_db() as conn:
        conn.execute("UPDATE reviews SET approved = ? WHERE id = ?", (1 if approve else 0, review_id))
        conn.commit()
    log_audit("REVIEW_APPROVE", f"#{review_id}", f"Статус модерации: {'Одобрен' if approve else 'Отклонен'}")
    return {"status": "ok", "approved": approve}

@router.delete("/api/admin/reviews/{review_id}")
def admin_delete_review(review_id: int, admin: str = Depends(verify_admin)):
    with get_db() as conn:
        conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()
    log_audit("REVIEW_DELETE", f"#{review_id}", "Отзыв удален администратором")
    return {"status": "ok"}

# --- SUPPORT CHAT MANAGEMENT ---

@router.get("/api/admin/support/dialogs")
def admin_support_list_dialogs(status: Optional[str] = None, admin: str = Depends(verify_admin)):
    with get_db() as conn:
        query = """
            SELECT d.*, 
                   u.balance as user_balance, 
                   (SELECT COUNT(*) FROM user_devices ud WHERE ud.user_id = d.user_id) as user_device_count,
                   (SELECT text FROM support_messages m WHERE m.dialog_id = d.id ORDER BY m.id DESC LIMIT 1) as last_msg_text,
                   (SELECT sender_type FROM support_messages m WHERE m.dialog_id = d.id ORDER BY m.id DESC LIMIT 1) as last_msg_sender
            FROM support_dialogs d
            LEFT JOIN users u ON u.id = d.user_id
        """
        params = []
        if status and status != 'all':
            query += " WHERE d.status = ?"
            params.append(status)
        query += " ORDER BY d.last_message_at DESC"

        rows = conn.execute(query, tuple(params)).fetchall()
        unread_row = conn.execute("SELECT SUM(unread_admin) FROM support_dialogs").fetchone()
        unread_total = unread_row[0] if unread_row and unread_row[0] else 0

        return {
            "dialogs": [dict(r) for r in rows],
            "unread_total": unread_total
        }

@router.get("/api/admin/support/dialogs/{dialog_id}/messages")
def admin_support_get_dialog_messages(dialog_id: int, admin: str = Depends(verify_admin)):
    with get_db() as conn:
        dlg = conn.execute("SELECT * FROM support_dialogs WHERE id = ?", (dialog_id,)).fetchone()
        if not dlg:
            raise HTTPException(status_code=404, detail="Диалог не найден")

        conn.execute("UPDATE support_messages SET is_read = 1 WHERE dialog_id = ? AND sender_type = 'user'", (dialog_id,))
        conn.execute("UPDATE support_dialogs SET unread_admin = 0 WHERE id = ?", (dialog_id,))
        conn.commit()

        user_info = None
        if dlg["user_id"]:
            u = conn.execute("SELECT id, email, nickname, user_code, balance, created_at FROM users WHERE id = ?", (dlg["user_id"],)).fetchone()
            if u:
                devices = conn.execute("SELECT id, device_name, tariff_plan, is_active, subscription_expires_at FROM user_devices WHERE user_id = ?", (dlg["user_id"],)).fetchall()
                user_info = dict(u)
                user_info["devices"] = [dict(dev) for dev in devices]

        messages = conn.execute("""
            SELECT id, sender_type, sender_name, text, created_at, is_read 
            FROM support_messages 
            WHERE dialog_id = ? 
            ORDER BY id ASC
        """, (dialog_id,)).fetchall()

        return {
            "dialog": dict(dlg),
            "user_info": user_info,
            "messages": [dict(m) for m in messages]
        }

@router.post("/api/admin/support/dialogs/{dialog_id}/reply")
def admin_support_reply(dialog_id: int, req: SupportAdminReplyReq, admin: str = Depends(verify_admin)):
    clean_text = req.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Текст ответа не может быть пустым")

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        dlg = conn.execute("SELECT * FROM support_dialogs WHERE id = ?", (dialog_id,)).fetchone()
        if not dlg:
            raise HTTPException(status_code=404, detail="Диалог не найден")

        conn.execute("""
            INSERT INTO support_messages (dialog_id, sender_type, sender_name, text, created_at, is_read)
            VALUES (?, 'admin', 'Оператор Tabis', ?, ?, 0)
        """, (dialog_id, clean_text, now_str))

        conn.execute("""
            UPDATE support_dialogs 
            SET unread_user = unread_user + 1, last_message_at = ?, status = 'open' 
            WHERE id = ?
        """, (now_str, dialog_id))
        conn.commit()

    notify_token_update("support_reply")
    return {"ok": True, "created_at": now_str}

@router.post("/api/admin/support/dialogs/{dialog_id}/status")
def admin_support_change_status(dialog_id: int, req: SupportStatusReq, admin: str = Depends(verify_admin)):
    if req.status not in ('open', 'closed'):
        raise HTTPException(status_code=400, detail="Неверный статус (только open или closed)")
    with get_db() as conn:
        conn.execute("UPDATE support_dialogs SET status = ? WHERE id = ?", (req.status, dialog_id))
        conn.commit()
    notify_token_update("support_status")
    return {"ok": True, "status": req.status}

@router.delete("/api/admin/support/dialogs/{dialog_id}")
def admin_support_delete_dialog(dialog_id: int, admin: str = Depends(verify_admin)):
    with get_db() as conn:
        conn.execute("DELETE FROM support_messages WHERE dialog_id = ?", (dialog_id,))
        conn.execute("DELETE FROM support_dialogs WHERE id = ?", (dialog_id,))
        conn.commit()
    notify_token_update("support_delete")
    return {"ok": True}

# --- TRAFFIC AUDIT (180 DAYS) ---

@router.get("/api/admin/traffic/logs")
def admin_get_traffic_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    event_type: Optional[str] = None,
    period: Optional[str] = "all",
    token: Optional[str] = None,
    user_id: Optional[int] = None,
    admin: str = Depends(verify_admin)
):
    offset = (page - 1) * limit
    where_clauses = ["1=1"]
    params = []

    if search:
        s = f"%{search.strip()}%"
        where_clauses.append("(t.target_domain LIKE ? OR t.target_ip LIKE ? OR t.client_ip LIKE ? OR t.token LIKE ? OR t.device_name LIKE ? OR u.email LIKE ?)")
        params.extend([s, s, s, s, s, s])

    if event_type and event_type != "all":
        where_clauses.append("t.event_type = ?")
        params.append(event_type)

    if token:
        where_clauses.append("t.token = ?")
        params.append(token.strip().upper())

    if user_id:
        where_clauses.append("t.user_id = ?")
        params.append(user_id)

    now = datetime.utcnow()
    if period == "today":
        today_start = now.strftime("%Y-%m-%d 00:00:00")
        where_clauses.append("t.created_at >= ?")
        params.append(today_start)
    elif period == "7d":
        since = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        where_clauses.append("t.created_at >= ?")
        params.append(since)
    elif period == "30d":
        since = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        where_clauses.append("t.created_at >= ?")
        params.append(since)
    elif period == "180d":
        since = (now - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
        where_clauses.append("t.created_at >= ?")
        params.append(since)

    where_sql = " AND ".join(where_clauses)

    with get_db() as conn:
        count_query = f"""
            SELECT COUNT(*) 
            FROM traffic_audit_logs t
            LEFT JOIN users u ON u.id = t.user_id
            WHERE {where_sql}
        """
        total = conn.execute(count_query, tuple(params)).fetchone()[0]

        data_query = f"""
            SELECT t.id, t.created_at, t.user_id, t.token, t.device_name,
                   t.client_ip, t.client_port, t.event_type, t.target_domain,
                   t.target_ip, t.target_port, t.protocol, t.details,
                   u.email as user_email, u.nickname as user_nickname
            FROM traffic_audit_logs t
            LEFT JOIN users u ON u.id = t.user_id
            WHERE {where_sql}
            ORDER BY t.id DESC
            LIMIT ? OFFSET ?
        """
        data_params = list(params) + [limit, offset]
        rows = conn.execute(data_query, tuple(data_params)).fetchall()

    pages = max(1, (total + limit - 1) // limit)
    return {
        "logs": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }

@router.get("/api/admin/traffic/stats")
def admin_get_traffic_stats(admin: str = Depends(verify_admin)):
    with get_db() as conn:
        total_records = conn.execute("SELECT COUNT(*) FROM traffic_audit_logs").fetchone()[0]
        total_connects = conn.execute("SELECT COUNT(*) FROM traffic_audit_logs WHERE event_type = 'CONNECT'").fetchone()[0]
        total_disconnects = conn.execute("SELECT COUNT(*) FROM traffic_audit_logs WHERE event_type = 'DISCONNECT'").fetchone()[0]
        total_visits = conn.execute("SELECT COUNT(*) FROM traffic_audit_logs WHERE event_type = 'TRAFFIC_VISIT'").fetchone()[0]
        unique_domains = conn.execute("SELECT COUNT(DISTINCT target_domain) FROM traffic_audit_logs WHERE target_domain != ''").fetchone()[0]

        top_rows = conn.execute("""
            SELECT target_domain, COUNT(*) as hit_count
            FROM traffic_audit_logs
            WHERE target_domain != ''
            GROUP BY target_domain
            ORDER BY hit_count DESC
            LIMIT 10
        """, ()).fetchall()

    return {
        "total_records": total_records,
        "total_connects": total_connects,
        "total_disconnects": total_disconnects,
        "total_visits": total_visits,
        "unique_domains": unique_domains,
        "retention_days": 180,
        "top_domains": [dict(r) for r in top_rows]
    }

@router.get("/api/admin/traffic/export")
def admin_export_traffic_csv(
    search: Optional[str] = None,
    event_type: Optional[str] = None,
    period: Optional[str] = "all",
    token: Optional[str] = None,
    user_id: Optional[int] = None,
    admin: str = Depends(verify_admin)
):
    where_clauses = ["1=1"]
    params = []

    if search:
        s = f"%{search.strip()}%"
        where_clauses.append("(t.target_domain LIKE ? OR t.target_ip LIKE ? OR t.client_ip LIKE ? OR t.token LIKE ? OR t.device_name LIKE ? OR u.email LIKE ?)")
        params.extend([s, s, s, s, s, s])

    if event_type and event_type != "all":
        where_clauses.append("t.event_type = ?")
        params.append(event_type)

    if token:
        where_clauses.append("t.token = ?")
        params.append(token.strip().upper())

    if user_id:
        where_clauses.append("t.user_id = ?")
        params.append(user_id)

    now = datetime.utcnow()
    if period == "today":
        today_start = now.strftime("%Y-%m-%d 00:00:00")
        where_clauses.append("t.created_at >= ?")
        params.append(today_start)
    elif period == "7d":
        since = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        where_clauses.append("t.created_at >= ?")
        params.append(since)
    elif period == "30d":
        since = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        where_clauses.append("t.created_at >= ?")
        params.append(since)
    elif period == "180d":
        since = (now - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
        where_clauses.append("t.created_at >= ?")
        params.append(since)

    where_sql = " AND ".join(where_clauses)

    with get_db() as conn:
        data_query = f"""
            SELECT t.id, t.created_at, t.user_id, t.token, t.device_name,
                   t.client_ip, t.client_port, t.event_type, t.target_domain,
                   t.target_ip, t.target_port, t.protocol, t.details,
                   u.email as user_email
            FROM traffic_audit_logs t
            LEFT JOIN users u ON u.id = t.user_id
            WHERE {where_sql}
            ORDER BY t.id DESC
            LIMIT 20000
        """
        rows = conn.execute(data_query, tuple(params)).fetchall()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "ID", "Дата/Время (UTC)", "Пользователь ID", "Email", "Код устройства", 
        "Имя устройства", "IP клиента", "Порт клиента", "Событие", 
        "Целевой домен", "Целевой IP", "Целевой порт", "Протокол", "Детали"
    ])
    for r in rows:
        writer.writerow([
            r["id"], r["created_at"], r["user_id"] or "", r["user_email"] or "",
            r["token"], r["device_name"] or "", r["client_ip"] or "", r["client_port"] or "",
            r["event_type"], r["target_domain"] or "", r["target_ip"] or "",
            r["target_port"] or "", r["protocol"] or "", r["details"] or ""
        ])

    csv_data = output.getvalue().encode('utf-8')
    filename = f"tabis_traffic_audit_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "text/csv; charset=utf-8"
    }
    return Response(content=csv_data, media_type="text/csv; charset=utf-8", headers=headers)
