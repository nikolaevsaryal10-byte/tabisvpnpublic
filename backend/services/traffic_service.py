import os
import sys
import time
import json
import socket
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Any
from database import get_db

_token_device_cache: Dict[str, Any] = {}
_recent_traffic_visits: Dict[str, float] = {}
_recent_traffic_lock = threading.Lock()

def parse_host_port(addr_str: str):
    if not addr_str:
        return "", 0
    addr_str = addr_str.strip()
    if addr_str.startswith("["):
        parts = addr_str.rsplit("]:", 1)
        if len(parts) == 2:
            return parts[0].lstrip("["), int(parts[1]) if parts[1].isdigit() else 0
        return addr_str.strip("[]"), 0
    parts = addr_str.rsplit(":", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0], int(parts[1])
    return addr_str, 0

def resolve_token_info(conn, token: str):
    clean_tok = token.strip().upper()
    now = time.time()
    cached = _token_device_cache.get(clean_tok)
    if cached and (now - cached.get("time", 0)) < 180:
        return cached.get("user_id"), cached.get("device_name")

    user_id = None
    device_name = ""
    try:
        row = conn.execute("""
            SELECT ud.user_id, ud.device_name 
            FROM user_devices ud 
            WHERE UPPER(ud.token) = ?
        """, (clean_tok,)).fetchone()
        if row:
            user_id = row["user_id"]
            device_name = row["device_name"] or ""
        else:
            t_row = conn.execute("SELECT label FROM tokens WHERE UPPER(token) = ?", (clean_tok,)).fetchone()
            if t_row and t_row["label"]:
                device_name = t_row["label"]
    except Exception:
        pass

    _token_device_cache[clean_tok] = {
        "user_id": user_id,
        "device_name": device_name,
        "time": now
    }
    return user_id, device_name

def record_traffic_event(event_type: str, token: str, client_ip: str, client_port: int,
                         target_domain: str = "", target_ip: str = "", target_port: int = 0,
                         protocol: str = "", details: str = ""):
    try:
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        with get_db() as conn:
            user_id, device_name = resolve_token_info(conn, token)
            conn.execute("""
                INSERT INTO traffic_audit_logs 
                (created_at, user_id, token, device_name, client_ip, client_port, 
                 event_type, target_domain, target_ip, target_port, protocol, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (now_str, user_id, token.strip().upper(), device_name, client_ip, client_port,
                  event_type, target_domain, target_ip, target_port, protocol, details))
            conn.commit()
    except Exception as e:
        print(f"[TRAFFIC AUDIT ERROR] Failed to record event: {e}", file=sys.stderr)

def process_hysteria_log_record(record: dict):
    msg = record.get("msg", "")
    token = (record.get("id") or "").strip()
    addr = record.get("addr", "")
    client_ip, client_port = parse_host_port(addr)

    # 1. Connection established
    if msg == "client connected":
        if token:
            record_traffic_event(
                event_type="CONNECT",
                token=token,
                client_ip=client_ip,
                client_port=client_port,
                details="Подключение к Hysteria 2"
            )
        return

    # 2. Connection closed / disconnected
    if msg == "client disconnected":
        if token:
            err = record.get("error", "closed")
            record_traffic_event(
                event_type="DISCONNECT",
                token=token,
                client_ip=client_ip,
                client_port=client_port,
                details=f"Отключение (причина: {err})"
            )
        return

    # 3. Stream requests (TCP / UDP)
    if msg in ("TCP request", "UDP request"):
        if not token:
            return
        req_addr = record.get("reqAddr", "")
        if not req_addr:
            return

        target_host, target_port = parse_host_port(req_addr)
        if not target_host:
            return

        # Filter out loopback / local node itself
        from config import HYSTERIA_SERVER, HYSTERIA_SNI
        if target_host in ("127.0.0.1", "localhost", "::1", HYSTERIA_SERVER, HYSTERIA_SNI):
            return

        # Determine whether target_host is IP or domain
        is_ip = False
        try:
            socket.inet_aton(target_host)
            is_ip = True
        except Exception:
            if ":" in target_host:
                is_ip = True

        target_domain = "" if is_ip else target_host
        target_ip = target_host if is_ip else ""

        # Sliding 60-second de-duplication per (token, target_host)
        now_ts = time.time()
        dedup_key = f"{token}:{target_host}"
        with _recent_traffic_lock:
            last_ts = _recent_traffic_visits.get(dedup_key, 0.0)
            if (now_ts - last_ts) < 60.0:
                return  # Skip repeated packet within 60s window
            _recent_traffic_visits[dedup_key] = now_ts
            # Cleanup old entries if map grows over 20000
            if len(_recent_traffic_visits) > 20000:
                expired_keys = [k for k, v in _recent_traffic_visits.items() if (now_ts - v) > 300]
                for k in expired_keys:
                    _recent_traffic_visits.pop(k, None)

        proto = "TCP" if msg == "TCP request" else "UDP"
        record_traffic_event(
            event_type="TRAFFIC_VISIT",
            token=token,
            client_ip=client_ip,
            client_port=client_port,
            target_domain=target_domain,
            target_ip=target_ip,
            target_port=target_port,
            protocol=proto,
            details=f"Посещение ресурса ({proto})"
        )

def hysteria_journal_collector_worker():
    if os.name == "nt":
        return
    cmd = ["journalctl", "-u", "hysteria-server", "-f", "-o", "cat", "-n", "0"]
    while True:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
            for line in proc.stdout:
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    record = json.loads(line)
                    process_hysteria_log_record(record)
                except Exception:
                    continue
            proc.wait()
        except Exception as e:
            print(f"[HYSTERIA LOG COLLECTOR ERROR] {e}", file=sys.stderr)
        time.sleep(5)

def traffic_log_retention_worker():
    """Retains logs for 180 days (6 months) as requested, purging older records."""
    time.sleep(60)
    while True:
        try:
            cutoff = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
            with get_db() as conn:
                cur = conn.execute("DELETE FROM traffic_audit_logs WHERE created_at < ?", (cutoff,))
                if cur.rowcount > 0:
                    print(f"[RETENTION] Purged {cur.rowcount} traffic audit log entries older than 180 days.")
                conn.commit()
        except Exception as e:
            print(f"[RETENTION WORKER ERROR] {e}", file=sys.stderr)
        time.sleep(21600)  # Runs every 6 hours
