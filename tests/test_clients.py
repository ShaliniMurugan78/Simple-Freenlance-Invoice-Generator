import unittest
import tempfile
import os
from pathlib import Path
from app import create_app
from app.config import Config
from app.database.db import get_db, seed_demo_data


class TestClients(unittest.TestCase):

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

    def test_client_creation_and_view(self):
        res = self.client.post("/clients/new", data={
            "name": "Acme Ventures",
            "company_name": "Acme Ventures Global",
            "email": "finance@acme.com",
            "phone": "+1 800 555 1212",
            "address": "100 Innovation Way, Austin, TX",
            "tax_number": "US-EIN-123456",
            "notes": "Fast growing venture capital partner"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            db = get_db()
            c = db.execute("SELECT * FROM clients WHERE name = 'Acme Ventures'").fetchone()
            self.assertIsNotNone(c)
            self.assertEqual(c["email"], "finance@acme.com")

    def test_client_delete_protection_when_invoices_exist(self):
        with self.app.app_context():
            seed_demo_data()

        # Attempt to delete client 1 (ABC Technologies) which has invoices
        res = self.client.post("/clients/1/delete", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            db = get_db()
            c = db.execute("SELECT * FROM clients WHERE id = 1").fetchone()
            # Client must still exist due to invoice association protection
            self.assertIsNotNone(c)


if __name__ == "__main__":
    unittest.main()
