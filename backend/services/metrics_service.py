import time
import json
import sys
import urllib.request
from datetime import datetime, date
from database import get_db

class SystemProbe:
    """Read Linux /proc files to obtain CPU, RAM, and Network deltas with microsecond precision."""
    def __init__(self):
        self._prev_cpu = self._read_cpu_raw()
        self._prev_net = self._read_net_raw()
        self._prev_time = time.time()

    def _read_cpu_raw(self):
        try:
            with open('/proc/stat', 'r') as f:
                for line in f:
                    if line.startswith('cpu '):
                        parts = [float(x) for x in line.split()[1:]]
                        idle = parts[3] + parts[4]  # idle + iowait
                        total = sum(parts)
                        return idle, total
        except Exception:
            pass
        return 0.0, 0.0

    def _read_net_raw(self):
        rx_total = 0
        tx_total = 0
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]
                for line in lines:
                    parts = line.split(':')
                    if len(parts) == 2:
                        iface = parts[0].strip()
                        if iface == 'lo':
                            continue
                        stats = parts[1].split()
                        rx_total += int(stats[0])
                        tx_total += int(stats[8])
        except Exception:
            pass
        return rx_total, tx_total

    def sample(self):
        now = time.time()
        dt = max(0.001, now - self._prev_time)
        self._prev_time = now

        # CPU %
        idle, total = self._read_cpu_raw()
        prev_idle, prev_total = self._prev_cpu
        self._prev_cpu = (idle, total)
        total_diff = total - prev_total
        idle_diff = idle - prev_idle
        cpu_percent = 0.0
        if total_diff > 0:
            cpu_percent = round(100.0 * (1.0 - (idle_diff / total_diff)), 2)
            cpu_percent = max(0.0, min(100.0, cpu_percent))

        # RAM
        ram_total_mb = 0.0
        ram_avail_mb = 0.0
        try:
            with open('/proc/meminfo', 'r') as f:
                mem = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = int(parts[1].split()[0])
                        mem[key] = val
                ram_total_mb = round(mem.get('MemTotal', 0) / 1024, 1)
                ram_avail_mb = round(mem.get('MemAvailable', mem.get('MemFree', 0)) / 1024, 1)
        except Exception:
            pass
        ram_used_mb = round(max(0.0, ram_total_mb - ram_avail_mb), 1)
        ram_percent = round((ram_used_mb / ram_total_mb * 100.0) if ram_total_mb > 0 else 0.0, 1)

        # Network speed (Mbps)
        rx, tx = self._read_net_raw()
        prev_rx, prev_tx = self._prev_net
        self._prev_net = (rx, tx)
        rx_diff = max(0, rx - prev_rx)
        tx_diff = max(0, tx - prev_tx)
        net_rx_mbps = round((rx_diff * 8.0) / (dt * 1_000_000.0), 3)
        net_tx_mbps = round((tx_diff * 8.0) / (dt * 1_000_000.0), 3)

        return {
            "timestamp": int(now),
            "cpu_percent": cpu_percent,
            "ram_used_mb": ram_used_mb,
            "ram_total_mb": ram_total_mb,
            "ram_percent": ram_percent,
            "net_rx_mbps": net_rx_mbps,
            "net_tx_mbps": net_tx_mbps,
            "net_rx_total_bytes": rx,
            "net_tx_total_bytes": tx,
        }

probe = SystemProbe()

def metrics_worker_loop():
    """Background thread collecting metrics every 60 seconds, keeping last 1440 points."""
    time.sleep(2)
    while True:
        try:
            sample_data = probe.sample()
            try:
                hy_req = urllib.request.Request("http://127.0.0.1:9999/traffic?clear=1")
                hy_req.add_header("Authorization", "TabisTrafficSecret2026!")
                with urllib.request.urlopen(hy_req, timeout=2) as hy_resp:
                    if hy_resp.status == 200:
                        traffic_map = json.loads(hy_resp.read().decode('utf-8'))
                        with get_db() as hy_conn:
                            for u_key, u_stats in traffic_map.items():
                                clean_k = str(u_key).strip().upper()
                                tx = int(u_stats.get("tx", 0))
                                rx = int(u_stats.get("rx", 0))
                                if tx > 0 or rx > 0:
                                    hy_conn.execute("""
                                        UPDATE tokens
                                        SET traffic_up = traffic_up + ?,
                                            traffic_down = traffic_down + ?,
                                            traffic_today_up = traffic_today_up + ?,
                                            traffic_today_down = traffic_today_down + ?
                                        WHERE UPPER(token) = ?
                                    """, (rx, tx, rx, tx, clean_k))
                            hy_conn.commit()
            except Exception:
                pass

            now_ts = sample_data["timestamp"]
            today_str = date.today().isoformat()
            cutoff_dt = datetime.utcfromtimestamp(now_ts - 300).strftime("%Y-%m-%d %H:%M:%S")

            with get_db() as conn:
                active_users = conn.execute(
                    "SELECT COUNT(*) FROM tokens WHERE is_active = 1 AND last_seen_at >= ?",
                    (cutoff_dt,)
                ).fetchone()[0]

                today_rx = conn.execute(
                    "SELECT SUM(traffic_today_down) FROM tokens WHERE last_reset_day = ?",
                    (today_str,)
                ).fetchone()[0] or 0

                today_tx = conn.execute(
                    "SELECT SUM(traffic_today_up) FROM tokens WHERE last_reset_day = ?",
                    (today_str,)
                ).fetchone()[0] or 0

                conn.execute("""
                    INSERT INTO server_metrics 
                    (timestamp, cpu_percent, ram_used_mb, ram_total_mb, ram_percent, 
                     net_rx_mbps, net_tx_mbps, traffic_today_rx, traffic_today_tx, active_users)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now_ts,
                    sample_data["cpu_percent"],
                    sample_data["ram_used_mb"],
                    sample_data["ram_total_mb"],
                    sample_data["ram_percent"],
                    sample_data["net_rx_mbps"],
                    sample_data["net_tx_mbps"],
                    today_rx,
                    today_tx,
                    active_users
                ))

                # Keep only last 1440 points (24 hours)
                conn.execute("""
                    DELETE FROM server_metrics 
                    WHERE id NOT IN (
                        SELECT id FROM server_metrics ORDER BY id DESC LIMIT 1440
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"[METRICS WORKER ERROR] {e}", file=sys.stderr)
        time.sleep(60)
