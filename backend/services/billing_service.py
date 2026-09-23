import time
import base64
import json
import urllib.request
import sqlite3
from datetime import datetime, date, timedelta
from database import get_db, kick_hy2_user, get_hy2_online_users
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, YOOKASSA_API_URL

def check_device_subscription(dev_id: int, conn: sqlite3.Connection):
    """
    Evaluates subscription validity for a single device under daily billing tariff.
    Base = 2 RUB/day (up to 100 GB traffic per month, speed limited to 10 Mbps)
    Premium = 8 RUB/day (unlimited traffic, max speed up to 300 Mbps)
    Daily deduction runs automatically on connect/access if balance permits.
    Deactivates immediately if balance is insufficient.
    """
    today_obj = date.today()
    today_str = today_obj.isoformat()
    current_month_str = today_str[:7]
    dev = conn.execute("SELECT * FROM user_devices WHERE id = ?", (dev_id,)).fetchone()
    if not dev:
        return

    user = conn.execute("SELECT * FROM users WHERE id = ?", (dev["user_id"],)).fetchone()
    if not user:
        return

    plan = dev["tariff_plan"] or "base"
    daily_cost = 8 if plan == "premium" else 2
    token = dev["token"]
    user_id = user["id"]
    balance = user["balance"] or 0
    last_billing = dev["last_billing_date"] if "last_billing_date" in dev.keys() else ""
    last_reset = dev["last_traffic_reset_month"] or ""

    # Monthly traffic reset on new calendar month
    if last_reset != current_month_str:
        conn.execute("UPDATE user_devices SET month_traffic_bytes = 0, last_traffic_reset_month = ? WHERE id = ?", (current_month_str, dev_id))

    # Calculate days to bill
    if not last_billing:
        days_due = 1
    else:
        try:
            last_date_obj = date.fromisoformat(last_billing[:10])
            days_due = max(0, (today_obj - last_date_obj).days)
        except Exception:
            days_due = 1

    if days_due > 0:
        total_due = days_due * daily_cost
        if balance >= daily_cost:
            charged_days = min(days_due, balance // daily_cost)
            charge_rub = charged_days * daily_cost
            new_bal = max(0, balance - charge_rub)
            conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_bal, user_id))
            balance = new_bal
            
            days_ahead = balance // daily_cost
            new_exp = (today_obj + timedelta(days=days_ahead)).isoformat()
            
            conn.execute("""
                UPDATE user_devices 
                SET last_billing_date = ?, subscription_expires_at = ?, is_active = 1
                WHERE id = ?
            """, (today_str, new_exp, dev_id))
            
            speed_mbps = 10 if plan == "base" else 0
            conn.execute("UPDATE tokens SET is_active = 1, speed_limit_mbps = ? WHERE token = ?", (speed_mbps, token))
        else:
            conn.execute("""
                UPDATE user_devices 
                SET is_active = 0, subscription_expires_at = '' 
                WHERE id = ?
            """, (dev_id,))
            conn.execute("UPDATE tokens SET is_active = 0 WHERE token = ?", (token,))
            kick_hy2_user(token)
    else:
        if balance >= daily_cost:
            days_ahead = balance // daily_cost
            new_exp = (today_obj + timedelta(days=days_ahead)).isoformat()
            conn.execute("UPDATE user_devices SET subscription_expires_at = ?, is_active = 1 WHERE id = ?", (new_exp, dev_id))
            speed_mbps = 10 if plan == "base" else 0
            conn.execute("UPDATE tokens SET is_active = 1, speed_limit_mbps = ? WHERE token = ?", (speed_mbps, token))
        else:
            conn.execute("UPDATE user_devices SET is_active = 0, subscription_expires_at = '' WHERE id = ?", (dev_id,))
            conn.execute("UPDATE tokens SET is_active = 0 WHERE token = ?", (token,))
            kick_hy2_user(token)

    conn.commit()

def check_user_subscription(user_id: int, conn: sqlite3.Connection):
    """Checks all devices belonging to the user."""
    dev_ids = [r[0] for r in conn.execute("SELECT id FROM user_devices WHERE user_id = ?", (user_id,)).fetchall()]
    for d_id in dev_ids:
        check_device_subscription(d_id, conn)

def check_user_daily_billing(user_id: int, conn: sqlite3.Connection):
    check_user_subscription(user_id, conn)

def apply_successful_payment(payment_id: str, conn: sqlite3.Connection) -> bool:
    """
    Safely credits user balance and activates devices when a YooKassa payment succeeds.
    Guarantees idempotency (never credits twice).
    """
    row = conn.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()
    if not row:
        return False
    if row["status"] == "succeeded":
        return True

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE payments SET status = 'succeeded', updated_at = ? WHERE payment_id = ?", (now_str, payment_id))

    user_id = row["user_id"]
    amount = row["amount"]

    # Credit balance
    conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    
    # Activate user devices and tokens
    conn.execute("UPDATE user_devices SET is_active = 1 WHERE user_id = ?", (user_id,))
    tokens = conn.execute("SELECT token FROM user_devices WHERE user_id = ?", (user_id,)).fetchall()
    for t in tokens:
        conn.execute("UPDATE tokens SET is_active = 1 WHERE token = ?", (t[0],))

    # Referral bonus (+60 RUB) on first payment >= 60
    user = conn.execute("SELECT referred_by FROM users WHERE id = ?", (user_id,)).fetchone()
    if user and user["referred_by"] and amount >= 60:
        already_rewarded = conn.execute(
            "SELECT id FROM referral_logs WHERE referred_user_id = ? AND bonus_rub >= 60", (user_id,)
        ).fetchone()
        if not already_rewarded:
            ref_owner = conn.execute("SELECT id FROM users WHERE referral_code = ?", (user["referred_by"],)).fetchone()
            if ref_owner:
                conn.execute("UPDATE users SET balance = balance + 60 WHERE id = ?", (ref_owner["id"],))
                conn.execute(
                    "INSERT INTO referral_logs (referrer_id, referred_user_id, bonus_rub, created_at) VALUES (?, ?, 60, ?)",
                    (ref_owner["id"], user_id, now_str)
                )

    conn.commit()
    return True


def reconcile_yookassa_pending_payments(max_batch: int = 20) -> int:
    """
    Reconciles recently created pending payments against YooKassa REST API.
    - Active checking is restricted to payments created within the last 2 hours.
    - Payments older than 24 hours that remain pending are automatically marked as canceled.
    - Returns the count of active payments checked.
    """
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        return 0

    auth_header = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
    checked_count = 0

    with get_db() as conn:
        now_dt = datetime.utcnow()
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Auto-expire abandoned pending payments older than 24 hours
        expire_cutoff = (now_dt - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE payments SET status = 'canceled', updated_at = ? WHERE status = 'pending' AND created_at < ?",
            (now_str, expire_cutoff)
        )
        conn.commit()

        # Find active pending payments from the last 2 hours
        active_cutoff = (now_dt - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        pending = conn.execute(
            "SELECT payment_id, user_id, amount FROM payments WHERE status = 'pending' AND created_at >= ? ORDER BY id DESC LIMIT ?",
            (active_cutoff, max_batch)
        ).fetchall()

        for row in pending:
            checked_count += 1
            p_id = row["payment_id"]
            req_yoo = urllib.request.Request(
                f"{YOOKASSA_API_URL}/payments/{p_id}",
                headers={"Authorization": f"Basic {auth_header}"}
            )
            try:
                with urllib.request.urlopen(req_yoo, timeout=6) as resp:
                    yoo_data = json.loads(resp.read().decode("utf-8"))
                    real_status = yoo_data.get("status")
                    if real_status == "succeeded":
                        apply_successful_payment(p_id, conn)
                        print(f"[BILLING RECONCILER] Successfully credited payment {p_id} (+{row['amount']} RUB) for user {row['user_id']}")
                    elif real_status == "canceled":
                        conn.execute("UPDATE payments SET status = 'canceled', updated_at = ? WHERE payment_id = ?", (now_str, p_id))
                        conn.commit()
            except Exception:
                pass

    return checked_count


def yookassa_reconciliation_worker_loop():
    """
    Autonomous background worker that runs periodically (every 60 seconds).
    Reconciles recently created pending payments against YooKassa REST API.
    - Active checking is restricted to payments created within the last 2 hours.
    - Payments older than 24 hours that remain pending are automatically marked as canceled.
    - Avoids API spam, prevents rate limits, and safely credits completed payments.
    """
    while True:
        try:
            reconcile_yookassa_pending_payments(max_batch=20)
        except Exception as e:
            print(f"[BILLING RECONCILER ERROR] {e}")
        time.sleep(60)


def hy2_single_device_watchdog_loop():
    """
    Real-time enforcer for 1-device-per-key policy.
    Queries Hysteria 2 core (/online) every 3 seconds.
    If any client token has online > 1 (multiple simultaneous connections):
    immediately disconnects the duplicate sessions to prevent unauthorized sharing.
    """
    while True:
        try:
            online = get_hy2_online_users()
            for token, count in online.items():
                if token == "admin_master":
                    continue
                if count > 1:
                    print(f"[HY2 WATCHDOG] Multi-device violation: token {token} has {count} active connections! Enforcing 1-device limit.")
                    kick_hy2_user(token)
        except Exception as e:
            pass
        time.sleep(3)
