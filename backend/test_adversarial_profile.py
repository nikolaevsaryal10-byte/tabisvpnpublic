#!/usr/bin/env python3
"""
Adversarial Test Suite for TabisVPN Profile Webhook & Fiscal Receipt Generation
Target: backend/routers/profile.py

Covers:
1. IP Spoofing & Header Injection
2. Fake YooKassa IP Payloads & Verification Bypass
3. Amount Rounding & Currency Mismatch
4. Receipt Generation Edge Cases
"""

import os
import sys
import io
import json
import uuid
import tempfile
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import urllib.request

# Ensure backend directory is on sys.path
BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException
from starlette.testclient import TestClient
import database
from routers.profile import router as profile_router, is_yookassa_ip, extract_webhook_client_ip
from core.dependencies import get_current_user


class FakeUrllibResponse:
    """Mock HTTP response returned by urllib.request.urlopen."""
    def __init__(self, data: dict, status: int = 200):
        self._data = json.dumps(data).encode("utf-8")
        self.status = status

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class AdversarialWebhookAndFiscalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary SQLite database
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db.close()
        cls.db_path = cls.temp_db.name

        # Patch DB_PATH in database and config modules
        cls.original_db_path = database.DB_PATH
        database.DB_PATH = cls.db_path
        os.environ["DB_PATH"] = cls.db_path

        # Initialize schema
        database.init_db()

        # Build FastAPI test app
        cls.app = FastAPI()
        cls.app.include_router(profile_router)

        # Base TestClients
        cls.client_localhost = TestClient(cls.app, client=("127.0.0.1", 50000))
        cls.client_external = TestClient(cls.app, client=("203.0.113.195", 50000))
        cls.client_lan = TestClient(cls.app, client=("192.168.1.100", 50000))
        cls.client_ipv6_local = TestClient(cls.app, client=("::1", 50000))

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = cls.original_db_path
        if os.path.exists(cls.db_path):
            try:
                os.unlink(cls.db_path)
            except Exception:
                pass

    def setUp(self):
        # Clean users and payments before each test
        with database.get_db() as conn:
            conn.execute("DELETE FROM payments")
            conn.execute("DELETE FROM users WHERE id >= 900")
            # Insert standard test user
            conn.execute(
                "INSERT INTO users (id, email, nickname, user_code, referral_code, balance, created_at) "
                "VALUES (999, 'victim@tabisvpn.site', 'victim', 'code999', 'ref999', 100.0, '2026-09-21 00:00:00')"
            )
            conn.commit()

    def get_user_balance(self, user_id=999) -> float:
        with database.get_db() as conn:
            row = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
            return float(row["balance"]) if row else 0.0

    def insert_test_payment(self, payment_id: str, amount: float, status="pending", user_id=999):
        with database.get_db() as conn:
            conn.execute(
                "INSERT INTO payments (payment_id, user_id, amount, status, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'Test payment', '2026-09-21 00:00:00', '2026-09-21 00:00:00')",
                (payment_id, user_id, amount, status)
            )
            conn.commit()

    def get_payment_record(self, payment_id: str):
        with database.get_db() as conn:
            return conn.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()

    # =========================================================================
    # 1. IP SPOOFING & HEADER INJECTION TESTS
    # =========================================================================

    def test_ip_spoofing_direct_external_ip_rejected(self):
        """Direct connection from external IP without headers is rejected with 403."""
        payload = {"event": "payment.succeeded", "object": {"id": "pay-123"}}
        resp = self.client_external.post("/api/v1/payments/yookassa-webhook", json=payload)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Forbidden", resp.json()["detail"])

    def test_ip_spoofing_external_caller_spoofing_x_real_ip(self):
        """External attacker sending X-Real-IP with YooKassa IP must be rejected with 403."""
        payload = {"event": "payment.succeeded", "object": {"id": "pay-123"}}
        headers = {"X-Real-IP": "185.71.76.10"}
        resp = self.client_external.post("/api/v1/payments/yookassa-webhook", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Untrusted source IP", resp.json()["detail"])

    def test_ip_spoofing_external_caller_spoofing_x_forwarded_for(self):
        """External attacker sending X-Forwarded-For with YooKassa IP must be rejected with 403."""
        payload = {"event": "payment.succeeded", "object": {"id": "pay-123"}}
        headers = {"X-Forwarded-For": "185.71.76.10"}
        resp = self.client_external.post("/api/v1/payments/yookassa-webhook", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Untrusted source IP", resp.json()["detail"])

    def test_ip_spoofing_external_caller_spoofing_both_headers(self):
        """External attacker sending both X-Real-IP and X-Forwarded-For must be rejected with 403."""
        payload = {"event": "payment.succeeded", "object": {"id": "pay-123"}}
        headers = {
            "X-Real-IP": "77.75.153.20",
            "X-Forwarded-For": "77.75.153.20, 127.0.0.1"
        }
        resp = self.client_external.post("/api/v1/payments/yookassa-webhook", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 403)

    def test_ip_spoofing_lan_caller_spoofing_x_real_ip(self):
        """Private LAN caller (192.168.1.100, not 127.0.0.1) cannot spoof X-Real-IP."""
        payload = {"event": "payment.succeeded", "object": {"id": "pay-123"}}
        headers = {"X-Real-IP": "185.71.76.10"}
        resp = self.client_lan.post("/api/v1/payments/yookassa-webhook", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 403)

    def test_ip_spoofing_trusted_proxy_with_untrusted_client_ip(self):
        """Localhost proxy forwarding an untrusted client IP in X-Real-IP is rejected with 403."""
        payload = {"event": "payment.succeeded", "object": {"id": "pay-123"}}
        headers = {"X-Real-IP": "203.0.113.55"}
        resp = self.client_localhost.post("/api/v1/payments/yookassa-webhook", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 403)

    def test_ip_spoofing_trusted_proxy_with_chained_forwarded_for(self):
        """Localhost proxy with client IP as first hop in X-Forwarded-For is evaluated against first hop."""
        payload = {"event": "payment.succeeded", "object": {"id": "pay-123"}}
        # First hop is untrusted attacker
        headers = {"X-Forwarded-For": "203.0.113.55, 185.71.76.10"}
        resp = self.client_localhost.post("/api/v1/payments/yookassa-webhook", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 403)

    def test_ip_spoofing_trusted_proxy_with_malformed_ip_header(self):
        """Localhost proxy with non-IP string in X-Real-IP raises 403 (ValueError handled)."""
        payload = {"event": "payment.succeeded", "object": {"id": "pay-123"}}
        headers = {"X-Real-IP": "malicious_string; DROP TABLE users;"}
        resp = self.client_localhost.post("/api/v1/payments/yookassa-webhook", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 403)

    def test_ip_spoofing_trusted_proxy_with_empty_headers(self):
        """Localhost proxy with no forwarding headers falls back to 127.0.0.1 which is rejected with 403."""
        payload = {"event": "payment.succeeded", "object": {"id": "pay-123"}}
        resp = self.client_localhost.post("/api/v1/payments/yookassa-webhook", json=payload)
        self.assertEqual(resp.status_code, 403)

    def test_ip_whitelist_all_allowed_subnets(self):
        """Verify all official YooKassa subnets are accepted via trusted proxy."""
        test_ips = [
            "185.71.76.1",       # In 185.71.76.0/27
            "185.71.76.30",      # In 185.71.76.0/27
            "185.71.77.5",       # In 185.71.77.0/27
            "77.75.153.1",       # In 77.75.153.0/25
            "77.75.153.120",     # In 77.75.153.0/25
            "77.75.156.11",      # Single /32
            "77.75.156.35",      # Single /32
        ]
        for ip in test_ips:
            self.assertTrue(is_yookassa_ip(ip), f"IP {ip} should be recognized as YooKassa")

    def test_ip_whitelist_boundary_subnets_rejected(self):
        """Verify boundaries outside the official YooKassa subnets are rejected."""
        invalid_ips = [
            "185.71.76.32",      # Outside 185.71.76.0/27 (0-31)
            "185.71.77.32",      # Outside 185.71.77.0/27 (0-31)
            "77.75.153.128",     # Outside 77.75.153.0/25 (0-127)
            "77.75.156.10",      # Adjacent to 77.75.156.11/32
            "77.75.156.12",      # Adjacent to 77.75.156.11/32
            "77.75.156.34",      # Adjacent to 77.75.156.35/32
            "77.75.156.36",      # Adjacent to 77.75.156.35/32
            "198.51.100.78",     # Non-YooKassa host IP
            "127.0.0.1",        # Localhost
            "::1",               # IPv6 localhost
        ]
        for ip in invalid_ips:
            self.assertFalse(is_yookassa_ip(ip), f"IP {ip} must NOT be accepted as YooKassa")

    def test_ip_whitelist_ipv6_mapped_ipv4(self):
        """Verify IPv6-mapped IPv4 addresses (::ffff:185.71.76.10) are handled correctly."""
        self.assertTrue(is_yookassa_ip("::ffff:185.71.76.10"))
        self.assertFalse(is_yookassa_ip("::ffff:203.0.113.195"))

    # =========================================================================
    # 2. FAKE YOOKASSA IP PAYLOAD & FORGED PAYMENT TESTS
    # =========================================================================

    def test_fake_payload_malformed_json_body(self):
        """Webhook with malformed JSON body returns 400 Bad Request."""
        headers = {"X-Real-IP": "185.71.76.10", "Content-Type": "application/json"}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            content=b"{invalid_json: true,",
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid JSON body", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    def test_fake_payload_missing_payment_id(self):
        """Webhook missing payment_id in body returns 400."""
        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"status": "succeeded"}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Missing payment id", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    def test_fake_payload_nonexistent_payment_id_rejected(self):
        """Webhook from valid YooKassa IP with nonexistent payment_id returns 404 and NEVER credits."""
        headers = {"X-Real-IP": "185.71.76.10"}
        fake_id = f"fake-pay-{uuid.uuid4()}"
        payload = {
            "type": "notification",
            "event": "payment.succeeded",
            "object": {
                "id": fake_id,
                "status": "succeeded",
                "amount": {"value": "5000.00", "currency": "RUB"}
            }
        }
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Payment record not found in local database", resp.json()["detail"])
        # Balance must remain unchanged
        self.assertEqual(self.get_user_balance(999), 100.0)

    @patch("urllib.request.urlopen")
    def test_fake_payload_yookassa_api_returns_404(self, mock_urlopen):
        """Local record exists, but YooKassa REST API returns 404 -> 502 returned, balance untouched."""
        pay_id = "test-pay-api-404"
        self.insert_test_payment(pay_id, amount=300.0, status="pending")

        mock_error = urllib.error.HTTPError(
            url=f"https://api.yookassa.ru/v3/payments/{pay_id}",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(b'{"type": "error", "description": "Not found"}')
        )
        mock_urlopen.side_effect = mock_error

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(self.get_user_balance(999), 100.0)
        # Payment status in DB must still be pending
        rec = self.get_payment_record(pay_id)
        self.assertEqual(rec["status"], "pending")

    @patch("urllib.request.urlopen")
    def test_fake_payload_yookassa_api_returns_status_pending(self, mock_urlopen):
        """Local record exists, but YooKassa REST API returns status='pending' -> 400, balance untouched."""
        pay_id = "test-pay-api-pending"
        self.insert_test_payment(pay_id, amount=300.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "pending",
            "amount": {"value": "300.00", "currency": "RUB"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Payment status is not succeeded (pending)", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)
        rec = self.get_payment_record(pay_id)
        self.assertEqual(rec["status"], "pending")

    @patch("urllib.request.urlopen")
    def test_fake_payload_yookassa_api_returns_status_canceled(self, mock_urlopen):
        """Local record exists, but YooKassa REST API returns status='canceled' -> 400, balance untouched."""
        pay_id = "test-pay-api-canceled"
        self.insert_test_payment(pay_id, amount=300.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "canceled",
            "amount": {"value": "300.00", "currency": "RUB"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Payment status is not succeeded (canceled)", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    @patch("urllib.request.urlopen")
    def test_fake_payload_yookassa_api_network_timeout(self, mock_urlopen):
        """YooKassa REST API network timeout raises 502, balance untouched."""
        pay_id = "test-pay-api-timeout"
        self.insert_test_payment(pay_id, amount=500.0, status="pending")

        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 502)
        self.assertIn("Failed to communicate with YooKassa", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    @patch("urllib.request.urlopen")
    def test_fake_payload_forged_amount_attack(self, mock_urlopen):
        """Attacker pays 1 RUB on YooKassa for a 1000 RUB pending payment -> rejected (400), balance untouched."""
        pay_id = "test-pay-forged-amount"
        self.insert_test_payment(pay_id, amount=1000.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "succeeded",
            "amount": {"value": "1.00", "currency": "RUB"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Payment amount mismatch", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    @patch("urllib.request.urlopen")
    def test_valid_payload_and_valid_api_credits_balance_exactly_once(self, mock_urlopen):
        """Legitimate webhook with matching YooKassa REST API credits user balance."""
        pay_id = "test-pay-legitimate"
        self.insert_test_payment(pay_id, amount=500.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "succeeded",
            "amount": {"value": "500.00", "currency": "RUB"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})
        # 100.0 initial + 500.0 = 600.0
        self.assertEqual(self.get_user_balance(999), 600.0)
        rec = self.get_payment_record(pay_id)
        self.assertEqual(rec["status"], "succeeded")

    @patch("urllib.request.urlopen")
    def test_replay_attack_on_already_succeeded_payment(self, mock_urlopen):
        """Replay attack: Resending webhook for an already succeeded payment returns idempotent OK without double crediting."""
        pay_id = "test-pay-replay"
        self.insert_test_payment(pay_id, amount=200.0, status="succeeded")
        # Ensure user balance starts at 300.0
        with database.get_db() as conn:
            conn.execute("UPDATE users SET balance = 300.0 WHERE id = 999")
            conn.commit()

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["message"], "Payment already applied")
        # Balance must NOT be incremented!
        self.assertEqual(self.get_user_balance(999), 300.0)
        # Verify mock_urlopen was not even called
        mock_urlopen.assert_not_called()

    # =========================================================================
    # 3. AMOUNT ROUNDING & CURRENCY MISMATCH TESTS
    # =========================================================================

    @patch("urllib.request.urlopen")
    def test_currency_mismatch_usd_rejected(self, mock_urlopen):
        """Payment in USD is rejected with 400 Invalid payment currency, balance untouched."""
        pay_id = "test-pay-usd"
        self.insert_test_payment(pay_id, amount=100.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "succeeded",
            "amount": {"value": "100.00", "currency": "USD"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid payment currency: USD", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    @patch("urllib.request.urlopen")
    def test_currency_mismatch_eur_and_kzt_rejected(self, mock_urlopen):
        """Payments in EUR and KZT are rejected with 400, balance untouched."""
        for curr in ["EUR", "KZT", "", "USDT"]:
            pay_id = f"test-pay-{curr or 'empty'}"
            self.insert_test_payment(pay_id, amount=50.0, status="pending")

            gateway_resp = {
                "id": pay_id,
                "status": "succeeded",
                "amount": {"value": "50.00", "currency": curr}
            }
            mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

            headers = {"X-Real-IP": "185.71.76.10"}
            payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
            resp = self.client_localhost.post(
                "/api/v1/payments/yookassa-webhook",
                json=payload,
                headers=headers
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Invalid payment currency", resp.json()["detail"])
            self.assertEqual(self.get_user_balance(999), 100.0)

    @patch("urllib.request.urlopen")
    def test_amount_rounding_exact_match(self, mock_urlopen):
        """Expected 100.0, YooKassa reports '100.00' -> exact match passes."""
        pay_id = "test-pay-exact"
        self.insert_test_payment(pay_id, amount=100.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "succeeded",
            "amount": {"value": "100.00", "currency": "RUB"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.get_user_balance(999), 200.0)

    @patch("urllib.request.urlopen")
    def test_different_amount_1_kopeck_difference_rejected(self, mock_urlopen):
        """Expected 100.0, YooKassa reports '100.01' (different amount) -> rejected with 400."""
        pay_id = "test-pay-diff-1-kopeck"
        self.insert_test_payment(pay_id, amount=100.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "succeeded",
            "amount": {"value": "100.01", "currency": "RUB"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Payment amount mismatch", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    @patch("urllib.request.urlopen")
    def test_amount_rounding_exceeding_0_01_tolerance_rejected(self, mock_urlopen):
        """Expected 100.0, YooKassa reports '100.02' (diff 0.02 > 0.01) -> rejected with 400."""
        pay_id = "test-pay-tolerance-fail-high"
        self.insert_test_payment(pay_id, amount=100.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "succeeded",
            "amount": {"value": "100.02", "currency": "RUB"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Payment amount mismatch", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    @patch("urllib.request.urlopen")
    def test_amount_rounding_below_0_01_tolerance_rejected(self, mock_urlopen):
        """Expected 100.0, YooKassa reports '99.98' (diff 0.02 > 0.01) -> rejected with 400."""
        pay_id = "test-pay-tolerance-fail-low"
        self.insert_test_payment(pay_id, amount=100.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "succeeded",
            "amount": {"value": "99.98", "currency": "RUB"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Payment amount mismatch", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    @patch("urllib.request.urlopen")
    def test_amount_malformed_string_rejected(self, mock_urlopen):
        """Malformed amount in YooKassa response (e.g. 'invalid_val') results in 400 rejection."""
        pay_id = "test-pay-malformed-val"
        self.insert_test_payment(pay_id, amount=100.0, status="pending")

        gateway_resp = {
            "id": pay_id,
            "status": "succeeded",
            "amount": {"value": "invalid_number", "currency": "RUB"}
        }
        mock_urlopen.return_value = FakeUrllibResponse(gateway_resp, status=200)

        headers = {"X-Real-IP": "185.71.76.10"}
        payload = {"event": "payment.succeeded", "object": {"id": pay_id}}
        resp = self.client_localhost.post(
            "/api/v1/payments/yookassa-webhook",
            json=payload,
            headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Payment amount mismatch", resp.json()["detail"])
        self.assertEqual(self.get_user_balance(999), 100.0)

    # =========================================================================
    # 4. RECEIPT GENERATION EDGE CASES
    # =========================================================================

    def _override_user_dependency(self, user_dict):
        self.app.dependency_overrides[get_current_user] = lambda: user_dict

    def _clear_user_dependency(self):
        self.app.dependency_overrides.pop(get_current_user, None)

    @patch("urllib.request.urlopen")
    def test_receipt_generation_boundary_amount_10_rub(self, mock_urlopen):
        """Top-up with 10.00 RUB creates valid receipt payload with 10.00 and vat_code=1."""
        test_user = {"id": 999, "email": "customer@tabisvpn.site"}
        self._override_user_dependency(test_user)
        try:
            mock_resp_data = {
                "id": "pay-receipt-10",
                "status": "pending",
                "confirmation": {"confirmation_url": "https://yookassa.ru/confirm/10"}
            }
            mock_urlopen.return_value = FakeUrllibResponse(mock_resp_data, status=200)

            resp = self.client_localhost.post("/api/v1/profile/top-up", json={"amount": 10})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["payment_id"], "pay-receipt-10")

            # Inspect intercepted outbound request to YooKassa
            self.assertEqual(mock_urlopen.call_count, 1)
            sent_req = mock_urlopen.call_args[0][0]
            sent_payload = json.loads(sent_req.data.decode("utf-8"))

            # Validate receipt structure per 54-FZ
            self.assertIn("receipt", sent_payload)
            receipt = sent_payload["receipt"]
            self.assertEqual(receipt["customer"]["email"], "customer@tabisvpn.site")
            self.assertEqual(len(receipt["items"]), 1)
            item = receipt["items"][0]
            self.assertEqual(item["amount"]["value"], "10.00")
            self.assertEqual(item["amount"]["currency"], "RUB")
            self.assertEqual(item["vat_code"], 1)
            self.assertEqual(item["quantity"], "1.00")
            self.assertEqual(item["payment_mode"], "full_prepayment")
            self.assertEqual(item["payment_subject"], "service")

            # Validate overall payment amount
            self.assertEqual(sent_payload["amount"]["value"], "10.00")
            self.assertEqual(sent_payload["amount"]["currency"], "RUB")
        finally:
            self._clear_user_dependency()

    @patch("urllib.request.urlopen")
    def test_receipt_generation_boundary_amount_min_1_rub(self, mock_urlopen):
        """Top-up with minimum valid amount 1 RUB creates receipt with value '1.00'."""
        test_user = {"id": 999, "email": "customer@tabisvpn.site"}
        self._override_user_dependency(test_user)
        try:
            mock_resp_data = {
                "id": "pay-receipt-min-1",
                "status": "pending",
                "confirmation": {"confirmation_url": "https://yookassa.ru/confirm/1"}
            }
            mock_urlopen.return_value = FakeUrllibResponse(mock_resp_data, status=200)

            resp = self.client_localhost.post("/api/v1/profile/top-up", json={"amount": 1})
            self.assertEqual(resp.status_code, 200)

            sent_req = mock_urlopen.call_args[0][0]
            sent_payload = json.loads(sent_req.data.decode("utf-8"))
            self.assertEqual(sent_payload["amount"]["value"], "1.00")
            self.assertEqual(sent_payload["receipt"]["items"][0]["amount"]["value"], "1.00")
            self.assertEqual(sent_payload["receipt"]["items"][0]["vat_code"], 1)
        finally:
            self._clear_user_dependency()

    @patch("urllib.request.urlopen")
    def test_receipt_generation_boundary_amount_max_30000_rub(self, mock_urlopen):
        """Top-up with maximum valid amount 30000 RUB creates receipt with value '30000.00'."""
        test_user = {"id": 999, "email": "customer@tabisvpn.site"}
        self._override_user_dependency(test_user)
        try:
            mock_resp_data = {
                "id": "pay-receipt-max-30000",
                "status": "pending",
                "confirmation": {"confirmation_url": "https://yookassa.ru/confirm/30000"}
            }
            mock_urlopen.return_value = FakeUrllibResponse(mock_resp_data, status=200)

            resp = self.client_localhost.post("/api/v1/profile/top-up", json={"amount": 30000})
            self.assertEqual(resp.status_code, 200)

            sent_req = mock_urlopen.call_args[0][0]
            sent_payload = json.loads(sent_req.data.decode("utf-8"))
            self.assertEqual(sent_payload["amount"]["value"], "30000.00")
            self.assertEqual(sent_payload["receipt"]["items"][0]["amount"]["value"], "30000.00")
            self.assertEqual(sent_payload["receipt"]["items"][0]["vat_code"], 1)
        finally:
            self._clear_user_dependency()

    def test_receipt_generation_boundary_amount_99999_rub_rejected(self):
        """Top-up with 99999.00 RUB exceeds limit (max 30,000) and is rejected with 400."""
        test_user = {"id": 999, "email": "customer@tabisvpn.site"}
        self._override_user_dependency(test_user)
        try:
            resp = self.client_localhost.post("/api/v1/profile/top-up", json={"amount": 99999})
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Сумма пополнения должна быть от 1 до 30 000 ₽", resp.json()["detail"])
        finally:
            self._clear_user_dependency()

    def test_receipt_generation_boundary_amount_zero_or_negative_rejected(self):
        """Top-up with 0 or negative amount is rejected with 400."""
        test_user = {"id": 999, "email": "customer@tabisvpn.site"}
        self._override_user_dependency(test_user)
        try:
            for bad_amt in [0, -1, -500]:
                resp = self.client_localhost.post("/api/v1/profile/top-up", json={"amount": bad_amt})
                self.assertEqual(resp.status_code, 400)
                self.assertIn("Сумма пополнения должна быть от 1 до 30 000 ₽", resp.json()["detail"])
        finally:
            self._clear_user_dependency()

    def test_receipt_generation_fractional_amount_rejected_by_schema(self):
        """Fractional ruble amount (e.g. 10.50) is rejected by Pydantic schema with 422."""
        test_user = {"id": 999, "email": "customer@tabisvpn.site"}
        self._override_user_dependency(test_user)
        try:
            resp = self.client_localhost.post("/api/v1/profile/top-up", json={"amount": 10.5})
            self.assertEqual(resp.status_code, 422)
        finally:
            self._clear_user_dependency()

    def test_receipt_generation_non_numeric_amount_rejected_by_schema(self):
        """Non-numeric or missing amount is rejected with 422."""
        test_user = {"id": 999, "email": "customer@tabisvpn.site"}
        self._override_user_dependency(test_user)
        try:
            resp1 = self.client_localhost.post("/api/v1/profile/top-up", json={"amount": "free"})
            self.assertEqual(resp1.status_code, 422)
            resp2 = self.client_localhost.post("/api/v1/profile/top-up", json={})
            self.assertEqual(resp2.status_code, 422)
        finally:
            self._clear_user_dependency()

    @patch("urllib.request.urlopen")
    def test_receipt_email_formatting_edge_cases(self, mock_urlopen):
        """Verify receipts with plus tags, dots, hyphens, and subdomains in email."""
        test_emails = [
            "user+tag@domain.co.uk",
            "first.last@service-sub.example.com",
            "12345@numbers.tabisvpn.site"
        ]
        for email in test_emails:
            mock_urlopen.reset_mock()
            test_user = {"id": 999, "email": email}
            self._override_user_dependency(test_user)
            try:
                mock_resp_data = {
                    "id": f"pay-email-{uuid.uuid4().hex[:6]}",
                    "status": "pending",
                    "confirmation": {"confirmation_url": "https://yookassa.ru/confirm"}
                }
                mock_urlopen.return_value = FakeUrllibResponse(mock_resp_data, status=200)

                resp = self.client_localhost.post("/api/v1/profile/top-up", json={"amount": 100})
                self.assertEqual(resp.status_code, 200)

                sent_req = mock_urlopen.call_args[0][0]
                sent_payload = json.loads(sent_req.data.decode("utf-8"))
                receipt = sent_payload["receipt"]
                self.assertEqual(receipt["customer"]["email"], email)
                self.assertIn(email, receipt["items"][0]["description"])
            finally:
                self._clear_user_dependency()

    @patch("urllib.request.urlopen")
    def test_receipt_description_length_within_yookassa_128_char_limit(self, mock_urlopen):
        """Verify description length stays <= 128 chars for realistic long emails."""
        # YooKassa imposes 128 characters max on items[].description
        long_email = "very_long_test_email_address_123456789@subdomain.example-company.org"  # 68 chars
        test_user = {"id": 999, "email": long_email}
        self._override_user_dependency(test_user)
        try:
            mock_resp_data = {
                "id": "pay-receipt-desc-len",
                "status": "pending",
                "confirmation": {"confirmation_url": "https://yookassa.ru/confirm"}
            }
            mock_urlopen.return_value = FakeUrllibResponse(mock_resp_data, status=200)

            resp = self.client_localhost.post("/api/v1/profile/top-up", json={"amount": 250})
            self.assertEqual(resp.status_code, 200)

            sent_req = mock_urlopen.call_args[0][0]
            sent_payload = json.loads(sent_req.data.decode("utf-8"))
            desc = sent_payload["receipt"]["items"][0]["description"]
            # Assert item description is <= 128 characters
            self.assertLessEqual(len(desc), 128, f"Description length ({len(desc)}) exceeds YooKassa 128 char limit!")
        finally:
            self._clear_user_dependency()


if __name__ == "__main__":
    unittest.main(verbosity=2)
