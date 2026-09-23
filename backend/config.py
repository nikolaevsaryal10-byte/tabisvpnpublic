import os
import asyncio
from pathlib import Path
from typing import Dict, Any, List

# --- BASE DIRECTORIES & PATHS ---
_default_db = "/root/tabis-backend/tabis.db" if os.name != "nt" else os.path.join(os.path.dirname(__file__), "tabis.db")
_default_servers = "/root/tabis-backend/servers.txt" if os.name != "nt" else os.path.join(os.path.dirname(__file__), "servers.txt")

DB_PATH = os.getenv("DB_PATH", _default_db)
SERVERS_FILE = os.getenv("SERVERS_FILE", _default_servers)
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))

# Allowed roots for Web File Explorer
ALLOWED_FS_ROOTS = [
    Path("/root/tabis-backend").resolve(),
    Path("/etc/hysteria").resolve(),
    Path("/var/www/tabisvpn").resolve(),
    Path("/etc/nginx/sites-available").resolve(),
]

# --- SMTP CONFIGURATION FOR EMAIL AUTH ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "Tabis VPN <support@tabisvpn.site>")

# --- YOOKASSA PAYMENT GATEWAY ---
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
YOOKASSA_API_URL = os.getenv("YOOKASSA_API_URL", "https://api.yookassa.ru/v3")

# --- DEFAULT ADMIN CREDENTIALS ---
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS_DEFAULT = os.getenv("ADMIN_PASS", "ChangeMeImmediately!")
ADMIN_BYPASS_TOKEN = os.getenv("ADMIN_BYPASS_TOKEN", "")

# --- AES-256-CBC KEYS (matching TabisSecurityManager.kt in Android app) ---
AES_KEY = os.getenv("AES_KEY", "TabisVpnSafeKey_2026_Encrypted32").encode("utf-8")[:32]
AES_IV = os.getenv("AES_IV", "TabisVpnInitIV16").encode("utf-8")[:16]

# --- NODE / PROXY CORE CONFIGURATION ---
HYSTERIA_SERVER = os.getenv("HYSTERIA_SERVER", "127.0.0.1")
HYSTERIA_PORT = int(os.getenv("HYSTERIA_PORT", "443"))
HYSTERIA_SNI = os.getenv("HYSTERIA_SNI", "tabisvpn.site")

REALITY_SERVER = os.getenv("REALITY_SERVER", "127.0.0.1")
REALITY_PORT = int(os.getenv("REALITY_PORT", "443"))
REALITY_PUBLIC_KEY = os.getenv("REALITY_PUBLIC_KEY", "YOUR_REALITY_PUBLIC_KEY")
REALITY_SHORT_ID = os.getenv("REALITY_SHORT_ID", "000000000000")
REALITY_SNI = os.getenv("REALITY_SNI", "gateway.icloud.com")

# Active Admin Sessions in memory {token: {"username": ..., "expires": ...}}
ADMIN_SESSIONS: Dict[str, Dict[str, Any]] = {}

# SSE Broadcaster Subscribers
ADMIN_SSE_SUBSCRIBERS: List[asyncio.Queue] = []

def notify_token_update(event_type: str = "token_update"):
    """Notifies all connected admin SSE streams without blocking."""
    dead_queues = []
    for q in ADMIN_SSE_SUBSCRIBERS:
        try:
            q.put_nowait(event_type)
        except Exception:
            dead_queues.append(q)
    for dq in dead_queues:
        if dq in ADMIN_SSE_SUBSCRIBERS:
            ADMIN_SSE_SUBSCRIBERS.remove(dq)
