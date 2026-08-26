from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from app.database.db import get_db
from app.services.calculation_service import format_currency


def generate_business_insights() -> List[Dict[str, Any]]:
    """
    Analyzes historical invoices, payments, client behavior, and expenses
    using deterministic business rules to generate actionable insights.
    Categories:
    - PAYMENT: Late payment flags & risk alerts
    - REVENUE: Service revenue drivers & top service contribution
    - EXPENSE: Month-over-month spending increases & category spikes
    - PRICING: Hourly rate trends & realization
    - CLIENT: High-value client concentration
    """
    db = get_db()
    insights = []
    clients_rows = db.execute("SELECT id, name FROM clients").fetchall()
    for c in clients_rows:
        cid = c["id"]
        cname = c["name"]
        overdue_count = db.execute(
            "SELECT COUNT(*) as cnt FROM invoices WHERE client_id = ? AND status = 'Overdue'",
            (cid,)
        ).fetchone()["cnt"]
        if overdue_count >= 1:
            insights.append({
                "type": "PAYMENT",
                "severity": "warning",
                "icon": "alert-circle",
                "title": f"Payment Attention: {cname}",
                "message": f"{cname} has {overdue_count} overdue invoice(s). Consider sending a payment reminder."
            })
    service_rows = db.execute("""
        SELECT ii.description, SUM(ii.amount) as total_service_rev
        FROM invoice_items ii
        JOIN invoices i ON ii.invoice_id = i.id
        WHERE i.status = 'Paid'
        GROUP BY ii.description
        ORDER BY total_service_rev DESC
    """).fetchall()
    total_paid_rev = db.execute(
        "SELECT SUM(total) as total_rev FROM invoices WHERE status = 'Paid'"
    ).fetchone()["total_rev"] or 0.0
    if service_rows and total_paid_rev > 0:
        top_service = service_rows[0]
        top_service_name = top_service["description"]
        short_service_name = top_service_name[:40] + \
            ("..."if len(top_service_name) > 40 else "")
        share_pct = round(
            (top_service["total_service_rev"] / total_paid_rev) * 100)
        insights.append({
            "type": "REVENUE",
            "severity": "info",
            "icon": "trending-up",
            "title": "Top Revenue Driver",
            "message": f"'{short_service_name}' represents {share_pct}% ({format_currency(top_service['total_service_rev'])}) of your settled revenue."
        })
    today = date.today()
    first_this_month = today.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    first_last_month = last_month_end.replace(day=1)
    this_month_exp = db.execute(
        "SELECT SUM(amount) as total FROM expenses WHERE date >= ?",
        (first_this_month.isoformat(),)
    ).fetchone()["total"] or 0.0
    last_month_exp = db.execute(
        "SELECT SUM(amount) as total FROM expenses WHERE date >= ? AND date <= ?",
        (first_last_month.isoformat(), last_month_end.isoformat())
    ).fetchone()["total"] or 0.0
    if last_month_exp > 0 and this_month_exp > last_month_exp:
        pct_increase = round(
            ((this_month_exp - last_month_exp) / last_month_exp) * 100)
        if pct_increase >= 15:
            insights.append({
                "type": "EXPENSE",
                "severity": "warning",
                "icon": "pie-chart",
                "title": "Expense Alert",
                "message": f"Expenses this month ({format_currency(this_month_exp)}) have increased by {pct_increase}% compared to last month."
            })
    cat_rows = db.execute("""
        SELECT category, SUM(amount) as cat_total
        FROM expenses
        GROUP BY category
        ORDER BY cat_total DESC
        LIMIT 1
    """).fetchall()
    if cat_rows:
        top_cat = cat_rows[0]
        insights.append({
            "type": "EXPENSE",
            "severity": "neutral",
            "icon": "tag",
            "title": "Primary Expense Category",
            "message": f"{top_cat['category']} is your highest cost category at {format_currency(top_cat['cat_total'])}."
        })
    rate_stat = db.execute("""
        SELECT AVG(ii.hourly_rate) as avg_rate, MAX(ii.hourly_rate) as max_rate
        FROM invoice_items ii
        JOIN invoices i ON ii.invoice_id = i.id
        WHERE ii.hours > 0 AND ii.hourly_rate > 0
    """).fetchone()
    if rate_stat and rate_stat["avg_rate"]:
        avg_rate = round(rate_stat["avg_rate"], 2)
        insights.append({
            "type": "PRICING",
            "severity": "info",
            "icon": "clock",
            "title": "Average Realized Rate",
            "message": f"Your average billing rate across projects is {format_currency(avg_rate)}/hr (Peak: {format_currency(rate_stat['max_rate'])}/hr)."
        })
    client_val_rows = db.execute("""
        SELECT c.name, SUM(i.total) as client_total
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        WHERE i.status = 'Paid'
        GROUP BY c.id
        ORDER BY client_total DESC
        LIMIT 1
    """).fetchall()
    if client_val_rows and total_paid_rev > 0:
        top_client = client_val_rows[0]
        c_share = round((top_client["client_total"] / total_paid_rev) * 100)
        insights.append({
            "type": "CLIENT",
            "severity": "success",
            "icon": "user-check",
            "title": "Highest-Value Client",
            "message": f"{top_client['name']} is your top client, contributing {c_share}% ({format_currency(top_client['client_total'])}) of total earnings."
        })
    return insights
