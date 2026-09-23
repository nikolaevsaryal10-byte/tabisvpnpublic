import sqlite3
import hashlib
import json
import urllib.request
from datetime import datetime, date, timedelta
from config import DB_PATH, ADMIN_USER, ADMIN_PASS_DEFAULT

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn

def kick_hy2_user(token: str):
    """Disconnects user from Hysteria 2 instantly via traffic logger kick API."""
    try:
        clean_token = token.strip().upper()
        data = json.dumps([clean_token]).encode('utf-8')
        req = urllib.request.Request("http://127.0.0.1:9999/kick", data=data)
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "TabisTrafficSecret2026!")
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass

def get_hy2_online_users() -> dict:
    """Returns dict of active online counts: { 'TOKEN': count } from Hysteria 2 core."""
    try:
        req = urllib.request.Request("http://127.0.0.1:9999/online")
        req.add_header("Authorization", "TabisTrafficSecret2026!")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return {}

def init_db():
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                label TEXT,
                device_id TEXT,
                device_model TEXT,
                last_ip TEXT,
                traffic_up INTEGER DEFAULT 0,
                traffic_down INTEGER DEFAULT 0,
                traffic_today_up INTEGER DEFAULT 0,
                traffic_today_down INTEGER DEFAULT 0,
                speed_limit_mbps INTEGER DEFAULT 0,
                last_reset_day TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                last_seen_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                username TEXT PRIMARY KEY,
                password_hash TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS server_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                cpu_percent REAL NOT NULL,
                ram_used_mb REAL NOT NULL,
                ram_total_mb REAL NOT NULL,
                ram_percent REAL NOT NULL,
                net_rx_mbps REAL NOT NULL,
                net_tx_mbps REAL NOT NULL,
                traffic_today_rx INTEGER DEFAULT 0,
                traffic_today_tx INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_ts ON server_metrics(timestamp)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER DEFAULT NULL,
                action TEXT NOT NULL,
                target TEXT DEFAULT '',
                details TEXT DEFAULT '',
                client_ip TEXT DEFAULT '',
                dest_ip TEXT DEFAULT '',
                dest_domain TEXT DEFAULT '',
                ip TEXT DEFAULT ''
            )
        """)
        # Migration for existing audit_logs table
        audit_cols = {row[1] for row in conn.execute("PRAGMA table_info(audit_logs)").fetchall()}
        if "user_id" not in audit_cols:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN user_id INTEGER DEFAULT NULL")
        if "client_ip" not in audit_cols:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN client_ip TEXT DEFAULT ''")
        if "dest_ip" not in audit_cols:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN dest_ip TEXT DEFAULT ''")
        if "dest_domain" not in audit_cols:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN dest_domain TEXT DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_logs(id DESC)")

        # Deep traffic audit logs (180 days retention)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traffic_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_id INTEGER DEFAULT NULL,
                token TEXT NOT NULL,
                device_name TEXT DEFAULT '',
                client_ip TEXT DEFAULT '',
                client_port INTEGER DEFAULT 0,
                event_type TEXT NOT NULL,
                target_domain TEXT DEFAULT '',
                target_ip TEXT DEFAULT '',
                target_port INTEGER DEFAULT 0,
                protocol TEXT DEFAULT '',
                details TEXT DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_token ON traffic_audit_logs(token)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_domain ON traffic_audit_logs(target_domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_event ON traffic_audit_logs(event_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_created ON traffic_audit_logs(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traffic_user ON traffic_audit_logs(user_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                ip TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                locked_until REAL DEFAULT 0,
                last_attempt REAL DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS vault_notes (
                key TEXT PRIMARY KEY,
                content TEXT,
                updated_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_release (
                id INTEGER PRIMARY KEY,
                version_code INTEGER NOT NULL,
                version_name TEXT NOT NULL,
                changelog TEXT DEFAULT '',
                download_url TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # Ensure latest v2.5.5 release record is set
        conn.execute("""
            INSERT INTO app_release (id, version_code, version_name, changelog, download_url, updated_at)
            VALUES (1, 4000755, '2.5.5', 'Обновление v2.5.5: официальный релизный сертификат Tabis VPN, обновленный идентификатор site.tabisvpn.app, повышение стабильности и безопасности соединения.', 'https://tabisvpn.site/downloads/TabisVPN.apk', datetime('now', 'localtime'))
            ON CONFLICT(id) DO UPDATE SET
                version_code = 4000755,
                version_name = '2.5.5',
                changelog = 'Обновление v2.5.5: официальный релизный сертификат Tabis VPN, обновленный идентификатор site.tabisvpn.app, повышение стабильности и безопасности соединения.',
                download_url = 'https://tabisvpn.site/downloads/TabisVPN.apk',
                updated_at = datetime('now', 'localtime')
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS support_dialogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_token TEXT UNIQUE NOT NULL,
                user_id INTEGER DEFAULT NULL,
                client_name TEXT DEFAULT 'Гость',
                client_email TEXT DEFAULT '',
                client_ip TEXT DEFAULT '',
                page_url TEXT DEFAULT '',
                status TEXT DEFAULT 'open',
                unread_admin INTEGER DEFAULT 0,
                unread_user INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_message_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dialog_id INTEGER NOT NULL,
                sender_type TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_read INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sup_msg_dlg ON support_messages(dialog_id, id ASC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sup_dlg_token ON support_dialogs(session_token)")

        # Migration: Add any missing columns to tokens table
        cursor = conn.execute("PRAGMA table_info(tokens)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "traffic_today_up" not in existing_cols:
            conn.execute("ALTER TABLE tokens ADD COLUMN traffic_today_up INTEGER DEFAULT 0")
        if "traffic_today_down" not in existing_cols:
            conn.execute("ALTER TABLE tokens ADD COLUMN traffic_today_down INTEGER DEFAULT 0")
        if "speed_limit_mbps" not in existing_cols:
            conn.execute("ALTER TABLE tokens ADD COLUMN speed_limit_mbps INTEGER DEFAULT 0")
        if "last_reset_day" not in existing_cols:
            conn.execute("ALTER TABLE tokens ADD COLUMN last_reset_day TEXT DEFAULT ''")

        # Tables for User Profile, Email Auth, Billing & Referrals
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                nickname TEXT NOT NULL,
                user_code TEXT UNIQUE NOT NULL,
                balance INTEGER DEFAULT 60,
                device_limit INTEGER DEFAULT 5,
                referral_code TEXT UNIQUE NOT NULL,
                referred_by TEXT DEFAULT NULL,
                created_at TEXT NOT NULL,
                last_billing_date TEXT DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_ref ON users(referral_code)")

        # Migration: ensure users table has new tariff & subscription fields
        user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "password_hash" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT DEFAULT ''")
        if "tariff_plan" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN tariff_plan TEXT DEFAULT 'base'")
        if "subscription_expires_at" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_expires_at TEXT DEFAULT ''")
        if "month_traffic_bytes" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN month_traffic_bytes INTEGER DEFAULT 0")
        if "last_traffic_reset_month" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN last_traffic_reset_month TEXT DEFAULT ''")

        # Table for user reviews with moderation
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                rating INTEGER NOT NULL DEFAULT 5,
                text TEXT NOT NULL,
                platform TEXT DEFAULT '',
                approved INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_approved ON reviews(approved)")

        # Migration: preserve all active balances and paid days for existing users
        existing_sub_users = conn.execute("SELECT id, balance, tariff_plan, subscription_expires_at FROM users WHERE subscription_expires_at = '' OR subscription_expires_at IS NULL").fetchall()
        for u in existing_sub_users:
            u_id = u["id"]
            u_bal = u["balance"] or 0
            u_plan = u["tariff_plan"] or "base"
            if u_bal > 0:
                paid_days = max(1, u_bal // 2)
                exp_date = (date.today() + timedelta(days=paid_days)).isoformat()
                conn.execute("UPDATE users SET subscription_expires_at = ?, tariff_plan = ? WHERE id = ?", (exp_date, u_plan, u_id))
            else:
                conn.execute("UPDATE users SET subscription_expires_at = '', tariff_plan = ? WHERE id = ?", (u_plan, u_id))

        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_otps (
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_otp_email ON email_otps(email)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS registration_tokens (
                token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_email ON registration_tokens(email)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                platform TEXT DEFAULT 'web',
                device_id TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")

        # Migration: ensure user_sessions has platform and device_id columns
        sess_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_sessions)").fetchall()}
        if "platform" not in sess_cols:
            conn.execute("ALTER TABLE user_sessions ADD COLUMN platform TEXT DEFAULT 'web'")
        if "device_id" not in sess_cols:
            conn.execute("ALTER TABLE user_sessions ADD COLUMN device_id TEXT DEFAULT ''")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_name TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                is_active INTEGER DEFAULT 1,
                tariff_plan TEXT DEFAULT 'base',
                subscription_expires_at TEXT DEFAULT '',
                month_traffic_bytes INTEGER DEFAULT 0,
                last_traffic_reset_month TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_devices_user ON user_devices(user_id)")

        # Migration: ensure existing user_devices table has per-device tariff & subscription fields
        dev_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_devices)").fetchall()}
        if "tariff_plan" not in dev_cols:
            conn.execute("ALTER TABLE user_devices ADD COLUMN tariff_plan TEXT DEFAULT 'base'")
        if "subscription_expires_at" not in dev_cols:
            conn.execute("ALTER TABLE user_devices ADD COLUMN subscription_expires_at TEXT DEFAULT ''")
        if "month_traffic_bytes" not in dev_cols:
            conn.execute("ALTER TABLE user_devices ADD COLUMN month_traffic_bytes INTEGER DEFAULT 0")
        if "last_traffic_reset_month" not in dev_cols:
            conn.execute("ALTER TABLE user_devices ADD COLUMN last_traffic_reset_month TEXT DEFAULT ''")
        if "last_billing_date" not in dev_cols:
            conn.execute("ALTER TABLE user_devices ADD COLUMN last_billing_date TEXT DEFAULT ''")

        # Propagate user subscriptions to devices
        users_with_sub = conn.execute("SELECT id, tariff_plan, subscription_expires_at FROM users WHERE subscription_expires_at != '' AND subscription_expires_at IS NOT NULL").fetchall()
        for u in users_with_sub:
            u_plan = u["tariff_plan"] or "base"
            u_exp = u["subscription_expires_at"] or ""
            conn.execute("""
                UPDATE user_devices 
                SET tariff_plan = ?, subscription_expires_at = ?
                WHERE user_id = ? AND (subscription_expires_at = '' OR subscription_expires_at IS NULL)
            """, (u_plan, u_exp, u["id"]))

        conn.execute("""
            CREATE TABLE IF NOT EXISTS referral_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_user_id INTEGER NOT NULL,
                bonus_rub INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ref_referrer ON referral_logs(referrer_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                description TEXT DEFAULT '',
                confirmation_url TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_yoo ON payments(payment_id)")

        # Create default admin if not exists
        cur = conn.execute("SELECT username FROM admins WHERE username = ?", (ADMIN_USER,))
        if not cur.fetchone():
            h = hashlib.sha256(ADMIN_PASS_DEFAULT.encode('utf-8')).hexdigest()
            conn.execute("INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
                         (ADMIN_USER, h, datetime.utcnow().isoformat()))

        # Migration: Normalize all device tokens from TABIS-USR- to standard TABIS-
        conn.execute("UPDATE tokens SET token = REPLACE(token, 'TABIS-USR-', 'TABIS-') WHERE token LIKE 'TABIS-USR-%'")
        conn.execute("UPDATE user_devices SET token = REPLACE(token, 'TABIS-USR-', 'TABIS-') WHERE token LIKE 'TABIS-USR-%'")
        conn.execute("UPDATE users SET device_limit = 5 WHERE device_limit < 5 OR device_limit IS NULL")
        sess_cols = {row[1] for row in conn.execute("PRAGMA table_info(user_sessions)").fetchall()}
        if "platform" not in sess_cols:
            conn.execute("ALTER TABLE user_sessions ADD COLUMN platform TEXT DEFAULT 'web'")
        conn.commit()
