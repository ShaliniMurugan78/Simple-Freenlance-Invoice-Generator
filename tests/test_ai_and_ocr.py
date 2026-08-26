import unittest
from app.services.ai_service import generate_invoice_description, get_fallback_description


class TestAIAssistant(unittest.TestCase):

    def test_ai_description_fallback_engine(self):
        res = generate_invoice_description("Website Development", tone="Professional")
        self.assertTrue(res["success"])
        self.assertIn("web", res["description"].lower())

        res_simple = generate_invoice_description("UI/UX Design", tone="Simple")
        self.assertTrue(res_simple["success"])
        self.assertTrue(len(res_simple["description"]) > 10)

    def test_ai_tones(self):
        res_detailed = generate_invoice_description("Data Science Pipeline", tone="Detailed")
        self.assertTrue(res_detailed["success"])
        self.assertTrue(len(res_detailed["description"]) > 20)


if __name__ == "__main__":
    unittest.main()
