import unittest
import json
import hmac
import hashlib
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from app import create_app
from app.config import Config


class TestPaymentService(unittest.TestCase):

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()

        class TestConfig(Config):
            TESTING = True
            DATABASE_PATH = Path(self.db_path)
            RAZORPAY_KEY_ID = "rzp_test_dummykey"
            RAZORPAY_KEY_SECRET = "test_secret_xyz"
            RAZORPAY_WEBHOOK_SECRET = "webhook_secret_abc"

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_razorpay_configured_when_keys_present(self):
        with self.app.app_context():
            from app.services.payment_service import is_razorpay_configured
            self.assertTrue(is_razorpay_configured())

    def test_get_razorpay_key_id(self):
        with self.app.app_context():
            from app.services.payment_service import get_razorpay_key_id
            self.assertEqual(get_razorpay_key_id(), "rzp_test_dummykey")

    def test_payment_signature_verification_valid(self):
        """Valid HMAC signature should be accepted."""
        with self.app.app_context():
            from app.services.payment_service import verify_payment_signature
            order_id = "order_test_123"
            payment_id = "pay_test_456"
            key_secret = self.app.config["RAZORPAY_KEY_SECRET"]
            # Generate correct signature
            msg = f"{order_id}|{payment_id}".encode("utf-8")
            correct_sig = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            self.assertTrue(verify_payment_signature(order_id, payment_id, correct_sig))

    def test_payment_signature_verification_invalid(self):
        """Tampered / invalid signature should be rejected."""
        with self.app.app_context():
            from app.services.payment_service import verify_payment_signature
            result = verify_payment_signature("order_abc", "pay_abc", "tampered_signature_xyz")
            self.assertFalse(result)

    def test_webhook_signature_verification_valid(self):
        """Valid webhook HMAC signature should pass."""
        with self.app.app_context():
            from app.services.payment_service import verify_webhook_signature
            webhook_secret = self.app.config["RAZORPAY_WEBHOOK_SECRET"]
            raw_body = b'{"event": "payment.captured"}'
            correct_sig = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            self.assertTrue(verify_webhook_signature(raw_body, correct_sig))

    def test_webhook_signature_verification_invalid(self):
        """Tampered webhook signature should be rejected."""
        with self.app.app_context():
            from app.services.payment_service import verify_webhook_signature
            raw_body = b'{"event": "payment.captured"}'
            self.assertFalse(verify_webhook_signature(raw_body, "fakesig"))

    def test_webhook_endpoint_invalid_signature(self):
        """Webhook endpoint should reject requests with invalid signature."""
        res = self.client.post(
            "/verify/razorpay-webhook",
            data='{"event": "payment.captured"}',
            content_type="application/json",
            headers={"X-Razorpay-Signature": "badsignature"}
        )
        self.assertEqual(res.status_code, 400)

    @patch("app.services.payment_service.requests.post")
    def test_create_order_api_call(self, mock_post):
        """create_razorpay_order should call Razorpay API with correct paise amount."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "order_test_abc",
            "amount": 1500000,  # 15000 INR in paise
            "currency": "INR"
        }
        mock_post.return_value = mock_response

        with self.app.app_context():
            from app.services.payment_service import create_razorpay_order
            order = create_razorpay_order(1, "INV-001", 15000.0, "INR")
            self.assertEqual(order["id"], "order_test_abc")
            self.assertEqual(order["amount"], 1500000)
            # Verify API was called with paise amount
            call_args = mock_post.call_args
            self.assertEqual(call_args[1]["json"]["amount"], 1500000)
            self.assertEqual(call_args[1]["json"]["currency"], "INR")


if __name__ == "__main__":
    unittest.main()
