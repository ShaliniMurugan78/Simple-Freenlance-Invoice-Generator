import os
import unittest
import tempfile
from pathlib import Path
from werkzeug.security import generate_password_hash
from app import create_app
from app.config import Config
from app.database.db import get_db, seed_demo_data


class TestAuth(unittest.TestCase):

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        class TestConfig(Config):
            TESTING = False  # To test real before_request auth redirect
            DATABASE_PATH = Path(self.db_path)
            
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            db = get_db()
            db.execute("INSERT OR REPLACE INTO users (id, email, password_hash, full_name, role) VALUES (1, 'test@example.com', ?, 'Test User', 'admin')", (generate_password_hash("password123"),))
            db.commit()

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_unauthenticated_redirect(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_valid_login(self):
        response = self.client.post("/login", data={
            "email": "test@example.com",
            "password": "password123"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Executive Command Center", response.data)

    def test_invalid_login(self):
        response = self.client.post("/login", data={
            "email": "test@example.com",
            "password": "wrongpassword"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid email address or password", response.data)

    def test_logout(self):
        # Login first
        self.client.post("/login", data={
            "email": "test@example.com",
            "password": "password123"
        })
        # Logout
        response = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sign In to Your Workspace", response.data)

    def test_register(self):
        response = self.client.post("/register", data={
            "full_name": "New Freelancer",
            "business_name": "Freelancer Studio",
            "email": "newuser@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Executive Command Center", response.data)


if __name__ == "__main__":
    unittest.main()
