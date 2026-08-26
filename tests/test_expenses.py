import unittest
import tempfile
import os
from pathlib import Path
from app import create_app
from app.config import Config
from app.database.db import get_db, seed_demo_data


class TestExpenses(unittest.TestCase):

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

    def test_expense_crud(self):
        # Create expense
        res = self.client.post("/expenses/new", data={
            "date": "2026-08-26",
            "description": "Figma Professional Subscription",
            "merchant": "Figma Inc",
            "category": "Software",
            "amount": "1500.00",
            "currency": "INR",
            "payment_method": "Credit Card",
            "notes": "Design tool licenses"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            db = get_db()
            exp = db.execute("SELECT * FROM expenses WHERE merchant = 'Figma Inc'").fetchone()
            self.assertIsNotNone(exp)
            self.assertEqual(exp["amount"], 1500.0)
            self.assertEqual(exp["category"], "Software")

    def test_expense_export_csv(self):
        with self.app.app_context():
            seed_demo_data()

        res = self.client.get("/expenses/export.csv")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Adobe Systems", res.get_data(as_text=True))
        self.assertIn("Software", res.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
