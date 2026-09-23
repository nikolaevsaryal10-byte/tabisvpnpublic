import time
import socket
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, status
from config import ADMIN_SESSIONS
from database import get_db
from services.billing_service import check_user_daily_billing

def verify_admin(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Требуется авторизация администратора")
    token = authorization.replace("Bearer ", "").strip()
    session = ADMIN_SESSIONS.get(token)
    if not session or session["expires"] < time.time():
        raise HTTPException(status_code=401, detail="Сессия истекла или недействительна")
    session["expires"] = time.time() + 3600  # 60 mins activity extension
    return session["username"]

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Требуется авторизация пользователя")
    token = authorization.replace("Bearer ", "").strip()
    with get_db() as conn:
        sess = conn.execute("SELECT user_id, expires_at FROM user_sessions WHERE token = ?", (token,)).fetchone()
        if not sess or sess["expires_at"] < time.time():
            raise HTTPException(status_code=401, detail="Сессия истекла или недействительна. Войдите снова.")
        user = conn.execute("SELECT * FROM users WHERE id = ?", (sess["user_id"],)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Пользователь не найден")
        
        # Check daily billing on active access
        check_user_daily_billing(sess["user_id"], conn)
        user_updated = conn.execute("SELECT * FROM users WHERE id = ?", (sess["user_id"],)).fetchone()
        return dict(user_updated)

def get_optional_current_user(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    if not token or token == "null" or token == "undefined":
        return None
    try:
        with get_db() as conn:
            sess = conn.execute("SELECT user_id, expires_at FROM user_sessions WHERE token = ?", (token,)).fetchone()
            if not sess or sess["expires_at"] < time.time():
                return None
            user = conn.execute("SELECT * FROM users WHERE id = ?", (sess["user_id"],)).fetchone()
            return dict(user) if user else None
    except Exception:
        return None

def resolve_ip_domain_cached(ip_str: str) -> str:
    """Safely resolves an IP address to reverse DNS hostname with 1.5s timeout."""
    if not ip_str or ip_str in ("127.0.0.1", "::1", "localhost"):
        return ""
    try:
        socket.setdefaulttimeout(1.5)
        host, _, _ = socket.gethostbyaddr(ip_str)
        return host
    except Exception:
        return ""

def log_audit(action: str, target: str = '', details: str = '', ip: str = '',
              user_id: Optional[int] = None, dest_ip: str = '', dest_domain: str = '', client_ip: str = ''):
    try:
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        actual_client_ip = client_ip or ip or ''
        
        actual_domain = dest_domain
        if dest_ip and not actual_domain:
            actual_domain = resolve_ip_domain_cached(dest_ip)
            
        with get_db() as conn:
            conn.execute("""
                INSERT INTO audit_logs (timestamp, user_id, action, target, details, client_ip, dest_ip, dest_domain, ip)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (now_str, user_id, action, target, details, actual_client_ip, dest_ip, actual_domain, actual_client_ip))
            conn.commit()
    except Exception as e:
        print(f'Failed to write audit log: {e}')

def check_login_rate_limit(ip: str):
    now = time.time()
    with get_db() as conn:
        row = conn.execute("SELECT attempts, locked_until FROM login_attempts WHERE ip = ?", (ip,)).fetchone()
        if row:
            if row["locked_until"] > now:
                remaining_sec = int(row["locked_until"] - now)
                hours = remaining_sec // 3600
                mins = (remaining_sec % 3600) // 60
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Превышен лимит попыток (5). Доступ заблокирован на 24 часа. Осталось: {hours}ч {mins}м."
                )
            elif row["locked_until"] > 0 and row["locked_until"] <= now:
                conn.execute("DELETE FROM login_attempts WHERE ip = ?", (ip,))
                conn.commit()

def record_login_failure(ip: str):
    now = time.time()
    with get_db() as conn:
        row = conn.execute("SELECT attempts FROM login_attempts WHERE ip = ?", (ip,)).fetchone()
        if not row:
            conn.execute("INSERT INTO login_attempts (ip, attempts, locked_until, last_attempt) VALUES (?, 1, 0, ?)", (ip, now))
        else:
            new_attempts = row["attempts"] + 1
            if new_attempts >= 5:
                locked_until = now + 86400  # 24 hours lock
                conn.execute("UPDATE login_attempts SET attempts = ?, locked_until = ?, last_attempt = ? WHERE ip = ?", (new_attempts, locked_until, now, ip))
            else:
                conn.execute("UPDATE login_attempts SET attempts = ?, last_attempt = ? WHERE ip = ?", (new_attempts, now, ip))
        conn.commit()

def record_login_success(ip: str):
    with get_db() as conn:
        conn.execute("DELETE FROM login_attempts WHERE ip = ?", (ip,))
        conn.commit()
