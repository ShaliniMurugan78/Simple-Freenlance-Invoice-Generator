import unittest
from app.services.calculation_service import (
    calculate_line_item,
    calculate_invoice_totals,
    format_currency,
    calculate_net_income
)


class TestCalculationService(unittest.TestCase):

    def test_line_item_math(self):
        # 10 hours * 500 = 5000
        self.assertEqual(calculate_line_item(10, 500), 5000.0)
        # Fractional hours
        self.assertEqual(calculate_line_item(2.5, 1200), 3000.0)
        # 0 rate or negative check
        self.assertEqual(calculate_line_item(-5, 500), 0.0)

    def test_invoice_totals_workflow(self):
        """
        Prompt explicit example:
        Hours = 10, Rate = 500 -> Subtotal = 5,000
        Discount = 10% -> Discount Amount = 500
        Taxable Amount = 4,500
        Tax = 18% -> Tax Amount = 810
        Grand Total = 5,310
        """
        items = [{"hours": 10, "hourly_rate": 500, "description": "Backend API"}]
        res = calculate_invoice_totals(items, discount_percent=10.0, tax_percent=18.0)

        self.assertEqual(res["subtotal"], 5000.0)
        self.assertEqual(res["discount_percent"], 10.0)
        self.assertEqual(res["discount_amount"], 500.0)
        self.assertEqual(res["taxable_amount"], 4500.0)
        self.assertEqual(res["tax_percent"], 18.0)
        self.assertEqual(res["tax_amount"], 810.0)
        self.assertEqual(res["total"], 5310.0)

    def test_multi_item_totals(self):
        items = [
            {"hours": 5, "hourly_rate": 1000, "description": "Design"}, # 5000
            {"hours": 10, "hourly_rate": 1500, "description": "Dev"}     # 15000
        ]
        res = calculate_invoice_totals(items, discount_percent=0.0, tax_percent=18.0)
        self.assertEqual(res["subtotal"], 20000.0)
        self.assertEqual(res["discount_amount"], 0.0)
        self.assertEqual(res["tax_amount"], 3600.0)
        self.assertEqual(res["total"], 23600.0)

    def test_currency_formatting(self):
        # INR formatting
        self.assertEqual(format_currency(250000, "INR"), "₹2,50,000.00")
        self.assertEqual(format_currency(1500, "INR"), "₹1,500.00")
        # USD formatting
        self.assertEqual(format_currency(12500.5, "USD"), "$12,500.50")
        # EUR formatting
        self.assertEqual(format_currency(499.99, "EUR"), "€499.99")
        # GBP formatting
        self.assertEqual(format_currency(1000, "GBP"), "£1,000.00")

    def test_net_income(self):
        # Net income must only use paid revenue - total expenses
        paid_revenue = 200000.0
        expenses = 40000.0
        self.assertEqual(calculate_net_income(paid_revenue, expenses), 160000.0)


if __name__ == "__main__":
    unittest.main()
