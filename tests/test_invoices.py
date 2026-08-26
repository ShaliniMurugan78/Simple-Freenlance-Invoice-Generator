import unittest
import tempfile
import os
from pathlib import Path
from app import create_app
from app.config import Config
from app.database.db import get_db, seed_demo_data
from app.services.invoice_service import generate_next_invoice_number, update_overdue_statuses, get_invoice_full_details


class TestInvoices(unittest.TestCase):

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

    def test_invoice_number_sequence(self):
        with self.app.app_context():
            # Initially no invoices
            self.assertEqual(generate_next_invoice_number(), "INV-001")
            
            # Seed demo data
            seed_demo_data()
            
            # After INV-001, INV-002, INV-003, INV-004
            next_num = generate_next_invoice_number()
            self.assertEqual(next_num, "INV-005")

    def test_overdue_status_detection(self):
        with self.app.app_context():
            seed_demo_data()
            db = get_db()
            
            # Manually insert a pending invoice with past due date
            db.execute("""
                INSERT INTO invoices (
                    invoice_number, client_id, invoice_date, due_date, currency,
                    subtotal, discount_percent, discount_amount, tax_percent, tax_amount,
                    total, status, template, verification_token
                ) VALUES ('INV-999', 1, '2026-01-01', '2026-01-15', 'INR', 1000, 0, 0, 0, 0, 1000, 'Pending', 'classic', 'token999')
            """)
            db.commit()

            # Run overdue status update
            update_overdue_statuses()
            
            inv = db.execute("SELECT status FROM invoices WHERE invoice_number = 'INV-999'").fetchone()
            self.assertEqual(inv["status"], "Overdue")

    def test_invoice_crud_via_http(self):
        with self.app.app_context():
            seed_demo_data()

        # Create new invoice
        res = self.client.post("/invoices/new", data={
            "invoice_number": "INV-101",
            "client_id": 1,
            "invoice_date": "2026-08-26",
            "due_date": "2026-09-10",
            "currency": "INR",
            "discount_percent": 0,
            "tax_percent": 18,
            "template": "classic",
            "item_description[]": ["Custom API Integration"],
            "item_hours[]": ["10"],
            "item_rate[]": ["2000"]
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify in database
        with self.app.app_context():
            inv = get_invoice_full_details(5)
            self.assertIsNotNone(inv)
            self.assertEqual(inv["invoice_number"], "INV-101")
            self.assertEqual(inv["subtotal"], 20000.0)
            self.assertEqual(inv["tax_amount"], 3600.0)
            self.assertEqual(inv["total"], 23600.0)


if __name__ == "__main__":
    unittest.main()
