import os
import sqlite3
import json
import uuid
import time
import urllib.parse
import threading
import subprocess
from datetime import datetime, date
from database import get_db
from services.billing_service import check_device_subscription
from config import (
    REALITY_PORT,
    REALITY_PUBLIC_KEY,
    REALITY_SHORT_ID,
    REALITY_SNI,
    REALITY_SERVER
)

XUI_DB_PATH = os.getenv("XUI_DB_PATH", "/etc/x-ui/x-ui.db")

def token_to_uuid(token: str) -> str:
    clean_tok = token.strip().upper()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tabisvpn.site:{clean_tok}"))

def generate_vless_reality_uri(token: str, label: str = "🇸🇪 Швеция (VLESS Reality - iOS)") -> str:
    clean_token = token.strip().upper()
    user_uuid = token_to_uuid(clean_token)
    encoded_label = urllib.parse.quote(label)
    return (
        f"vless://{user_uuid}@{REALITY_SERVER}:{REALITY_PORT}"
        f"?encryption=none&flow=xtls-rprx-vision&security=reality"
        f"&sni={REALITY_SNI}&fp=chrome&pbk={REALITY_PUBLIC_KEY}"
        f"&sid={REALITY_SHORT_ID}&type=tcp#{encoded_label}"
    )

def sync_3xui_clients_and_traffic():
    """
    Bi-directional sync between Tabis VPN database and 3x-ui SQLite database:
    1. Reads active devices from Tabis DB, computes expiry, limits (1 IP, 100GB or unlim),
       and syncs into x-ui.db inbound #1 and client_traffics.
    2. Reads traffic counters from client_traffics and increments usage in Tabis DB.
    3. Restarts x-ui only when clients list actually changes.
    """
    if not os.path.exists(XUI_DB_PATH):
        return

    today_str = date.today().isoformat()
    now_dt = datetime.now()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    now_ms = int(time.time() * 1000)

    # 1. Fetch active users and devices from Tabis DB
    clients_to_add = []
    with get_db() as conn:
        tokens = conn.execute("SELECT * FROM tokens WHERE is_active = 1").fetchall()
        for t in tokens:
            tok = t["token"].strip().upper()
            u_uuid = token_to_uuid(tok)
            dev = conn.execute("SELECT * FROM user_devices WHERE UPPER(token) = ?", (tok,)).fetchone()

            limit_bytes = 0
            expiry_ms = 0
            is_enabled = True

            if dev:
                check_device_subscription(dev["id"], conn)
                ud = conn.execute("SELECT * FROM user_devices WHERE id = ?", (dev["id"],)).fetchone()
                if not ud or not ud["is_active"]:
                    is_enabled = False
                elif ud["subscription_expires_at"]:
                    try:
                        exp_dt = datetime.fromisoformat(ud["subscription_expires_at"])
                        expiry_ms = int(exp_dt.timestamp() * 1000)
                        if now_dt > exp_dt:
                            is_enabled = False
                    except Exception:
                        pass
                
                plan = (ud["tariff_plan"] if ud else "base") or "base"
                if plan == "base":
                    limit_bytes = 100 * 1024 * 1024 * 1024
                    if (ud["month_traffic_bytes"] or 0) >= limit_bytes:
                        is_enabled = False

            clients_to_add.append({
                "id": u_uuid,
                "flow": "xtls-rprx-vision",
                "email": tok,
                "limitIp": 1,
                "totalGB": limit_bytes,
                "expiryTime": expiry_ms,
                "enable": is_enabled,
                "subId": tok,
                "tgId": 0,
                "reset": 0
            })

    # 2. Update 3x-ui database
    try:
        xui_conn = sqlite3.connect(XUI_DB_PATH)
        row = xui_conn.execute("SELECT settings, stream_settings, sniffing FROM inbounds WHERE id = 1").fetchone()
        if not row:
            xui_conn.close()
            return

        settings = json.loads(row[0]) if row[0] else {}
        stream_settings = json.loads(row[1]) if len(row) > 1 and row[1] else {}
        sniffing = json.loads(row[2]) if len(row) > 2 and row[2] else {}
        old_clients = settings.get("clients", [])

        # Verify / enforce streamSettings parameters
        reality_settings = stream_settings.get("realitySettings", {})
        stream_changed = False
        if reality_settings.get("dest") != f"{REALITY_SNI}:443":
            reality_settings["dest"] = f"{REALITY_SNI}:443"
            stream_changed = True
        if reality_settings.get("minClientVer") != "1.8.0":
            reality_settings["minClientVer"] = "1.8.0"
            stream_changed = True
        if not reality_settings.get("fallbacks") or reality_settings["fallbacks"][0].get("dest") != f"{REALITY_SNI}:443":
            reality_settings["fallbacks"] = [{"dest": f"{REALITY_SNI}:443", "xver": 0}]
            stream_changed = True

        if stream_changed:
            stream_settings["realitySettings"] = reality_settings
            xui_conn.execute("UPDATE inbounds SET stream_settings = ? WHERE id = 1", (json.dumps(stream_settings),))

        # Verify / enforce sniffing (critical for iOS TUN / fakeDNS / web browsing)
        sniff_changed = False
        if not sniffing.get("enabled") or not sniffing.get("destOverride"):
            sniffing = {
                "enabled": True,
                "destOverride": ["http", "tls", "quic"],
                "metadataOnly": False,
                "routeOnly": False
            }
            xui_conn.execute("UPDATE inbounds SET sniffing = ? WHERE id = 1", (json.dumps(sniffing),))
            sniff_changed = True

        # Check if clients list changed
        old_keys = [(c.get("id"), c.get("enable"), c.get("totalGB"), c.get("expiryTime"), c.get("flow")) for c in old_clients]
        new_keys = [(c.get("id"), c.get("enable"), c.get("totalGB"), c.get("expiryTime"), c.get("flow")) for c in clients_to_add]

        needs_restart = (sorted(old_keys) != sorted(new_keys)) or stream_changed or sniff_changed

        if needs_restart:
            settings["clients"] = clients_to_add
            xui_conn.execute("UPDATE inbounds SET settings = ? WHERE id = 1", (json.dumps(settings),))

        # Sync relational clients and client_inbounds tables (3x-ui v3.7+ architecture)
        active_emails = set()
        for c in clients_to_add:
            email = c["email"]
            active_emails.add(email)
            u_uuid = c["id"]
            flow = c["flow"]
            limit_ip = c["limitIp"]
            total_gb = c["totalGB"]
            expiry_time = c["expiryTime"]
            enable_val = 1 if c["enable"] else 0

            # Check if exists in clients table
            cl_row = xui_conn.execute("SELECT id, uuid, enable, flow, limit_ip, total_gb, expiry_time FROM clients WHERE email = ?", (email,)).fetchone()
            if not cl_row:
                cur = xui_conn.cursor()
                cur.execute("""
                    INSERT INTO clients (
                        email, sub_id, uuid, flow, limit_ip, total_gb, expiry_time, enable, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (email, email, u_uuid, flow, limit_ip, total_gb, expiry_time, enable_val, now_ms, now_ms))
                client_id = cur.lastrowid
                cur.execute("""
                    INSERT OR REPLACE INTO client_inbounds (client_id, inbound_id, flow_override, created_at)
                    VALUES (?, 1, ?, ?)
                """, (client_id, flow, now_ms))
                needs_restart = True
            else:
                client_id = cl_row[0]
                if (cl_row[1] != u_uuid or cl_row[2] != enable_val or cl_row[3] != flow or 
                    cl_row[4] != limit_ip or cl_row[5] != total_gb or cl_row[6] != expiry_time):
                    xui_conn.execute("""
                        UPDATE clients
                        SET uuid = ?, enable = ?, flow = ?, limit_ip = ?, total_gb = ?, expiry_time = ?, updated_at = ?
                        WHERE id = ?
                    """, (u_uuid, enable_val, flow, limit_ip, total_gb, expiry_time, now_ms, client_id))
                    needs_restart = True

                # Ensure client_inbounds mapping has flow_override = 'xtls-rprx-vision'
                ci_row = xui_conn.execute("SELECT flow_override FROM client_inbounds WHERE client_id = ? AND inbound_id = 1", (client_id,)).fetchone()
                if not ci_row or ci_row[0] != flow:
                    xui_conn.execute("""
                        INSERT OR REPLACE INTO client_inbounds (client_id, inbound_id, flow_override, created_at)
                        VALUES (?, 1, ?, ?)
                    """, (client_id, flow, now_ms))
                    needs_restart = True

        # Disable any clients in x-ui that are no longer active in Tabis DB
        for cl_id, email, is_en in xui_conn.execute("SELECT id, email, enable FROM clients WHERE email LIKE 'TABIS-%'").fetchall():
            if email not in active_emails and is_en:
                xui_conn.execute("UPDATE clients SET enable = 0, updated_at = ? WHERE id = ?", (now_ms, cl_id))
                needs_restart = True

        # Update client_traffics and read traffic consumption
        traffic_deltas = {}
        for c in clients_to_add:
            email = c["email"]
            t_row = xui_conn.execute(
                "SELECT id, up, down, enable, expiry_time, total FROM client_traffics WHERE email = ? AND inbound_id = 1",
                (email,)
            ).fetchone()

            if not t_row:
                xui_conn.execute("""
                    INSERT INTO client_traffics (inbound_id, enable, email, up, down, expiry_time, total, reset, reset_day, reset_max, reset_count)
                    VALUES (1, ?, ?, 0, 0, ?, ?, 0, 0, 0, 0)
                """, (1 if c["enable"] else 0, email, c["expiryTime"], c["totalGB"]))
            else:
                up_bytes = t_row[1] or 0
                down_bytes = t_row[2] or 0
                traffic_deltas[email] = (up_bytes, down_bytes)

                xui_conn.execute("""
                    UPDATE client_traffics 
                    SET enable = ?, expiry_time = ?, total = ?
                    WHERE email = ? AND inbound_id = 1
                """, (1 if c["enable"] else 0, c["expiryTime"], c["totalGB"], email))

        xui_conn.commit()
        xui_conn.close()

        # Sync traffic consumption back to Tabis DB
        if traffic_deltas:
            with get_db() as conn:
                for tok, (up, down) in traffic_deltas.items():
                    total = up + down
                    if total <= 0:
                        continue
                    conn.execute("""
                        UPDATE tokens 
                        SET last_seen_at = ?
                        WHERE UPPER(token) = ?
                    """, (now_str, tok))
                    ud = conn.execute("SELECT id, user_id FROM user_devices WHERE UPPER(token) = ?", (tok,)).fetchone()
                    if ud:
                        conn.execute("UPDATE user_devices SET month_traffic_bytes = MAX(month_traffic_bytes, ?) WHERE id = ?", (total, ud["id"]))
                        conn.execute("UPDATE users SET month_traffic_bytes = MAX(month_traffic_bytes, ?) WHERE id = ?", (total, ud["user_id"]))
                conn.commit()

        if needs_restart:
            subprocess.run(["systemctl", "restart", "x-ui"], check=False)
            print(f"[3X-UI SYNC] Synchronized 3x-ui relational tables & restarted x-ui ({len(clients_to_add)} clients).")

    except Exception as e:
        print(f"[3X-UI SYNC ERROR] {e}")

def start_xray_background_worker():
    def worker():
        time.sleep(1)
        while True:
            try:
                sync_3xui_clients_and_traffic()
            except Exception as e:
                print(f"[3X-UI WORKER ERROR] {e}")
            time.sleep(20)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    print("[3X-UI WORKER] Started 3x-ui sync worker (20s interval)")
