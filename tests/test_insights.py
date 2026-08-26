import unittest
import tempfile
import os
from pathlib import Path
from app import create_app
from app.config import Config
from app.database.db import seed_demo_data
from app.services.insight_service import generate_business_insights


class TestInsights(unittest.TestCase):

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        class TestConfig(Config):
            TESTING = True
            DATABASE_PATH = Path(self.db_path)
            
        self.app = create_app(TestConfig)

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_rule_based_insights_generation(self):
        with self.app.app_context():
            seed_demo_data()
            insights = generate_business_insights()

            # Should generate structured insights
            self.assertGreater(len(insights), 0)
            
            types = [ins["type"] for ins in insights]
            # Check presence of key categories
            self.assertTrue(any(t in types for t in ["PAYMENT", "REVENUE", "EXPENSE", "PRICING", "CLIENT"]))

            # Inspect structure
            for ins in insights:
                self.assertIn("type", ins)
                self.assertIn("severity", ins)
                self.assertIn("title", ins)
                self.assertIn("message", ins)


if __name__ == "__main__":
    unittest.main()
