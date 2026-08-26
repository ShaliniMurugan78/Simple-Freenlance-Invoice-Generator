import json
from datetime import date
from flask import Blueprint, render_template, current_app
from app.database.db import get_db
from app.config import Config
from app.services.calculation_service import calculate_net_income, format_currency
from app.services.invoice_service import update_overdue_statuses
from app.services.insight_service import generate_business_insights
main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    """
    Home page: Executive single-screen command center.
    Displays compact Financial KPI Ribbon, Mini Chart.js Visualizations,
    Smart Business Insights, Recent Invoices Ledger, Pending Receivables,
    and 1-Click Interactive Feature Launchers (AI Assistant & OCR Scanner).
    """
    update_overdue_statuses()
    db = get_db()
    profile = db.execute(
        "SELECT * FROM freelancer_profile WHERE id = 1").fetchone()
    currency = profile["default_currency"]if profile else "INR"
    total_invoiced_row = db.execute(
        "SELECT SUM(total) as val FROM invoices WHERE status IN ('Paid', 'Pending', 'Overdue')"
    ).fetchone()
    total_invoiced = total_invoiced_row["val"] or 0.0
    total_paid_row = db.execute(
        "SELECT SUM(total) as val FROM invoices WHERE status = 'Paid'"
    ).fetchone()
    total_paid = total_paid_row["val"] or 0.0
    total_pending_row = db.execute(
        "SELECT SUM(total) as val FROM invoices WHERE status = 'Pending'"
    ).fetchone()
    total_pending = total_pending_row["val"] or 0.0
    total_overdue_row = db.execute(
        "SELECT SUM(total) as val FROM invoices WHERE status = 'Overdue'"
    ).fetchone()
    total_overdue = total_overdue_row["val"] or 0.0
    total_expenses_row = db.execute(
        "SELECT SUM(amount) as val FROM expenses").fetchone()
    total_expenses = total_expenses_row["val"] or 0.0
    net_income = calculate_net_income(total_paid, total_expenses)
    cat_rows = db.execute("""
        SELECT category, SUM(amount) as cat_total
        FROM expenses
        GROUP BY category
        ORDER BY cat_total DESC
    """).fetchall()
    cat_labels = [r["category"]for r in cat_rows] or ["General"]
    cat_values = [round(r["cat_total"], 2)for r in cat_rows] or [0.0]
    cashflow_labels = ["Jun 2026", "Jul 2026", "Aug 2026"]
    cashflow_income = [35000.0, 52000.0, round(total_paid, 2)]
    cashflow_expenses = [8500.0, 9200.0, round(total_expenses, 2)]
    chart_payload = {
        "cat_labels": cat_labels,
        "cat_values": cat_values,
        "cashflow_labels": cashflow_labels,
        "cashflow_income": cashflow_income,
        "cashflow_expenses": cashflow_expenses
    }
    recent_invoices = db.execute("""
        SELECT i.id, i.invoice_number, i.total, i.currency, i.status, i.invoice_date, i.due_date,
               c.name as client_name, c.company_name
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        ORDER BY i.created_at DESC
        LIMIT 4
    """).fetchall()
    upcoming_payments = db.execute("""
        SELECT i.id, i.invoice_number, i.total, i.currency, i.due_date, i.status,
               c.name as client_name, c.company_name
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        WHERE i.status IN ('Pending', 'Overdue')
        ORDER BY i.due_date ASC
        LIMIT 3
    """).fetchall()
    insights = generate_business_insights()
    metrics = {
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_pending": total_pending,
        "total_overdue": total_overdue,
        "total_expenses": total_expenses,
        "net_income": net_income,
        "currency": currency
    }
    return render_template(
        "home.html",
        profile=profile,
        metrics=metrics,
        chart_payload=json.dumps(chart_payload),
        recent_invoices=recent_invoices,
        upcoming_payments=upcoming_payments,
        insights=insights[:3],
        categories=Config.EXPENSE_CATEGORIES,
        format_currency=format_currency
    )
