#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for Solutions 1.2, 2.1, 2.3, 3.1, 3.2
Target components:
- 1.2: backend/routers/auth.py (Strict Registration OTP & Token Security)
- 2.1: backend/services/billing_service.py (YooKassa Reconciliation Worker Loop)
- 2.3: backend/routers/client.py, database.py (Reliable Direct APK Distribution)
- 3.1: backend/routers/profile.py (API Contract Standardization & Route Ordering)
- 3.2: backend/database.py, backend/routers/auth.py (Multi-Session & Device Identification)
"""

import os
import sys
import time
import json
import tempfile
import sqlite3
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI
from starlette.testclient import TestClient

import database
from core.dependencies import get_current_user, get_optional_current_user
from routers.auth import router as auth_router
from routers.client import router as client_router
from routers.profile import router as profile_router
from routers.public import router as public_router
from routers.admin import router as admin_router


class SolutionsAuditTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db.close()
        cls.db_path = cls.temp_db.name

        cls.orig_db_path = database.DB_PATH
        database.DB_PATH = cls.db_path
        os.environ["DB_PATH"] = cls.db_path

        database.init_db()

        cls.app = FastAPI()
        cls.app.include_router(auth_router)
        cls.app.include_router(client_router)
        cls.app.include_router(profile_router)
        cls.app.include_router(public_router)
        cls.app.include_router(admin_router)

        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = cls.orig_db_path
        if os.path.exists(cls.db_path):
            try:
                os.unlink(cls.db_path)
            except Exception:
                pass

    def setUp(self):
        with database.get_db() as conn:
            conn.execute("DELETE FROM user_sessions")
            conn.execute("DELETE FROM registration_tokens")
            conn.execute("DELETE FROM email_otps")
            conn.execute("DELETE FROM user_devices")
            conn.execute("DELETE FROM tokens")
            conn.execute("DELETE FROM payments")
            conn.execute("DELETE FROM users WHERE id >= 800")

            # Setup test user for profile routes
            conn.execute(
                "INSERT INTO users (id, email, password_hash, nickname, user_code, referral_code, balance, created_at) "
                "VALUES (888, 'audit_user@tabisvpn.site', 'hash888', 'audit_user', 'code888', 'ref888', 500.0, '2026-09-21 00:00:00')"
            )
            conn.commit()

        # Override dependencies for authenticated profile endpoints
        test_user = {
            "id": 888,
            "email": "audit_user@tabisvpn.site",
            "nickname": "audit_user",
            "is_admin": 1
        }
        self.app.dependency_overrides[get_current_user] = lambda: test_user
        self.app.dependency_overrides[get_optional_current_user] = lambda: test_user

    def tearDown(self):
        self.app.dependency_overrides.clear()

    # -------------------------------------------------------------
    # 1.2: Strict Registration OTP & Token Security Tests
    # -------------------------------------------------------------
    def test_1_2_registration_token_validation(self):
        """Verify auth_register_complete enforces strict reg_token validation and single-use."""
        # 1. Direct register complete without token should be rejected (HTTP 400)
        resp = self.client.post("/api/v1/auth/register/complete", json={
            "email": "newuser@tabisvpn.site",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "nickname": "Newbie",
            "reg_token": ""
        })
        self.assertEqual(resp.status_code, 400)

        # 2. Complete with non-existent token should be rejected (HTTP 400)
        resp = self.client.post("/api/v1/auth/register/complete", json={
            "email": "newuser@tabisvpn.site",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "nickname": "Newbie",
            "reg_token": "reg_fake_token_12345"
        })
        self.assertEqual(resp.status_code, 400)

        # 3. Insert valid registration token in DB (REAL timestamp)
        valid_token = "reg_secure_token_abc123456789"
        with database.get_db() as conn:
            conn.execute(
                "INSERT INTO registration_tokens (token, email, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (valid_token, "newuser@tabisvpn.site", time.time() + 1800, time.time())
            )
            conn.commit()

        # 4. Successful registration completion with valid token
        resp = self.client.post("/api/v1/auth/register/complete", json={
            "email": "newuser@tabisvpn.site",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "nickname": "Newbie",
            "reg_token": valid_token,
            "device_id": "test_device_123",
            "platform": "android"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("token", data)
        self.assertEqual(data["user"]["email"], "newuser@tabisvpn.site")

        # 5. Token is strictly single-use: Repeating registration with same token MUST fail (HTTP 400)
        resp_repeat = self.client.post("/api/v1/auth/register/complete", json={
            "email": "newuser@tabisvpn.site",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "nickname": "Newbie",
            "reg_token": valid_token
        })
        self.assertEqual(resp_repeat.status_code, 400)

        # 6. Test expired token
        expired_token = "reg_expired_token_xyz987654321"
        with database.get_db() as conn:
            conn.execute(
                "INSERT INTO registration_tokens (token, email, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (expired_token, "expired@tabisvpn.site", time.time() - 300, time.time() - 1800)
            )
            conn.commit()

        resp_expired = self.client.post("/api/v1/auth/register/complete", json={
            "email": "expired@tabisvpn.site",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "nickname": "Expired",
            "reg_token": expired_token
        })
        self.assertEqual(resp_expired.status_code, 400)

    # -------------------------------------------------------------
    # 2.1: YooKassa Reconciliation Optimization Tests
    # -------------------------------------------------------------
    def test_2_1_yookassa_reconciliation_window_and_expiration(self):
        """Verify reconciler limits active check to 2 hours and expires abandoned payments (>24h)."""
        from services.billing_service import reconcile_yookassa_pending_payments

        # Insert 3 payments:
        # 1. Fresh pending (< 2h)
        # 2. Intermediate pending (between 2h and 24h)
        # 3. Abandoned pending (> 24h)
        with database.get_db() as conn:
            conn.execute(
                "INSERT INTO payments (id, payment_id, user_id, amount, status, created_at, updated_at) "
                "VALUES (101, 'yk_fresh', 888, 100, 'pending', datetime('now', '-30 minutes'), datetime('now', '-30 minutes'))"
            )
            conn.execute(
                "INSERT INTO payments (id, payment_id, user_id, amount, status, created_at, updated_at) "
                "VALUES (102, 'yk_mid', 888, 100, 'pending', datetime('now', '-5 hours'), datetime('now', '-5 hours'))"
            )
            conn.execute(
                "INSERT INTO payments (id, payment_id, user_id, amount, status, created_at, updated_at) "
                "VALUES (103, 'yk_abandoned', 888, 100, 'pending', datetime('now', '-30 hours'), datetime('now', '-30 hours'))"
            )
            conn.commit()

        class MockResp:
            def __init__(self, data):
                self.data = json.dumps(data).encode("utf-8")
            def read(self):
                return self.data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        with patch("services.billing_service.YOOKASSA_SHOP_ID", "mock_shop"), \
             patch("services.billing_service.YOOKASSA_SECRET_KEY", "mock_sec"), \
             patch("urllib.request.urlopen") as mock_url:

            mock_url.return_value = MockResp({"status": "pending"})

            checked_count = reconcile_yookassa_pending_payments(max_batch=20)

            # Reconciler should only actively query YooKassa for fresh payment (<2h)
            self.assertEqual(checked_count, 1)
            self.assertEqual(mock_url.call_count, 1)

        # Verify DB states:
        with database.get_db() as conn:
            p_fresh = conn.execute("SELECT status FROM payments WHERE payment_id = 'yk_fresh'").fetchone()
            self.assertEqual(p_fresh["status"], "pending")

            p_mid = conn.execute("SELECT status FROM payments WHERE payment_id = 'yk_mid'").fetchone()
            self.assertEqual(p_mid["status"], "pending")

            p_abandoned = conn.execute("SELECT status FROM payments WHERE payment_id = 'yk_abandoned'").fetchone()
            self.assertEqual(p_abandoned["status"], "canceled")

    # -------------------------------------------------------------
    # 2.3: Reliable Direct APK Distribution Tests
    # -------------------------------------------------------------
    def test_2_3_app_download_and_version(self):
        """Verify /api/v1/app/download redirects directly to VPS Nginx downloads and version matches."""
        # 1. Test /api/v1/app/download endpoint (redirects to /downloads/TabisVPN.apk)
        resp = self.client.get("/api/v1/app/download", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        location = resp.headers.get("location", "")
        self.assertTrue(
            location.startswith("https://tabisvpn.site/downloads/TabisVPN.apk") or
            location.startswith("/downloads/TabisVPN.apk")
        )
        self.assertNotIn("media.githubusercontent.com", location)

        # 2. Test /api/v1/app/version endpoint
        resp_ver = self.client.get("/api/v1/app/version")
        self.assertEqual(resp_ver.status_code, 200)
        ver_data = resp_ver.json()
        self.assertIn("download_url", ver_data)
        self.assertEqual(ver_data["download_url"], "https://tabisvpn.site/downloads/TabisVPN.apk")

    def test_vless_reality_subscription_and_uri(self):
        """Verify iOS gets VLESS Reality in subscription and dedicated endpoint."""
        import base64
        token = "TABIS-VLES-TEST"
        with database.get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO tokens (token, is_active, label) VALUES (?, 1, 'iOS Test')", (token,))
            conn.commit()

        # 1. Test /api/v1/client/vless-uri
        resp = self.client.get(f"/api/v1/client/vless-uri?token={token}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        vless_uri = data["vless_uri"]
        self.assertTrue(vless_uri.startswith("vless://"))
        import config
        self.assertIn(f"{config.REALITY_SERVER}:{config.REALITY_PORT}", vless_uri)
        self.assertIn("sni=gateway.icloud.com", vless_uri)

        # 2. Test /api/v1/sub includes both VLESS and Hysteria 2
        sub_resp = self.client.get(f"/api/v1/sub?token={token}")
        self.assertEqual(sub_resp.status_code, 200)
        raw_sub = base64.b64decode(sub_resp.content.decode('utf-8')).decode('utf-8')
        self.assertIn("vless://", raw_sub)
        self.assertIn("hy2://", raw_sub)

    # -------------------------------------------------------------
    # 3.1: API Contract Standardization & Route Ordering Tests
    # -------------------------------------------------------------
    def test_3_1_route_ordering_and_aliases(self):
        """Verify static routes and aliases do not collide or produce HTTP 405 Method Not Allowed."""
        # 1. Test POST /api/v1/profile/devices (canonical)
        resp_add_canonical = self.client.post("/api/v1/profile/devices", json={
            "device_name": "Pixel 7 Pro",
            "tariff_plan": "base"
        })
        self.assertEqual(resp_add_canonical.status_code, 200)
        data = resp_add_canonical.json()
        self.assertEqual(data.get("status"), "ok")
        dev_id = data["device"]["id"]

        # 2. Test POST /api/v1/profile/devices/add (alias) - MUST NOT return 405
        resp_add_alias = self.client.post("/api/v1/profile/devices/add", json={
            "device_name": "Pixel Tablet",
            "tariff_plan": "base"
        })
        self.assertEqual(resp_add_alias.status_code, 200)
        self.assertEqual(resp_add_alias.json().get("status"), "ok")
        alias_dev_id = resp_add_alias.json()["device"]["id"]

        # 3. Test POST /api/v1/profile/devices/limit - MUST NOT return 405 (no collision with {device_id})
        resp_limit = self.client.post("/api/v1/profile/devices/limit", json={"device_limit": 5})
        self.assertEqual(resp_limit.status_code, 200)
        self.assertEqual(resp_limit.json().get("status"), "ok")

        # 4. Test POST /api/v1/profile/devices/{device_id}/renew (canonical)
        resp_renew = self.client.post(f"/api/v1/profile/devices/{dev_id}/renew")
        self.assertEqual(resp_renew.status_code, 200)
        self.assertEqual(resp_renew.json().get("status"), "ok")

        # 5. Test POST /api/v1/profile/devices/{device_id}/activate (alias)
        resp_activate = self.client.post(f"/api/v1/profile/devices/{dev_id}/activate")
        self.assertEqual(resp_activate.status_code, 200)
        self.assertEqual(resp_activate.json().get("status"), "ok")

        # 6. Test DELETE /api/v1/profile/devices/{device_id} (canonical)
        resp_del_canonical = self.client.delete(f"/api/v1/profile/devices/{dev_id}")
        self.assertEqual(resp_del_canonical.status_code, 200)
        self.assertEqual(resp_del_canonical.json().get("status"), "ok")

        # 7. Test POST /api/v1/profile/devices/{device_id}/delete (alias)
        resp_del_alias = self.client.post(f"/api/v1/profile/devices/{alias_dev_id}/delete")
        self.assertEqual(resp_del_alias.status_code, 200)
        self.assertEqual(resp_del_alias.json().get("status"), "ok")

        # 8. Test GET payment-status (canonical) vs payment/check (alias)
        resp_pay_canonical = self.client.get("/api/v1/profile/payment-status")
        self.assertEqual(resp_pay_canonical.status_code, 200)
        resp_pay_alias = self.client.get("/api/v1/profile/payment/check")
        self.assertEqual(resp_pay_alias.status_code, 200)
        self.assertEqual(resp_pay_canonical.json(), resp_pay_alias.json())

        # 9. Test GET support/messages (canonical) vs support/history (alias)
        resp_supp_canonical = self.client.get("/api/v1/support/messages?session_token=test_session_123")
        self.assertEqual(resp_supp_canonical.status_code, 200)
        resp_supp_alias = self.client.get("/api/v1/support/history?session_token=test_session_123")
        self.assertEqual(resp_supp_alias.status_code, 200)
        self.assertEqual(resp_supp_canonical.json(), resp_supp_alias.json())

    # -------------------------------------------------------------
    # 3.2: Robust Multi-Session & Device Identification Tests
    # -------------------------------------------------------------
    def test_3_2_multi_session_and_device_identification(self):
        """Verify Android session replacement tracks device_id without invalidating web sessions."""
        from core.security import hash_user_password
        pwd = "SecretPassword123!"
        with database.get_db() as conn:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, nickname, user_code, referral_code, balance, created_at) "
                "VALUES (889, 'multisession@tabisvpn.site', ?, 'multi', 'code889', 'ref889', 100.0, '2026-09-21 00:00:00')",
                (hash_user_password(pwd),)
            )
            conn.commit()

        # 1. Login from Web browser (platform='web', device_id='')
        resp_web = self.client.post("/api/v1/auth/login", json={
            "email": "multisession@tabisvpn.site",
            "password": pwd,
            "platform": "web",
            "device_id": ""
        }, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        self.assertEqual(resp_web.status_code, 200)
        web_token = resp_web.json()["token"]

        # 2. Login from Android Device A
        resp_android_a = self.client.post("/api/v1/auth/login", json={
            "email": "multisession@tabisvpn.site",
            "password": pwd,
            "platform": "android",
            "device_id": "device_android_A"
        }, headers={"User-Agent": "TabisVPN-Android/2.5.1 (Linux; Android 14)"})
        self.assertEqual(resp_android_a.status_code, 200)
        android_a_token = resp_android_a.json()["token"]

        # Verify both sessions are currently in DB
        with database.get_db() as conn:
            s_web = conn.execute("SELECT platform, device_id FROM user_sessions WHERE token = ?", (web_token,)).fetchone()
            s_a = conn.execute("SELECT platform, device_id FROM user_sessions WHERE token = ?", (android_a_token,)).fetchone()
            self.assertIsNotNone(s_web)
            self.assertEqual(s_web["platform"], "web")
            self.assertIsNotNone(s_a)
            self.assertEqual(s_a["platform"], "android")
            self.assertEqual(s_a["device_id"], "device_android_A")

        # 3. Login from Android Device B (new device!)
        resp_android_b = self.client.post("/api/v1/auth/login", json={
            "email": "multisession@tabisvpn.site",
            "password": pwd,
            "platform": "android",
            "device_id": "device_android_B"
        }, headers={"User-Agent": "TabisVPN-Android/2.5.1 (Linux; Android 14)"})
        self.assertEqual(resp_android_b.status_code, 200)
        android_b_token = resp_android_b.json()["token"]

        # Verify session states in DB:
        with database.get_db() as conn:
            s_web = conn.execute("SELECT * FROM user_sessions WHERE token = ?", (web_token,)).fetchone()
            s_a = conn.execute("SELECT * FROM user_sessions WHERE token = ?", (android_a_token,)).fetchone()
            s_b = conn.execute("SELECT platform, device_id FROM user_sessions WHERE token = ?", (android_b_token,)).fetchone()

            # Web session MUST remain valid and present!
            self.assertIsNotNone(s_web)

            # Old Android Device A session MUST be deleted/invalidated
            self.assertIsNone(s_a)

            # New Android Device B session MUST be present
            self.assertIsNotNone(s_b)
            self.assertEqual(s_b["device_id"], "device_android_B")

        # 4. Re-login from same Android Device B -> should NOT invalidate Device B's new login
        resp_android_b2 = self.client.post("/api/v1/auth/login", json={
            "email": "multisession@tabisvpn.site",
            "password": pwd,
            "platform": "android",
            "device_id": "device_android_B"
        }, headers={"User-Agent": "TabisVPN-Android/2.5.1 (Linux; Android 14)"})
        self.assertEqual(resp_android_b2.status_code, 200)
        android_b2_token = resp_android_b2.json()["token"]

        with database.get_db() as conn:
            s_b2 = conn.execute("SELECT * FROM user_sessions WHERE token = ?", (android_b2_token,)).fetchone()
            self.assertIsNotNone(s_b2)


if __name__ == "__main__":
    unittest.main()
