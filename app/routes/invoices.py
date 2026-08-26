import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from app.database.db import get_db, log_activity
from app.config import Config
from app.services.calculation_service import calculate_invoice_totals, format_currency
from app.services.invoice_service import (
    generate_next_invoice_number,
    calculate_document_hash,
    update_overdue_statuses,
    get_invoice_full_details,
    export_invoices_to_csv
)
from app.services.qr_service import generate_verification_token, generate_invoice_qr_code, generate_payment_qr_code
invoices_bp = Blueprint("invoices", __name__, url_prefix="/invoices")


@invoices_bp.route("/")
def index():
    """Invoices list page with search, status filtering, and CSV export."""
    update_overdue_statuses()
    db = get_db()
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    query = """
        SELECT i.*, c.name as client_name, c.company_name
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (i.invoice_number LIKE ? OR c.name LIKE ? OR c.company_name LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])
    if status_filter and status_filter.lower() != "all":
        query += " AND i.status = ?"
        params.append(status_filter)
    query += " ORDER BY i.invoice_date DESC, i.id DESC"
    invoices = db.execute(query, params).fetchall()
    counts = {
        "all": db.execute("SELECT COUNT(*) as c FROM invoices").fetchone()["c"],
        "Paid": db.execute("SELECT COUNT(*) as c FROM invoices WHERE status = 'Paid'").fetchone()["c"],
        "Pending": db.execute("SELECT COUNT(*) as c FROM invoices WHERE status = 'Pending'").fetchone()["c"],
        "Overdue": db.execute("SELECT COUNT(*) as c FROM invoices WHERE status = 'Overdue'").fetchone()["c"],
        "Draft": db.execute("SELECT COUNT(*) as c FROM invoices WHERE status = 'Draft'").fetchone()["c"],
        "Cancelled": db.execute("SELECT COUNT(*) as c FROM invoices WHERE status = 'Cancelled'").fetchone()["c"]
    }
    return render_template(
        "invoices/index.html",
        invoices=invoices,
        search=search,
        status_filter=status_filter,
        counts=counts,
        format_currency=format_currency
    )


@invoices_bp.route("/export.csv")
def export_csv():
    """Exports current invoice dataset as CSV."""
    db = get_db()
    invoices = db.execute("""
        SELECT i.*, c.name as client_name, c.company_name
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        ORDER BY i.invoice_date DESC
    """).fetchall()
    csv_data = export_invoices_to_csv([dict(inv)for inv in invoices])
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=invoices_export_{date.today().isoformat()}.csv"}
    )


@invoices_bp.route("/new", methods=["GET", "POST"])
def create():
    """Create a new invoice with automatic sequential numbering and dynamic line items."""
    db = get_db()
    profile = db.execute(
        "SELECT * FROM freelancer_profile WHERE id = 1").fetchone()
    clients = db.execute(
        "SELECT id, name, company_name FROM clients ORDER BY name ASC").fetchall()
    if request.method == "POST":
        invoice_number = request.form.get(
            "invoice_number", "").strip().upper()
        client_id = request.form.get("client_id")
        invoice_date_val = request.form.get(
            "invoice_date", date.today().isoformat())
        due_date_val = request.form.get("due_date", "")
        currency = request.form.get(
            "currency", profile["default_currency"]if profile else "INR")
        discount_percent = float(
            request.form.get(
                "discount_percent",
                0.0) or 0.0)
        tax_percent = float(
            request.form.get(
                "tax_percent",
                profile["default_tax_percent"]if profile else 18.0) or 0.0)
        payment_terms = request.form.get(
            "payment_terms", profile["default_payment_terms"]if profile else "")
        notes = request.form.get("notes", "")
        template = request.form.get(
            "template", profile["default_template"]if profile else "classic")
        status = request.form.get("status", "Pending")
        if not invoice_number:
            flash("Invoice number is required.", "error")
            return redirect(url_for("invoices.create"))
        existing = db.execute(
            "SELECT id FROM invoices WHERE invoice_number = ?",
            (invoice_number,
             )).fetchone()
        if existing:
            flash(
                f"Invoice number '{invoice_number}' already exists.Please choose a unique number.",
                "error")
            return redirect(url_for("invoices.create"))
        if not client_id:
            flash("Please select a client.", "error")
            return redirect(url_for("invoices.create"))
        descriptions = request.form.getlist("item_description[]")
        hours_list = request.form.getlist("item_hours[]")
        rates_list = request.form.getlist("item_rate[]")
        raw_items = []
        for i in range(len(descriptions)):
            desc = descriptions[i].strip()
            if not desc:
                continue
            hrs = float(hours_list[i]if i < len(
                hours_list) and hours_list[i]else 1.0)
            rate = float(rates_list[i]if i < len(
                rates_list) and rates_list[i]else 0.0)
            raw_items.append(
                {"description": desc, "hours": hrs, "hourly_rate": rate})
        if not raw_items:
            flash("Please add at least one line item with a description.", "error")
            return redirect(url_for("invoices.create"))
        totals = calculate_invoice_totals(
            raw_items, discount_percent, tax_percent)
        token = generate_verification_token()
        doc_hash = calculate_document_hash(
            invoice_number,
            int(client_id),
            totals["total"],
            invoice_date_val)
        cur = db.execute("""
            INSERT INTO invoices (
                invoice_number, client_id, invoice_date, due_date, currency,
                subtotal, discount_percent, discount_amount, tax_percent, tax_amount,
                total, status, payment_terms, notes, template, verification_token, document_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_number, client_id, invoice_date_val, due_date_val, currency,
            totals["subtotal"], totals["discount_percent"], totals["discount_amount"],
            totals["tax_percent"], totals["tax_amount"], totals["total"], status,
            payment_terms, notes, template, token, doc_hash
        ))
        invoice_id = cur.lastrowid
        for idx, item in enumerate(totals["processed_items"]):
            db.execute("""
                INSERT INTO invoice_items (invoice_id, description, hours, hourly_rate, amount, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (invoice_id, item["description"], item["hours"], item["hourly_rate"], item["amount"], idx))
        log_activity(
            "CREATE",
            "INVOICE",
            invoice_id,
            f"Created invoice {invoice_number} ({format_currency(totals['total'], currency)})")
        db.commit()
        flash(f"Invoice {invoice_number} generated successfully.", "success")
        return redirect(url_for("invoices.view", invoice_id=invoice_id))
    next_inv_number = generate_next_invoice_number()
    return render_template(
        "invoices/form.html",
        mode="create",
        next_invoice_number=next_inv_number,
        clients=clients,
        profile=profile,
        today=date.today().isoformat(),
        currencies=Config.SUPPORTED_CURRENCIES,
        templates=Config.AVAILABLE_TEMPLATES
    )


@invoices_bp.route("/<int:invoice_id>")
def view(invoice_id: int):
    """View invoice with template preview, live template switcher, print layout, and QR code."""
    update_overdue_statuses()
    invoice = get_invoice_full_details(invoice_id)
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.index"))
    requested_template = request.args.get(
        "template", invoice["template"]).lower()
    if requested_template in Config.AVAILABLE_TEMPLATES:
        active_template = requested_template
    else:
        active_template = invoice["template"]
    profile = invoice.get("profile") or {}
    upi_id = profile.get("upi_id") or "alexmorgan@okhdfcbank"
    business_name = profile.get("business_name") or profile.get(
        "full_name") or "Freelancer"
    payment_qr_data = generate_payment_qr_code(
        upi_id=upi_id,
        payee_name=business_name,
        amount=invoice["total"],
        currency=invoice["currency"],
        invoice_number=invoice["invoice_number"]
    )
    verification_qr_data = generate_invoice_qr_code(
        invoice["invoice_number"], invoice["verification_token"])
    return render_template(
        "invoices/view.html",
        invoice=invoice,
        active_template=active_template,
        qr_code_data=payment_qr_data,
        payment_qr_data=payment_qr_data,
        verification_qr_data=verification_qr_data,
        upi_id=upi_id,
        templates=Config.AVAILABLE_TEMPLATES,
        format_currency=format_currency
    )


@invoices_bp.route("/<int:invoice_id>/edit", methods=["GET", "POST"])
def edit(invoice_id: int):
    """Edit existing invoice."""
    db = get_db()
    invoice = get_invoice_full_details(invoice_id)
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.index"))
    profile = db.execute(
        "SELECT * FROM freelancer_profile WHERE id = 1").fetchone()
    clients = db.execute(
        "SELECT id, name, company_name FROM clients ORDER BY name ASC").fetchall()
    if request.method == "POST":
        invoice_number = request.form.get(
            "invoice_number", "").strip().upper()
        client_id = request.form.get("client_id")
        invoice_date_val = request.form.get(
            "invoice_date", invoice["invoice_date"])
        due_date_val = request.form.get("due_date", invoice["due_date"])
        currency = request.form.get("currency", invoice["currency"])
        discount_percent = float(
            request.form.get(
                "discount_percent",
                0.0) or 0.0)
        tax_percent = float(request.form.get("tax_percent", 0.0) or 0.0)
        payment_terms = request.form.get("payment_terms", "")
        notes = request.form.get("notes", "")
        template = request.form.get("template", invoice["template"])
        status = request.form.get("status", invoice["status"])
        if invoice_number != invoice["invoice_number"]:
            existing = db.execute(
                "SELECT id FROM invoices WHERE invoice_number = ? AND id != ?",
                (invoice_number,
                 invoice_id)).fetchone()
            if existing:
                flash(
                    f"Invoice number '{invoice_number}' is already in use.",
                    "error")
                return redirect(
                    url_for("invoices.edit", invoice_id=invoice_id))
        descriptions = request.form.getlist("item_description[]")
        hours_list = request.form.getlist("item_hours[]")
        rates_list = request.form.getlist("item_rate[]")
        raw_items = []
        for i in range(len(descriptions)):
            desc = descriptions[i].strip()
            if not desc:
                continue
            hrs = float(hours_list[i]if i < len(
                hours_list) and hours_list[i]else 1.0)
            rate = float(rates_list[i]if i < len(
                rates_list) and rates_list[i]else 0.0)
            raw_items.append(
                {"description": desc, "hours": hrs, "hourly_rate": rate})
        if not raw_items:
            flash("Please add at least one line item.", "error")
            return redirect(url_for("invoices.edit", invoice_id=invoice_id))
        totals = calculate_invoice_totals(
            raw_items, discount_percent, tax_percent)
        doc_hash = calculate_document_hash(
            invoice_number,
            int(client_id),
            totals["total"],
            invoice_date_val)
        db.execute("""
            UPDATE invoices
            SET invoice_number = ?, client_id = ?, invoice_date = ?, due_date = ?, currency = ?,
                subtotal = ?, discount_percent = ?, discount_amount = ?, tax_percent = ?, tax_amount = ?,
                total = ?, status = ?, payment_terms = ?, notes = ?, template = ?, document_hash = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            invoice_number, client_id, invoice_date_val, due_date_val, currency,
            totals["subtotal"], totals["discount_percent"], totals["discount_amount"],
            totals["tax_percent"], totals["tax_amount"], totals["total"], status,
            payment_terms, notes, template, doc_hash, invoice_id
        ))
        db.execute(
            "DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        for idx, item in enumerate(totals["processed_items"]):
            db.execute("""
                INSERT INTO invoice_items (invoice_id, description, hours, hourly_rate, amount, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (invoice_id, item["description"], item["hours"], item["hourly_rate"], item["amount"], idx))
        log_activity(
            "UPDATE",
            "INVOICE",
            invoice_id,
            f"Updated invoice {invoice_number}")
        db.commit()
        flash("Invoice updated successfully.", "success")
        return redirect(url_for("invoices.view", invoice_id=invoice_id))
    return render_template(
        "invoices/form.html",
        mode="edit",
        invoice=invoice,
        clients=clients,
        profile=profile,
        currencies=Config.SUPPORTED_CURRENCIES,
        templates=Config.AVAILABLE_TEMPLATES
    )


@invoices_bp.route("/<int:invoice_id>/mark-paid", methods=["POST"])
def mark_paid(invoice_id: int):
    """Marks an invoice as Paid and records the payment record."""
    db = get_db()
    invoice = db.execute(
        "SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.index"))
    paid_date_val = request.form.get("paid_date", date.today().isoformat())
    payment_method = request.form.get("payment_method", "Bank Transfer")
    db.execute("""
        UPDATE invoices
        SET status = 'Paid', paid_date = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (paid_date_val, invoice_id))
    db.execute("""
        INSERT INTO payment_records (invoice_id, amount, payment_date, payment_method, notes)
        VALUES (?, ?, ?, ?, 'Full payment settlement')
    """, (invoice_id, invoice["total"], paid_date_val, payment_method))
    log_activity(
        "PAYMENT",
        "INVOICE",
        invoice_id,
        f"Settled invoice {invoice['invoice_number']} ({format_currency(invoice['total'], invoice['currency'])})")
    db.commit()
    flash(f"Invoice {invoice['invoice_number']} marked as Paid.", "success")
    return redirect(url_for("invoices.view", invoice_id=invoice_id))


@invoices_bp.route("/<int:invoice_id>/delete", methods=["POST"])
def delete(invoice_id: int):
    """Deletes an invoice."""
    db = get_db()
    invoice = db.execute(
        "SELECT invoice_number FROM invoices WHERE id = ?",
        (invoice_id,
         )).fetchone()
    if invoice:
        inv_no = invoice["invoice_number"]
        db.execute(
            "DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        db.execute(
            "DELETE FROM payment_records WHERE invoice_id = ?", (invoice_id,))
        db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        log_activity(
            "DELETE",
            "INVOICE",
            invoice_id,
            f"Deleted invoice {inv_no}")
        db.commit()
        flash(f"Invoice {inv_no} was deleted.", "success")
    return redirect(url_for("invoices.index"))


@invoices_bp.route("/<int:invoice_id>/send-reminder", methods=["POST"])
def send_reminder(invoice_id: int):
    """Dispatches or prepares a payment reminder."""
    invoice = get_invoice_full_details(invoice_id)
    if not invoice:
        return jsonify(
            {"success": False, "message": "Invoice not found."}), 404
    client_email = invoice.get("client_email")
    client_name = invoice.get("client_name")
    invoice_number = invoice.get("invoice_number")
    amount = format_currency(invoice.get("total"), invoice.get("currency"))
    due_date_str = invoice.get("due_date")
    business_name = invoice["profile"].get(
        "business_name") or invoice["profile"].get("full_name") or "Freelance Billing"
    email_body = (
        f"Dear {client_name},\n\n"
        f"This is a friendly reminder that invoice {invoice_number} for {amount} "
        f"was due on {due_date_str} and is currently marked as {invoice['status']}.\n\n"
        f"Please verify and complete payment at your earliest convenience.\n\n"
        f"Thank you,\n{business_name}"
    )
    from dotenv import load_dotenv
    load_dotenv(override=True)
    smtp_host = os.getenv("SMTP_HOST") or Config.SMTP_HOST
    smtp_port = int(os.getenv("SMTP_PORT") or Config.SMTP_PORT or 587)
    smtp_user = (os.getenv("SMTP_USERNAME")
                 or Config.SMTP_USERNAME or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD")
                 or Config.SMTP_PASSWORD or "").strip()
    smtp_from = (os.getenv(
        "SMTP_FROM") or Config.SMTP_FROM or smtp_user or "invoices@freelance.local").strip()
    smtp_tls = os.getenv(
        "SMTP_USE_TLS",
        "True").lower() in (
        "true",
        "1",
        "yes")
    if smtp_host and smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_from
            msg["To"] = client_email
            msg["Subject"] = f"Payment Reminder: Invoice {invoice_number} - {business_name}"
            msg.attach(MIMEText(email_body, "plain"))
            with smtplib.SMTP(smtp_host, smtp_port, timeout=12)as server:
                if smtp_tls:
                    server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            log_activity(
                "REMINDER",
                "INVOICE",
                invoice_id,
                f"Sent email payment reminder for {invoice_number} to {client_email}")
            return jsonify({
                "success": True,
                "sent": True,
                "message": f"Payment reminder email sent successfully to {client_email} via Gmail SMTP.",
                "preview": email_body
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "sent": False,
                "message": f"SMTP dispatch error: {str(e)}",
                "preview": email_body
            })
    log_activity(
        "REMINDER",
        "INVOICE",
        invoice_id,
        f"Prepared payment reminder for {invoice_number}")
    return jsonify({
        "success": True,
        "sent": False,
        "message": f"Reminder generated for {client_name} ({client_email}). (SMTP not configured; copied message to clipboard/preview).",
        "preview": email_body
    })


@invoices_bp.route("/calculate", methods=["POST"])
def calculate_api():
    """API endpoint for live deterministic calculation updates from frontend JS."""
    data = request.get_json() or {}
    items = data.get("items", [])
    discount_pct = float(data.get("discount_percent", 0.0) or 0.0)
    tax_pct = float(data.get("tax_percent", 0.0) or 0.0)
    currency = data.get("currency", "INR")
    totals = calculate_invoice_totals(items, discount_pct, tax_pct)
    totals["formatted_subtotal"] = format_currency(
        totals["subtotal"], currency)
    totals["formatted_discount"] = format_currency(
        totals["discount_amount"], currency)
    totals["formatted_tax"] = format_currency(totals["tax_amount"], currency)
    totals["formatted_total"] = format_currency(totals["total"], currency)
    return jsonify(totals)
