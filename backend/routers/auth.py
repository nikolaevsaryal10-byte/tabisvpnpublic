import re
import time
import secrets
from datetime import datetime, date
from fastapi import APIRouter, HTTPException, Request
from database import get_db
from models import (
    EmailSendOtpReq, EmailVerifyOtpReq, RegisterSendOtpReq, RegisterVerifyOtpReq,
    RegisterCompleteReq, UserLoginReq, ResetPasswordSendOtpReq, ResetPasswordCompleteReq
)
from core.security import hash_user_password, verify_and_migrate_password, generate_user_code, generate_device_token, generate_referral_code
from core.dependencies import check_login_rate_limit, record_login_failure, record_login_success
from services.email_service import send_email_otp

router = APIRouter()

@router.post("/api/v1/auth/send-otp")
def auth_send_otp(req: EmailSendOtpReq):
    email = req.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Укажите корректный email адрес")
    
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = time.time() + 600  # 10 minutes
    
    with get_db() as conn:
        conn.execute("INSERT INTO email_otps (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)",
                     (email, code, expires_at, time.time()))
        conn.commit()
    
    delivered = send_email_otp(email, code)
    if not delivered:
        raise HTTPException(
            status_code=500,
            detail="Не удалось отправить письмо с кодом на указанный email. Проверьте правильность адреса или обратитесь в поддержку."
        )
    
    return {
        "status": "ok",
        "message": f"Код подтверждения отправлен на {email}"
    }

@router.post("/api/v1/auth/register/send-otp")
def auth_register_send_otp(req: RegisterSendOtpReq):
    if not req.agree_terms or not req.agree_privacy:
        raise HTTPException(status_code=400, detail="Необходимо согласиться с пользовательским соглашением и политикой конфиденциальности")
    
    email = req.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Укажите корректный email адрес")
    
    with get_db() as conn:
        existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing_user:
            raise HTTPException(status_code=400, detail="Аккаунт с таким email уже зарегистрирован. Пожалуйста, выполните вход.")
        
        code = f"{secrets.randbelow(900000) + 100000}"
        expires_at = time.time() + 600
        conn.execute("INSERT INTO email_otps (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)",
                     (email, code, expires_at, time.time()))
        conn.commit()
    
    delivered = send_email_otp(email, code, subject=f"Регистрация Tabis VPN: код {code}")
    if not delivered:
        raise HTTPException(status_code=500, detail="Не удалось доставить проверочный код на email. Проверьте правильность адреса.")
    
    return {"status": "ok", "message": f"Код подтверждения отправлен на {email}"}

@router.post("/api/v1/auth/register/verify-otp")
def auth_register_verify_otp(req: RegisterVerifyOtpReq):
    email = req.email.strip().lower()
    code = req.code.strip()
    
    with get_db() as conn:
        otp_row = conn.execute("""
            SELECT * FROM email_otps 
            WHERE email = ? AND code = ? AND expires_at >= ?
            ORDER BY created_at DESC LIMIT 1
        """, (email, code, time.time())).fetchone()
        
        if not otp_row:
            raise HTTPException(status_code=400, detail="Неверный или истекший проверочный код")
        
        conn.execute("DELETE FROM email_otps WHERE email = ?", (email,))
        reg_token = f"reg_{secrets.token_hex(24)}"
        expires_at = time.time() + 1800  # 30 mins
        conn.execute("INSERT INTO registration_tokens (token, email, expires_at, created_at) VALUES (?, ?, ?, ?)",
                     (reg_token, email, expires_at, time.time()))
        conn.commit()
        
    return {"status": "ok", "reg_token": reg_token, "email": email}

@router.post("/api/v1/auth/register/complete")
def auth_register_complete(req: RegisterCompleteReq):
    email = req.email.strip().lower()
    reg_token = req.reg_token.strip()
    nickname = req.nickname.strip()
    password = req.password.strip()
    confirm_password = req.confirm_password.strip()
    clean_ref = (req.ref_code or "").strip().upper()
    
    if not nickname or len(nickname) < 2 or len(nickname) > 30:
        raise HTTPException(status_code=400, detail="Никнейм должен содержать от 2 до 30 символов")
    
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 6 символов")
    
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")
    
    with get_db() as conn:
        if not reg_token or not reg_token.startswith("reg_"):
            raise HTTPException(status_code=400, detail="Сессия регистрации истекла или недействительна. Начните сначала.")

        tok_row = conn.execute("""
            SELECT * FROM registration_tokens 
            WHERE token = ? AND email = ? AND expires_at >= ?
        """, (reg_token, email, time.time())).fetchone()
        
        if not tok_row:
            raise HTTPException(status_code=400, detail="Сессия регистрации истекла или недействительна. Начните сначала.")
        
        conn.execute("DELETE FROM registration_tokens WHERE email = ?", (email,))
        
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Пользователь с таким email уже зарегистрирован")
        
        user_code = generate_user_code()
        referral_code = generate_referral_code()
        pw_hash = hash_user_password(password)
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        today_str = date.today().isoformat()
        
        referred_by = None
        starting_balance = 0
        if clean_ref:
            ref_owner = conn.execute("SELECT id FROM users WHERE referral_code = ?", (clean_ref,)).fetchone()
            if ref_owner:
                referred_by = clean_ref
                starting_balance = 6
        
        cur = conn.execute("""
            INSERT INTO users (email, password_hash, nickname, user_code, balance, device_limit, referral_code, referred_by, created_at, last_billing_date)
            VALUES (?, ?, ?, ?, ?, 5, ?, ?, ?, ?)
        """, (email, pw_hash, nickname, user_code, starting_balance, referral_code, referred_by, now_str, today_str))
        user_id = cur.lastrowid
        
        primary_token = generate_device_token()
        conn.execute("""
            INSERT INTO tokens (token, label, speed_limit_mbps, last_reset_day, created_at)
            VALUES (?, ?, 0, ?, ?)
        """, (primary_token, f"{nickname} (Основное устройство)", today_str, now_str))
        
        conn.execute("""
            INSERT INTO user_devices (user_id, device_name, token, is_active, created_at)
            VALUES (?, 'Основное устройство', ?, 1, ?)
        """, (user_id, primary_token, now_str))
        
        if referred_by:
            ref_owner = conn.execute("SELECT id, balance FROM users WHERE referral_code = ?", (referred_by,)).fetchone()
            if ref_owner:
                ref_id = ref_owner["id"]
                conn.execute("INSERT INTO referral_logs (referrer_id, referred_user_id, bonus_rub, created_at) VALUES (?, ?, 0, ?)",
                             (ref_id, user_id, now_str))
                total_friends = conn.execute("SELECT COUNT(*) FROM referral_logs WHERE referrer_id = ?", (ref_id,)).fetchone()[0]
                if total_friends > 0 and total_friends % 3 == 0:
                    conn.execute("UPDATE users SET balance = balance + 20 WHERE id = ?", (ref_id,))
                    conn.execute("UPDATE referral_logs SET bonus_rub = 20 WHERE referrer_id = ? AND referred_user_id = ?",
                                 (ref_id, user_id))
        
        platform_str = (req.platform or "web").strip().lower()
        device_id = (req.device_id or "").strip()
        session_token = f"sess_{secrets.token_hex(24)}"
        expires_at = time.time() + (86400 * 30)
        conn.execute("INSERT INTO user_sessions (token, user_id, platform, device_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (session_token, user_id, platform_str, device_id, now_str, expires_at))
        conn.commit()
        
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        
    return {
        "status": "ok",
        "token": session_token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "nickname": user["nickname"],
            "user_code": user["user_code"],
            "balance": user["balance"],
            "referral_code": user["referral_code"]
        }
    }

@router.post("/api/v1/auth/login")
def auth_user_login(req: UserLoginReq, request: Request):
    email = req.email.strip().lower()
    password = req.password.strip()
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "").split(",")[0].strip()
    check_login_rate_limit(client_ip)
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            record_login_failure(client_ip)
            raise HTTPException(status_code=400, detail="Неверный email или пароль")
        
        if not user["password_hash"]:
            record_login_failure(client_ip)
            raise HTTPException(status_code=400, detail="Для данного аккаунта не установлен пароль. Воспользуйтесь входом по одноразовому коду.")
        
        is_valid, new_hash = verify_and_migrate_password(user["password_hash"], password)
        if not is_valid:
            record_login_failure(client_ip)
            raise HTTPException(status_code=400, detail="Неверный email или пароль")
        
        # Reset login attempts on successful credentials check
        record_login_success(client_ip)

        # Transparently upgrade legacy SHA-256 hash to Argon2id
        if new_hash:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
            conn.commit()
        
        # Determine platform: Android or Web
        user_agent = request.headers.get("User-Agent", "")
        client_platform = request.headers.get("X-Client-Platform", "")
        header_device_id = request.headers.get("X-Device-Id", "")
        device_id = (req.device_id or header_device_id or "").strip()
        is_android = (
            bool(device_id) or
            (req.platform and req.platform.lower() == "android") or
            (client_platform.lower() == "android") or
            ("TabisVPN-Android" in user_agent)
        )
        platform_str = "android" if is_android else "web"

        # If logging in from Android, enforce single active Android session per user
        if is_android:
            if device_id:
                conn.execute("DELETE FROM user_sessions WHERE user_id = ? AND platform = 'android' AND (device_id != ? OR device_id = '')", (user["id"], device_id))
            else:
                conn.execute("DELETE FROM user_sessions WHERE user_id = ? AND platform = 'android'", (user["id"],))

        session_token = f"sess_{secrets.token_hex(24)}"
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        expires_at = time.time() + (86400 * 30)
        conn.execute("INSERT INTO user_sessions (token, user_id, platform, device_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (session_token, user["id"], platform_str, device_id, now_str, expires_at))
        conn.commit()
        
    return {
        "status": "ok",
        "token": session_token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "nickname": user["nickname"],
            "user_code": user["user_code"],
            "balance": user["balance"],
            "referral_code": user["referral_code"]
        }
    }

@router.post("/api/v1/auth/reset-password/send-otp")
def auth_reset_password_send_otp(req: ResetPasswordSendOtpReq):
    email = req.email.strip().lower()
    with get_db() as conn:
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Аккаунт с таким email не найден")
        
        code = f"{secrets.randbelow(900000) + 100000}"
        expires_at = time.time() + 600
        conn.execute("INSERT INTO email_otps (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)",
                     (email, code, expires_at, time.time()))
        conn.commit()
    
    delivered = send_email_otp(email, code, subject=f"Восстановление пароля Tabis VPN: {code}")
    if not delivered:
        raise HTTPException(status_code=500, detail="Не удалось отправить письмо на email")
    return {"status": "ok", "message": f"Код сброса пароля отправлен на {email}"}

@router.post("/api/v1/auth/reset-password/complete")
def auth_reset_password_complete(req: ResetPasswordCompleteReq):
    email = req.email.strip().lower()
    code = req.code.strip()
    new_pw = req.new_password.strip()
    
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 6 символов")
    
    with get_db() as conn:
        otp = conn.execute("""
            SELECT rowid FROM email_otps 
            WHERE email = ? AND code = ? AND expires_at >= ?
            ORDER BY rowid DESC LIMIT 1
        """, (email, code, time.time())).fetchone()
        if not otp:
            raise HTTPException(status_code=400, detail="Неверный или просроченный проверочный код")
        
        conn.execute("DELETE FROM email_otps WHERE email = ?", (email,))
        pw_hash = hash_user_password(new_pw)
        conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pw_hash, email))
        conn.commit()
    return {"status": "ok", "message": "Пароль успешно изменен! Теперь вы можете войти."}

@router.post("/api/v1/auth/verify-otp")
def auth_verify_otp(req: EmailVerifyOtpReq, request: Request):
    email = req.email.strip().lower()
    code = req.code.strip()
    
    with get_db() as conn:
        otp_row = conn.execute("""
            SELECT * FROM email_otps 
            WHERE email = ? AND code = ? AND expires_at >= ?
            ORDER BY created_at DESC LIMIT 1
        """, (email, code, time.time())).fetchone()
        
        if not otp_row:
            raise HTTPException(status_code=400, detail="Неверный или истекший код подтверждения")
        
        conn.execute("DELETE FROM email_otps WHERE email = ?", (email,))
        
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        is_new = False
        if not user:
            is_new = True
            user_code = generate_user_code()
            referral_code = generate_referral_code()
            nickname = email.split("@")[0]
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            today_str = date.today().isoformat()
            
            clean_ref = (req.ref_code or "").strip().upper()
            referred_by = None
            starting_balance = 0
            if clean_ref:
                ref_user = conn.execute("SELECT id FROM users WHERE referral_code = ?", (clean_ref,)).fetchone()
                if ref_user:
                    referred_by = clean_ref
                    starting_balance = 6
            
            cur = conn.execute("""
                INSERT INTO users (email, nickname, user_code, balance, device_limit, referral_code, referred_by, created_at, last_billing_date)
                VALUES (?, ?, ?, ?, 5, ?, ?, ?, ?)
            """, (email, nickname, user_code, starting_balance, referral_code, referred_by, now_str, today_str))
            user_id = cur.lastrowid
            
            primary_token = generate_device_token()
            conn.execute("""
                INSERT INTO tokens (token, label, speed_limit_mbps, last_reset_day, created_at)
                VALUES (?, ?, 0, ?, ?)
            """, (primary_token, f"{nickname} (Основное устройство)", today_str, now_str))
            
            conn.execute("""
                INSERT INTO user_devices (user_id, device_name, token, is_active, created_at)
                VALUES (?, 'Основное устройство', ?, 1, ?)
            """, (user_id, primary_token, now_str))
            
            if referred_by:
                ref_owner = conn.execute("SELECT id, balance FROM users WHERE referral_code = ?", (referred_by,)).fetchone()
                if ref_owner:
                    ref_id = ref_owner["id"]
                    conn.execute("INSERT INTO referral_logs (referrer_id, referred_user_id, bonus_rub, created_at) VALUES (?, ?, 0, ?)",
                                 (ref_id, user_id, now_str))
                    total_friends = conn.execute("SELECT COUNT(*) FROM referral_logs WHERE referrer_id = ?", (ref_id,)).fetchone()[0]
                    if total_friends > 0 and total_friends % 3 == 0:
                        conn.execute("UPDATE users SET balance = balance + 20 WHERE id = ?", (ref_id,))
                        conn.execute("UPDATE referral_logs SET bonus_rub = 20 WHERE referrer_id = ? AND referred_user_id = ?",
                                     (ref_id, user_id))
            
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        
        # Determine platform: Android or Web
        user_agent = request.headers.get("User-Agent", "")
        client_platform = request.headers.get("X-Client-Platform", "")
        header_device_id = request.headers.get("X-Device-Id", "")
        device_id = (req.device_id or header_device_id or "").strip()
        is_android = (
            bool(device_id) or
            (req.platform and req.platform.lower() == "android") or
            (client_platform.lower() == "android") or
            ("TabisVPN-Android" in user_agent)
        )
        platform_str = "android" if is_android else "web"

        if is_android:
            if device_id:
                conn.execute("DELETE FROM user_sessions WHERE user_id = ? AND platform = 'android' AND (device_id != ? OR device_id = '')", (user["id"], device_id))
            else:
                conn.execute("DELETE FROM user_sessions WHERE user_id = ? AND platform = 'android'", (user["id"],))

        session_token = f"sess_{secrets.token_hex(24)}"
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        expires_at = time.time() + (86400 * 30)
        conn.execute("INSERT INTO user_sessions (token, user_id, platform, device_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (session_token, user["id"], platform_str, device_id, now_str, expires_at))
        conn.commit()

        return {
            "status": "ok",
            "token": session_token,
            "is_new_user": is_new,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "nickname": user["nickname"],
                "user_code": user["user_code"],
                "balance": user["balance"],
                "referral_code": user["referral_code"]
            }
        }
