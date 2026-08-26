import math
from typing import List, Dict, Any, Tuple
from app.config import Config


def calculate_line_item(hours: float, hourly_rate: float) -> float:
    """Calculates single line item total: hours * hourly_rate rounded to 2 decimal places."""
    try:
        hrs = max(0.0, float(hours))
        rate = max(0.0, float(hourly_rate))
        return round(hrs * rate, 2)
    except (ValueError, TypeError):
        return 0.0


def calculate_invoice_totals(
    items: List[Dict[str, Any]],
    discount_percent: float = 0.0,
    tax_percent: float = 0.0
) -> Dict[str, float]:
    """
    Deterministically computes subtotal, discount, taxable amount, tax, and grand total.
    Formula:
    1.Line Amount = hours * rate
    2.Subtotal = sum(Line Amounts)
    3.Discount Amount = Subtotal * (Discount Percent / 100.0)
    4.Taxable Amount = Subtotal - Discount Amount
    5.Tax Amount = Taxable Amount * (Tax Percent / 100.0)
    6.Grand Total = Taxable Amount + Tax Amount
    """
    subtotal = 0.0
    processed_items = []
    for item in items:
        hours = float(item.get("hours", 0.0) or 0.0)
        rate = float(item.get("hourly_rate", 0.0) or 0.0)
        amount = calculate_line_item(hours, rate)
        subtotal += amount
        processed_items.append({
            "description": str(item.get("description", "")).strip(),
            "hours": hours,
            "hourly_rate": rate,
            "amount": amount
        })
    subtotal = round(subtotal, 2)
    disc_pct = max(0.0, min(100.0, float(discount_percent or 0.0)))
    tax_pct = max(0.0, min(100.0, float(tax_percent or 0.0)))
    discount_amount = round(subtotal * (disc_pct / 100.0), 2)
    taxable_amount = max(0.0, round(subtotal - discount_amount, 2))
    tax_amount = round(taxable_amount * (tax_pct / 100.0), 2)
    grand_total = round(taxable_amount + tax_amount, 2)
    return {
        "subtotal": subtotal,
        "discount_percent": disc_pct,
        "discount_amount": discount_amount,
        "taxable_amount": taxable_amount,
        "tax_percent": tax_pct,
        "tax_amount": tax_amount,
        "total": grand_total,
        "processed_items": processed_items
    }


def format_currency(amount: float, currency_code: str = "INR",
                    include_symbol: bool = True) -> str:
    """
    Formats amounts cleanly.
    Supports Indian Lakh/Crore system for INR or standard Western thousands grouping.
    """
    try:
        amt = float(amount or 0.0)
    except (ValueError, TypeError):
        amt = 0.0
    curr_info = Config.SUPPORTED_CURRENCIES.get(
        currency_code.upper(), {"symbol": "₹", "name": "INR"})
    symbol = curr_info["symbol"]if include_symbol else ""
    is_negative = amt < 0
    amt = abs(amt)
    if currency_code.upper() == "INR":
        parts = f"{amt:.2f}".split(".")
        integer_part = parts[0]
        decimal_part = parts[1]
        if len(integer_part) > 3:
            last_three = integer_part[-3:]
            remaining = integer_part[:-3]
            chunks = []
            while len(remaining) > 2:
                chunks.insert(0, remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                chunks.insert(0, remaining)
            formatted_int = ",".join(chunks) + "," + last_three
        else:
            formatted_int = integer_part
        formatted_num = f"{formatted_int}.{decimal_part}"
    else:
        formatted_num = f"{amt:,.2f}"
    if is_negative:
        return f"-{symbol}{formatted_num}"if include_symbol else f"-{formatted_num}"
    return f"{symbol}{formatted_num}"if include_symbol else formatted_num


def calculate_net_income(total_paid_revenue: float,
                         total_expenses: float) -> float:
    """
    Net Income = Total Paid Revenue - Total Expenses
    Deterministic and transparent.
    """
    paid = float(total_paid_revenue or 0.0)
    expenses = float(total_expenses or 0.0)
    return round(paid - expenses, 2)
