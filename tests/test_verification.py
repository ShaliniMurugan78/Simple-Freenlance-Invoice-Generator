import unittest
import tempfile
import os
from pathlib import Path
from app import create_app
from app.config import Config
from app.database.db import seed_demo_data
from app.services.invoice_service import calculate_document_hash
from app.services.qr_service import generate_verification_token, generate_invoice_qr_code, generate_payment_qr_code


class TestVerification(unittest.TestCase):

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        class TestConfig(Config):
            TESTING = True
            DATABASE_PATH = Path(self.db_path)
            
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_token_and_qr_generation(self):
        token = generate_verification_token()
        self.assertEqual(len(token), 32)

        qr_data_uri = generate_invoice_qr_code("INV-001", token, "https://myfreelance.app")
        self.assertTrue(qr_data_uri.startswith("data:image/png;base64,"))

    def test_upi_payment_qr_generation(self):
        payment_qr = generate_payment_qr_code(
            upi_id="alexmorgan@okhdfcbank",
            payee_name="Morgan Creative Labs",
            amount=147500.0,
            currency="INR",
            invoice_number="INV-001"
        )
        self.assertTrue(payment_qr.startswith("data:image/png;base64,"))

    def test_document_hash_consistency(self):
        h1 = calculate_document_hash("INV-001", 1, 15000.0, "2026-08-01")
        h2 = calculate_document_hash("INV-001", 1, 15000.0, "2026-08-01")
        self.assertEqual(h1, h2)

        # Altered total creates distinct hash
        h3 = calculate_document_hash("INV-001", 1, 15001.0, "2026-08-01")
        self.assertNotEqual(h1, h3)

    def test_public_verification_endpoint(self):
        with self.app.app_context():
            seed_demo_data()

        # Valid verification access
        # Retrieve token of INV-001
        with self.app.app_context():
            from app.database.db import get_db
            inv = get_db().execute("SELECT * FROM invoices WHERE invoice_number = 'INV-001'").fetchone()
            token = inv["verification_token"]

        res = self.client.get(f"/verify/INV-001/{token}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("AUTHENTIC INVOICE RECORD", res.get_data(as_text=True))
        self.assertIn("INV-001", res.get_data(as_text=True))

        # Invalid verification token
        res_invalid = self.client.get("/verify/INV-001/invalidtoken123")
        self.assertEqual(res_invalid.status_code, 404)
        self.assertIn("Invalid Verification Link", res_invalid.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
