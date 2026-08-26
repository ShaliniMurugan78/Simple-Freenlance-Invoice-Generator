import hashlib
import re
import csv
import io
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from app.database.db import get_db


def calculate_document_hash(
    invoice_number: str,
    client_id: int,
    total: float,
    invoice_date: str
) -> str:
    """
    Computes a SHA-256 cryptographic hash of critical invoice parameters
    to serve as a verifiable document integrity indicator.
    """
    raw = f"{invoice_number}:{client_id}:{total:.2f}:{invoice_date}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_next_invoice_number() -> str:
    """
    Generates the next sequential invoice number (e.g.INV-001, INV-002).
    Inspects existing invoice numbers to safely find the maximum index and increments it.
    Works reliably even if earlier invoices have been deleted.
    """
    db = get_db()
    rows = db.execute("SELECT invoice_number FROM invoices").fetchall()
    max_num = 0
    pattern = re.compile(r"INV-(\d+)", re.IGNORECASE)
    for row in rows:
        match = pattern.match (row["invoice_number"])
        if match:
            try:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    next_num = max_num + 1
    return f"INV-{next_num:03d}"


def update_overdue_statuses():
    """
    Automatically checks and updates invoices whose due_date < current_date
    and status is currently 'Pending' to 'Overdue'.
    """
    db = get_db()
    today_str = date.today().isoformat()
    db.execute("""
        UPDATE invoices
        SET status = 'Overdue', updated_at = CURRENT_TIMESTAMP
        WHERE due_date < ? AND status = 'Pending'
    """, (today_str,))
    db.commit()


def get_invoice_full_details(invoice_id: int) -> Optional[Dict[str, Any]]:
    """Fetches invoice, associated client details, line items, and profile."""
    db = get_db()
    inv_row = db.execute("""
        SELECT i.*, c.name as client_name, c.company_name as client_company,
               c.email as client_email, c.phone as client_phone,
               c.address as client_address, c.tax_number as client_tax_number
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        WHERE i.id = ?
    """, (invoice_id,)).fetchone()
    if not inv_row:
        return None
    invoice = dict(inv_row)
    items = db.execute("""
        SELECT * FROM invoice_items
        WHERE invoice_id = ?
        ORDER BY sort_order ASC, id ASC
    """, (invoice_id,)).fetchall()
    items_list = [dict(it)for it in items]
    invoice["items"] = items_list
    invoice["line_items"] = items_list
    profile = db.execute(
        "SELECT * FROM freelancer_profile WHERE id = 1").fetchone()
    invoice["profile"] = dict(profile)if profile else {}
    return invoice


def export_invoices_to_csv(invoices: List[Dict[str, Any]]) -> str:
    """Generates a structured CSV file content of invoices."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Invoice Number",
        "Client Name",
        "Company",
        "Invoice Date",
        "Due Date",
        "Currency",
        "Subtotal",
        "Discount (%)",
        "Discount Amount",
        "Tax (%)",
        "Tax Amount",
        "Grand Total",
        "Status",
        "Paid Date",
        "Created At"
    ])
    for inv in invoices:
        writer.writerow([
            inv.get("invoice_number", ""),
            inv.get("client_name", ""),
            inv.get("company_name", "") or inv.get("client_company", ""),
            inv.get("invoice_date", ""),
            inv.get("due_date", ""),
            inv.get("currency", "INR"),
            f"{inv.get('subtotal', 0.0):.2f}",
            f"{inv.get('discount_percent', 0.0):.2f}",
            f"{inv.get('discount_amount', 0.0):.2f}",
            f"{inv.get('tax_percent', 0.0):.2f}",
            f"{inv.get('tax_amount', 0.0):.2f}",
            f"{inv.get('total', 0.0):.2f}",
            inv.get("status", ""),
            inv.get("paid_date", "") or "",
            inv.get("created_at", "")
        ])
    return output.getvalue()
