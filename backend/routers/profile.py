import time
import base64
import uuid
import json
import secrets
import ipaddress
import urllib.request
import urllib.parse
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from database import get_db, kick_hy2_user
from config import (
    YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, YOOKASSA_API_URL, notify_token_update,
    HYSTERIA_SERVER, HYSTERIA_PORT
)
from models import (
    ProfileTopUpReq, ProfileNicknameReq, TariffChangeReq, ProfileDeviceAddReq,
    ProfileDeviceTariffReq, DeleteAccountCompleteReq, ProfileDeviceLimitReq,
    SupportClientMsgReq
)
from core.dependencies import get_current_user, get_optional_current_user
from core.security import generate_device_token, generate_referral_code, load_server_keys
from services.billing_service import check_user_subscription, check_device_subscription, apply_successful_payment
from services.email_service import send_email_otp

router = APIRouter()

YOOKASSA_WEBHOOK_SUBNETS = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.156.11/32"),
    ipaddress.ip_network("77.75.156.35/32"),
]

def extract_webhook_client_ip(request: Request) -> str:
    peer_ip = request.client.host if request.client else "127.0.0.1"
    if peer_ip in ("127.0.0.1", "::1"):
        real_ip = request.headers.get("X-Real-IP")
        if real_ip and real_ip.strip():
            return real_ip.strip()
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded and forwarded.strip():
            return forwarded.split(",")[0].strip()
    return peer_ip

def is_yookassa_ip(client_ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(client_ip_str)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return any(ip in subnet for subnet in YOOKASSA_WEBHOOK_SUBNETS)
    except ValueError:
        return False

def get_real_servers_list() -> List[Dict[str, Any]]:
    """Parses servers.txt and returns real active servers for the profile dashboard."""
    raw_keys = load_server_keys()
    servers = []
    
    for idx, key in enumerate(raw_keys):
        key = key.strip()
        if not key:
            continue
        server_name = f"Узел #{idx + 1}"
        protocol = "Hysteria 2" if key.startswith("hy2://") else "VLESS Reality"
        host = HYSTERIA_SERVER
        port = HYSTERIA_PORT
        flag = "🇸🇪"
        location = "Швеция (Стокгольм)"
        
        if "#" in key:
            tag = urllib.parse.unquote(key.split("#")[-1])
            server_name = tag
            if "Sweden" in tag or "🇸🇪" in tag:
                flag = "🇸🇪"
                location = "Швеция (Стокгольм)"
            elif "Finland" in tag or "🇫🇮" in tag:
                flag = "🇫🇮"
                location = "Финляндия (Хельсинки)"
            elif "Germany" in tag or "🇩🇪" in tag:
                flag = "🇩🇪"
                location = "Германия (Франкфурт)"
        
        if "@" in key:
            after_at = key.split("@")[1].split("?")[0]
            if ":" in after_at:
                host, port_str = after_at.split(":")
                try:
                    port = int(port_str)
                except ValueError:
                    pass

        servers.append({
            "id": f"srv-{idx + 1}",
            "name": server_name,
            "protocol": protocol,
            "host": host,
            "port": port,
            "flag": flag,
            "location": location,
            "ping_ms": 1.8 if idx == 0 else 22.0,
            "status": "ONLINE"
        })
    
    if not servers:
        servers.append({
            "id": "srv-1",
            "name": "🇸🇪 Sweden - Hysteria2 Fast",
            "protocol": "Hysteria 2",
            "host": HYSTERIA_SERVER,
            "port": HYSTERIA_PORT,
            "flag": "🇸🇪",
            "location": "Швеция (Стокгольм)",
            "ping_ms": 1.8,
            "status": "ONLINE"
        })
    return servers

@router.get("/api/v1/profile/me")
def get_profile_me(user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["id"]
    with get_db() as conn:
        check_user_subscription(user_id, conn)
        
        u = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        
        devices_rows = conn.execute("""
            SELECT id, device_name, token, is_active, tariff_plan, subscription_expires_at, month_traffic_bytes, created_at 
            FROM user_devices WHERE user_id = ? ORDER BY id ASC
        """, (user_id,)).fetchall()
        
        today = date.today()
        devices = []
        total_monthly_cost = 0
        active_count = 0
        
        for r in devices_rows:
            d = dict(r)
            plan = d.get("tariff_plan") or "base"
            cost = 240 if plan == "premium" else 60
            expires_at = d.get("subscription_expires_at") or ""
            days_remaining = 0
            if expires_at:
                try:
                    exp_d = date.fromisoformat(expires_at[:10])
                    days_remaining = max(0, (exp_d - today).days)
                except Exception:
                    days_remaining = 0

            # Real live traffic from tokens table
            tok_row = conn.execute("SELECT traffic_up, traffic_down, last_ip, last_seen_at FROM tokens WHERE UPPER(token) = ?", (d["token"].upper(),)).fetchone()
            traffic_used = 0
            is_online = False
            last_ip = ""
            if tok_row:
                traffic_used = (tok_row["traffic_up"] or 0) + (tok_row["traffic_down"] or 0)
                last_ip = tok_row["last_ip"] or ""
                seen = tok_row["last_seen_at"] or ""
                if seen:
                    try:
                        seen_dt = datetime.fromisoformat(seen)
                        if (datetime.utcnow() - seen_dt).total_seconds() < 300:
                            is_online = True
                    except Exception:
                        pass

            dev_month_bytes = d.get("month_traffic_bytes") or 0
            if dev_month_bytes > traffic_used:
                traffic_used = dev_month_bytes
            elif traffic_used > dev_month_bytes:
                conn.execute("UPDATE user_devices SET month_traffic_bytes = ? WHERE id = ?", (traffic_used, d["id"]))
                conn.commit()

            limit_bytes = 100 * 1024 * 1024 * 1024 if plan == "base" else 0
            traffic_percent = 0.0
            if limit_bytes > 0:
                traffic_percent = round((traffic_used / limit_bytes) * 100.0, 1)

            traffic_gb = round(traffic_used / (1024 * 1024 * 1024), 2)
            if traffic_used > 0 and traffic_gb == 0.0:
                traffic_gb = 0.01

            is_act = bool(d["is_active"] and days_remaining > 0)
            if is_act:
                active_count += 1
                total_monthly_cost += cost

            status_text = "Активна" if is_act else "Приостановлена (пополните баланс)"
            if is_act and plan == "base" and traffic_percent >= 100:
                status_text = "Лимит 100 ГБ исчерпан"

            d["days_remaining"] = days_remaining
            d["daily_cost_rub"] = 8 if plan == "premium" else 2
            d["monthly_cost_rub"] = cost
            d["monthly_cost"] = cost
            d["is_online"] = is_online
            d["last_ip"] = last_ip
            d["traffic_used_bytes"] = traffic_used
            d["traffic_limit_bytes"] = limit_bytes
            d["traffic_gb"] = traffic_gb
            d["traffic_limit_gb"] = 0 if plan == "premium" else 100
            d["traffic_percent"] = min(100.0, traffic_percent)
            d["status_text"] = status_text
            d["tariff_name"] = "Премиум" if plan == "premium" else "Базовый"
            d["speed_limit"] = "Без ограничений" if plan == "premium" else "до 10 Мбит/с"
            d["is_active"] = 1 if is_act else 0
            devices.append(d)

        real_servers = get_real_servers_list()

        return {
            "status": "ok",
            "user": {
                "id": u["id"],
                "email": u["email"],
                "nickname": u["nickname"],
                "user_code": u["user_code"],
                "balance": u["balance"],
                "created_at": u["created_at"]
            },
            "billing": {
                "total_devices": len(devices),
                "active_devices": active_count,
                "max_devices": 5,
                "total_monthly_cost_rub": total_monthly_cost,
                "is_active": active_count > 0
            },
            "devices": devices,
            "servers": real_servers
        }

@router.post("/api/v1/profile/top-up")
def profile_top_up(req: ProfileTopUpReq, user: Dict[str, Any] = Depends(get_current_user)):
    if req.amount < 1 or req.amount > 30000:
        raise HTTPException(status_code=400, detail="Сумма пополнения должна быть от 1 до 30 000 ₽")

    amount = req.amount
    idempotence_key = str(uuid.uuid4())
    auth_header = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()

    receipt_amount_val = f"{amount:.2f}" if isinstance(amount, float) else f"{amount}.00"
    payload = {
        "amount": {
            "value": receipt_amount_val,
            "currency": "RUB"
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://tabisvpn.site/profile?payment=check&amount={amount}"
        },
        "description": f"Пополнение баланса Tabis VPN (+{amount} ₽)",
        "receipt": {
            "customer": {
                "email": user["email"]
            },
            "items": [
                {
                    "description": f"Пополнение баланса Tabis VPN (аккаунт {user['email']})",
                    "quantity": "1.00",
                    "amount": {
                        "value": receipt_amount_val,
                        "currency": "RUB"
                    },
                    "vat_code": 1,
                    "payment_mode": "full_prepayment",
                    "payment_subject": "service"
                }
            ]
        },
        "metadata": {
            "user_id": str(user["id"]),
            "amount": str(amount),
            "email": user["email"]
        }
    }

    req_yoo = urllib.request.Request(
        f"{YOOKASSA_API_URL}/payments",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Basic {auth_header}",
            "Idempotence-Key": idempotence_key,
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req_yoo, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            payment_id = resp_data.get("id")
            conf_url = resp_data.get("confirmation", {}).get("confirmation_url")
            status = resp_data.get("status", "pending")
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            with get_db() as conn:
                conn.execute("""
                    INSERT INTO payments (payment_id, user_id, amount, status, description, confirmation_url, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (payment_id, user["id"], amount, status, payload["description"], conf_url, now_str, now_str))
                conn.commit()

            return {
                "status": "ok",
                "payment_id": payment_id,
                "confirmation_url": conf_url
            }
    except Exception as e:
        print(f"[YOOKASSA ERROR] Failed to create payment: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать платеж через платёжный шлюз")

@router.get("/api/v1/profile/payment-status", summary="Check payment status (canonical)")
@router.get("/api/v1/profile/payment/check", include_in_schema=False)
def profile_payment_status(
    payment_id: Optional[str] = None,
    user: Optional[Dict[str, Any]] = Depends(get_optional_current_user)
):
    with get_db() as conn:
        row = None
        if payment_id:
            row = conn.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()
        elif user:
            # Check pending payments first
            row = conn.execute("SELECT * FROM payments WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
            if not row:
                row = conn.execute("SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
        else:
            raise HTTPException(status_code=401, detail="Требуется авторизация или идентификатор платежа")

        if not row:
            return {"status": "none", "message": "Платежей не найдено"}

        p_id = row["payment_id"]
        current_status = row["status"]

        if current_status == "succeeded":
            return {"status": "succeeded", "amount": row["amount"]}

        auth_header = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
        req_yoo = urllib.request.Request(
            f"{YOOKASSA_API_URL}/payments/{p_id}",
            headers={"Authorization": f"Basic {auth_header}"}
        )

        try:
            with urllib.request.urlopen(req_yoo, timeout=5) as resp:
                yoo_data = json.loads(resp.read().decode("utf-8"))
                real_status = yoo_data.get("status", current_status)
                if real_status == "succeeded":
                    apply_successful_payment(p_id, conn)
                    return {"status": "succeeded", "amount": row["amount"]}
                else:
                    return {"status": real_status, "amount": row["amount"]}
        except Exception:
            return {"status": current_status, "amount": row["amount"]}

@router.post("/api/v1/payments/yookassa-webhook")
async def yookassa_webhook(request: Request):
    """Handles real-time asynchronous notifications from YooKassa with IP whitelist and authoritative verification."""
    # 1. Validate caller IP against official YooKassa subnets
    client_ip_str = extract_webhook_client_ip(request)
    if not is_yookassa_ip(client_ip_str):
        raise HTTPException(status_code=403, detail="Forbidden: Untrusted source IP")

    # 2. Parse incoming webhook notification payload
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    payment_obj = data.get("object", {}) if isinstance(data, dict) else {}
    payment_id = payment_obj.get("id") or (data.get("payment_id") if isinstance(data, dict) else None)
    if not payment_id:
        raise HTTPException(status_code=400, detail="Missing payment id")

    # 3. Verify payment exists in local database
    with get_db() as conn:
        local_pay = conn.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()
        if not local_pay:
            raise HTTPException(status_code=404, detail="Payment record not found in local database")
        if local_pay["status"] == "succeeded":
            return {"status": "ok", "message": "Payment already applied"}
        expected_amount = float(local_pay["amount"])

    # 4. Execute zero-trust authoritative outbound GET to YooKassa REST API
    auth_str = f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}"
    auth_header = base64.b64encode(auth_str.encode()).decode()
    req_yoo = urllib.request.Request(
        f"{YOOKASSA_API_URL}/payments/{payment_id}",
        headers={
            "Authorization": f"Basic {auth_header}",
            "User-Agent": "TabisVPN-Backend-Verifier/2.0"
        }
    )

    try:
        with urllib.request.urlopen(req_yoo, timeout=10) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=502, detail="Gateway query returned non-200")
            gateway_data = json.loads(resp.read().decode("utf-8"))
    except HTTPException:
        raise
    except Exception as e:
        print(f"[YOOKASSA WEBHOOK VERIFY ERROR] {e}")
        raise HTTPException(status_code=502, detail=f"Failed to communicate with YooKassa: {e}")

    # 5. Verify payment object state, currency, and amount
    real_status = gateway_data.get("status")
    amount_obj = gateway_data.get("amount", {})
    currency = amount_obj.get("currency", "")
    try:
        remote_amount = float(amount_obj.get("value", 0))
    except (ValueError, TypeError):
        remote_amount = -1.0

    if real_status != "succeeded":
        raise HTTPException(status_code=400, detail=f"Payment status is not succeeded ({real_status})")

    if currency != "RUB":
        raise HTTPException(status_code=400, detail=f"Invalid payment currency: {currency}")

    if abs(remote_amount - expected_amount) > 0.01:
        raise HTTPException(status_code=400, detail=f"Payment amount mismatch: expected {expected_amount}, got {remote_amount}")

    with get_db() as conn:
        apply_successful_payment(payment_id, conn)

    return {"status": "ok"}

@router.post("/api/v1/profile/nickname")
def profile_update_nickname(req: ProfileNicknameReq, user: Dict[str, Any] = Depends(get_current_user)):
    new_nick = req.nickname.strip()
    if not new_nick or len(new_nick) < 2 or len(new_nick) > 30:
        raise HTTPException(status_code=400, detail="Никнейм должен содержать от 2 до 30 символов")
    
    with get_db() as conn:
        conn.execute("UPDATE users SET nickname = ? WHERE id = ?", (new_nick, user["id"]))
        conn.commit()
    return {"status": "ok", "nickname": new_nick}

@router.post("/api/v1/profile/tariff")
def profile_change_tariff(req: TariffChangeReq, user: Dict[str, Any] = Depends(get_current_user)):
    plan = req.plan.lower().strip()
    if plan not in ("base", "premium"):
        raise HTTPException(status_code=400, detail="Неверный тариф. Допустимы: 'base' или 'premium'")
    
    with get_db() as conn:
        conn.execute("UPDATE users SET tariff_plan = ? WHERE id = ?", (plan, user["id"]))
        conn.execute("UPDATE user_devices SET tariff_plan = ? WHERE user_id = ?", (plan, user["id"]))
        speed_mbps = 10 if plan == "base" else 0
        tokens = conn.execute("SELECT token FROM user_devices WHERE user_id = ?", (user["id"],)).fetchall()
        for t in tokens:
            conn.execute("UPDATE tokens SET speed_limit_mbps = ? WHERE token = ?", (speed_mbps, t[0]))
        check_user_subscription(user["id"], conn)
        conn.commit()
        
    return {"status": "ok", "tariff_plan": plan}

@router.post("/api/v1/profile/devices", summary="Add new device (canonical)")
@router.post("/api/v1/profile/devices/add", include_in_schema=False)
def profile_add_device(req: ProfileDeviceAddReq, user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["id"]
    raw_name = req.device_name or req.name or "Мое устройство"
    name = raw_name.strip()
    if not name:
        name = "Мое устройство"
    if len(name) > 40:
        name = name[:40]
    
    with get_db() as conn:
        u_row = conn.execute("SELECT device_limit, balance, tariff_plan FROM users WHERE id = ?", (user_id,)).fetchone()
        limit = max(5, u_row["device_limit"] if (u_row and u_row["device_limit"]) else 5)
        current_count = conn.execute("SELECT COUNT(*) FROM user_devices WHERE user_id = ?", (user_id,)).fetchone()[0]
        if current_count >= limit:
            raise HTTPException(status_code=400, detail=f"Достигнут лимит устройств ({limit}). Удалите неиспользуемое устройство.")
        
        token = generate_device_token()
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        today_str = date.today().isoformat()
        
        plan = req.tariff_plan if req.tariff_plan in ("base", "premium") else (u_row["tariff_plan"] or "base")
        speed_mbps = 10 if plan == "base" else 0
        
        conn.execute("""
            INSERT INTO tokens (token, label, speed_limit_mbps, last_reset_day, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (token, f"{user['nickname']} ({name})", speed_mbps, today_str, now_str))
        
        cur = conn.execute("""
            INSERT INTO user_devices (user_id, device_name, token, is_active, tariff_plan, created_at)
            VALUES (?, ?, ?, 1, ?, ?)
        """, (user_id, name, token, plan, now_str))
        dev_id = cur.lastrowid
        
        check_device_subscription(dev_id, conn)

        dev_row = conn.execute("SELECT is_active FROM user_devices WHERE id = ?", (dev_id,)).fetchone()
        is_active = bool(dev_row and dev_row["is_active"])
        conn.commit()
        
    return {
        "status": "ok",
        "message": f"Устройство {name} успешно добавлено!",
        "device": {
            "id": dev_id,
            "device_name": name,
            "token": token,
            "tariff_plan": plan,
            "is_active": 1 if is_active else 0,
            "created_at": now_str
        }
    }

@router.post("/api/v1/profile/devices/limit", summary="Set device limit (canonical)")
def profile_set_device_limit(req: ProfileDeviceLimitReq, user: Dict[str, Any] = Depends(get_current_user)):
    if req.device_limit < 1 or req.device_limit > 5:
        raise HTTPException(status_code=400, detail="Лимит устройств должен быть от 1 до 5")
    with get_db() as conn:
        conn.execute("UPDATE users SET device_limit = ? WHERE id = ?", (req.device_limit, user["id"]))
        conn.commit()
    return {"status": "ok", "device_limit": req.device_limit}

@router.post("/api/v1/profile/devices/{device_id}/tariff")
def profile_device_change_tariff(device_id: int, req: ProfileDeviceTariffReq, user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["id"]
    plan = req.tariff_plan.lower().strip()
    if plan not in ("base", "premium"):
        raise HTTPException(status_code=400, detail="Неверный тариф (только base или premium)")
    
    with get_db() as conn:
        dev = conn.execute("SELECT * FROM user_devices WHERE id = ? AND user_id = ?", (device_id, user_id)).fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail="Устройство не найдено")
        
        conn.execute("UPDATE user_devices SET tariff_plan = ? WHERE id = ?", (plan, device_id))
        speed_mbps = 10 if plan == "base" else 0
        conn.execute("UPDATE tokens SET speed_limit_mbps = ? WHERE token = ?", (speed_mbps, dev["token"]))
        check_device_subscription(device_id, conn)
        conn.commit()
        
    return {"status": "ok", "tariff_plan": plan}

@router.post("/api/v1/profile/devices/{device_id}/renew", summary="Renew device subscription (canonical)")
@router.post("/api/v1/profile/devices/{device_id}/activate", include_in_schema=False)
def profile_device_activate(device_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["id"]
    with get_db() as conn:
        dev = conn.execute("SELECT * FROM user_devices WHERE id = ? AND user_id = ?", (device_id, user_id)).fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail="Устройство не найдено")
        
        u = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        plan = dev["tariff_plan"] or "base"
        daily_cost = 8 if plan == "premium" else 2
        
        if not u or (u["balance"] or 0) < daily_cost:
            raise HTTPException(status_code=400, detail=f"Недостаточно средств. Для активации требуется минимум {daily_cost} ₽")
        
        today_obj = date.today()
        today_str = today_obj.isoformat()
        new_bal = u["balance"] - daily_cost
        conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_bal, user_id))
        
        days_ahead = new_bal // daily_cost
        new_exp = (today_obj + timedelta(days=days_ahead)).isoformat()
        
        conn.execute("""
            UPDATE user_devices 
            SET subscription_expires_at = ?, is_active = 1, last_billing_date = ? 
            WHERE id = ?
        """, (new_exp, today_str, device_id))
        
        speed_mbps = 10 if plan == "base" else 0
        conn.execute("UPDATE tokens SET is_active = 1, speed_limit_mbps = ? WHERE token = ?", (speed_mbps, dev["token"]))
        conn.commit()
        
    return {"status": "ok", "subscription_expires_at": new_exp, "message": f"Устройство успешно активировано на базе тарифа {'Базовый (2 ₽/день)' if plan == 'base' else 'Премиальный (8 ₽/день)'}"}

@router.delete("/api/v1/profile/devices/{device_id}", summary="Delete device (canonical)")
@router.post("/api/v1/profile/devices/{device_id}/delete", include_in_schema=False)
def profile_delete_device(device_id: int, user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["id"]
    with get_db() as conn:
        dev = conn.execute("SELECT * FROM user_devices WHERE id = ? AND user_id = ?", (device_id, user_id)).fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail="Устройство не найдено")
        
        tok = dev["token"]
        conn.execute("DELETE FROM user_devices WHERE id = ?", (device_id,))
        conn.execute("DELETE FROM tokens WHERE token = ?", (tok,))
        kick_hy2_user(tok)
        conn.commit()
        
    return {"status": "ok", "message": "Устройство отключено и удалено"}

@router.post("/api/v1/profile/delete-account/send-otp")
def profile_delete_account_send_otp(user: Dict[str, Any] = Depends(get_current_user)):
    email = user["email"]
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = time.time() + 600
    with get_db() as conn:
        conn.execute("INSERT INTO email_otps (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)",
                     (email, code, expires_at, time.time()))
        conn.commit()
    delivered = send_email_otp(email, code, subject="Подтверждение удаления аккаунта Tabis VPN")
    if not delivered:
        raise HTTPException(status_code=500, detail="Не удалось отправить проверочный код на email")
    return {"status": "ok", "message": f"Код подтверждения отправлен на {email}"}

@router.post("/api/v1/profile/delete-account/complete")
def profile_delete_account_complete(req: DeleteAccountCompleteReq, user: Dict[str, Any] = Depends(get_current_user)):
    user_id = user["id"]
    email = user["email"]
    code = req.code.strip()
    with get_db() as conn:
        otp = conn.execute("""
            SELECT rowid FROM email_otps 
            WHERE email = ? AND code = ? AND expires_at >= ?
            ORDER BY rowid DESC LIMIT 1
        """, (email, code, time.time())).fetchone()
        if not otp:
            raise HTTPException(status_code=400, detail="Неверный или просроченный проверочный код")
        
        dev_tokens = [r[0] for r in conn.execute("SELECT token FROM user_devices WHERE user_id = ?", (user_id,)).fetchall()]
        for tok in dev_tokens:
            conn.execute("DELETE FROM tokens WHERE token = ?", (tok,))
            kick_hy2_user(tok)
            
        conn.execute("DELETE FROM user_devices WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM payments WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM referral_logs WHERE referrer_id = ? OR referred_user_id = ?", (user_id, user_id))
        conn.execute("DELETE FROM email_otps WHERE email = ?", (email,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        
    return {"status": "ok", "message": "Аккаунт и все связанные устройства успешно удалены"}

@router.post("/api/v1/profile/referral/generate")
@router.get("/api/v1/profile/referral")
def profile_generate_referral(user: Dict[str, Any] = Depends(get_current_user)):
    with get_db() as conn:
        row = conn.execute("SELECT referral_code FROM users WHERE id = ?", (user["id"],)).fetchone()
        current_code = row["referral_code"] if row and row["referral_code"] else None
        if not current_code:
            current_code = generate_referral_code()
            conn.execute("UPDATE users SET referral_code = ? WHERE id = ?", (current_code, user["id"]))
            conn.commit()
    return {
        "status": "ok",
        "referral_code": current_code,
        "link": f"https://tabisvpn.site/profile/auth?ref={current_code}"
    }

@router.get("/api/v1/profile/servers")
def profile_get_servers():
    return {"status": "ok", "servers": get_real_servers_list()}

# --- CLIENT SUPPORT CHAT ENDPOINTS ---

@router.post("/api/v1/support/messages")
def support_client_send_message(req: SupportClientMsgReq, request: Request):
    """User / guest sends message to support chat from widget."""
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    if len(clean_msg) > 3000:
        raise HTTPException(status_code=400, detail="Сообщение слишком длинное")

    clean_session = req.session_token.strip()
    if not clean_session:
        raise HTTPException(status_code=400, detail="Отсутствует токен сессии чата")

    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "")
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Check if user session token is attached
    auth_header = request.headers.get("Authorization", "")
    user_id = None
    client_name = "Гость"
    client_email = ""

    with get_db() as conn:
        if auth_header.startswith("Bearer sess_"):
            u_sess_token = auth_header.replace("Bearer ", "").strip()
            s_row = conn.execute("SELECT user_id FROM user_sessions WHERE token = ? AND expires_at >= ?", (u_sess_token, time.time())).fetchone()
            if s_row:
                user_id = s_row["user_id"]
                u_row = conn.execute("SELECT email, nickname, user_code FROM users WHERE id = ?", (user_id,)).fetchone()
                if u_row:
                    client_name = u_row["nickname"] or f"Пользователь #{user_id}"
                    client_email = u_row["email"] or ""

        # Find or create support dialog
        dlg = conn.execute("SELECT id FROM support_dialogs WHERE session_token = ?", (clean_session,)).fetchone()
        if not dlg:
            cur = conn.execute("""
                INSERT INTO support_dialogs (session_token, user_id, client_name, client_email, client_ip, page_url, status, unread_admin, unread_user, created_at, last_message_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', 1, 0, ?, ?)
            """, (clean_session, user_id, client_name, client_email, client_ip, req.page_url or "", now_str, now_str))
            dialog_id = cur.lastrowid
        else:
            dialog_id = dlg["id"]
            conn.execute("""
                UPDATE support_dialogs 
                SET unread_admin = unread_admin + 1, last_message_at = ?, status = 'open',
                    user_id = COALESCE(?, user_id), client_name = CASE WHEN ? != 'Гость' THEN ? ELSE client_name END,
                    client_email = CASE WHEN ? != '' THEN ? ELSE client_email END, client_ip = ?
                WHERE id = ?
            """, (now_str, user_id, client_name, client_name, client_email, client_email, client_ip, dialog_id))

        # Insert message
        conn.execute("""
            INSERT INTO support_messages (dialog_id, sender_type, sender_name, text, created_at, is_read)
            VALUES (?, 'user', ?, ?, ?, 0)
        """, (dialog_id, client_name, clean_msg, now_str))
        conn.commit()

    notify_token_update("support_message")
    return {"ok": True, "created_at": now_str}

@router.get("/api/v1/support/messages", summary="Get support messages (canonical)")
@router.get("/api/v1/support/history", include_in_schema=False)
def support_client_get_messages(session_token: str = Query(...)):
    """User / guest fetches conversation thread for active widget."""
    clean_session = session_token.strip()
    if not clean_session:
        raise HTTPException(status_code=400, detail="Отсутствует токен сессии")

    with get_db() as conn:
        dlg = conn.execute("SELECT * FROM support_dialogs WHERE session_token = ?", (clean_session,)).fetchone()
        if not dlg:
            return {"dialog": None, "messages": []}

        # Mark admin messages as read by user
        conn.execute("UPDATE support_messages SET is_read = 1 WHERE dialog_id = ? AND sender_type = 'admin'", (dlg["id"],))
        conn.execute("UPDATE support_dialogs SET unread_user = 0 WHERE id = ?", (dlg["id"],))
        conn.commit()

        messages = conn.execute("""
            SELECT id, sender_type, sender_name, text, created_at, is_read 
            FROM support_messages 
            WHERE dialog_id = ? 
            ORDER BY id ASC
        """, (dlg["id"],)).fetchall()

        return {
            "dialog": {
                "id": dlg["id"],
                "status": dlg["status"],
                "unread_user": 0,
                "last_message_at": dlg["last_message_at"]
            },
            "messages": [dict(m) for m in messages]
        }
