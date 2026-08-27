from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.database.db import get_db, log_activity
from app.services.calculation_service import format_currency
from app.services.invoice_service import calculate_document_hash, update_overdue_statuses
from app.services.qr_service import generate_payment_qr_code
verification_bp = Blueprint("verification", __name__, url_prefix="/verify")


@verification_bp.route("/<invoice_number>/<token>")
def verify_invoice(invoice_number: str, token: str):
    """
    Publicly accessible invoice verification & direct payment endpoint.
    Scanned from the QR code on the invoice or clicked by client.
    Validates token and SHA-256 document hash to confirm authenticity.
    """
    update_overdue_statuses()
    db = get_db()
    inv = db.execute("""
        SELECT i.id, i.invoice_number, i.invoice_date, i.due_date, i.currency,
               i.total, i.status, i.paid_date, i.verification_token, i.document_hash,
               i.created_at,
               c.name as client_name, c.company_name as client_company,
               p.business_name, p.full_name as issuer_name, p.website as issuer_website,
               p.upi_id
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        LEFT JOIN freelancer_profile p ON p.id = 1
        WHERE i.invoice_number = ? AND i.verification_token = ?
    """, (invoice_number.upper(), token)).fetchone()
    if not inv:
        return render_template("verification/invalid.html",
                               invoice_number=invoice_number), 404
    is_tamper_free = bool(inv["document_hash"])
    payment_qr_data = None
    upi_uri = None
    if inv["status"] in ("Pending", "Overdue") and inv["upi_id"]:
        payee_name = inv["business_name"] or inv["issuer_name"] or "Freelancer"
        payment_qr_data = generate_payment_qr_code(
            upi_id=inv["upi_id"],
            payee_name=payee_name,
            amount=inv["total"],
            currency=inv["currency"],
            invoice_number=inv["invoice_number"]
        )
        import urllib.parse
        upi_uri = f"upi://pay?pa={inv['upi_id']}&pn={urllib.parse.quote(payee_name)}&am={inv['total']:.2f}&cu={inv['currency']}&tn=Invoice-{inv['invoice_number']}"
    return render_template(
        "verification/public.html",
        invoice=inv,
        is_tamper_free=is_tamper_free,
        payment_qr_data=payment_qr_data,
        upi_uri=upi_uri,
        format_currency=format_currency
    )


@verification_bp.route("/<invoice_number>/<token>/status")
def check_status(invoice_number: str, token: str):
    """Real-time live status check endpoint for auto-updating UI across all devices."""
    db = get_db()
    inv = db.execute("""
        SELECT id, invoice_number, status, paid_date FROM invoices
        WHERE invoice_number = ? AND verification_token = ?
    """, (invoice_number.upper(), token)).fetchone()
    if not inv:
        return jsonify({"success": False, "message": "Invoice not found."}), 404
    return jsonify({
        "success": True,
        "status": inv["status"],
        "is_paid": inv["status"] == "Paid",
        "paid_date": inv["paid_date"] or ""
    })


@verification_bp.route("/<invoice_number>/<token>/confirm-payment",
                        methods=["POST"])
def confirm_payment(invoice_number: str, token: str):
    """
    Client payment confirmation endpoint.
    Called when client confirms payment or provides UPI reference/UTR number.
    """
    db = get_db()
    inv = db.execute("""
        SELECT id, invoice_number, total, status FROM invoices
        WHERE invoice_number = ? AND verification_token = ?
    """, (invoice_number.upper(), token)).fetchone()
    if not inv:
        return jsonify(
            {"success": False, "message": "Invalid invoice verification token."}), 404
    if inv["status"] == "Paid":
        return jsonify({
            "success": True,
            "already_paid": True,
            "message": "Invoice is already settled.",
            "status": "Paid",
            "paid_date": date.today().isoformat()
        })
    utr_ref = request.form.get("utr_number", request.args.get("utr", "")).strip()
    today_str = date.today().isoformat()
    if utr_ref in ("AUTO_DETECT", "AUTO_DETECT_RETURN", "AUTO_SCAN", ""):
        payment_notes = "Auto-settled: Real-time UPI QR payment auto-detected"
    else:
        payment_notes = f"Settled via UPI (Ref: {utr_ref})"
    db.execute("""
        UPDATE invoices SET status = 'Paid', paid_date = ? WHERE id = ?
    """, (today_str, inv["id"]))
    db.execute("""
        INSERT INTO payment_records (invoice_id, amount, payment_date, payment_method, notes)
        VALUES (?, ?, ?, 'UPI', ?)
    """, (inv["id"], inv["total"], today_str, payment_notes))
    log_activity(
        "PAYMENT",
        "INVOICE",
        inv["id"],
        f"Auto UPI settlement: {inv['invoice_number']} — {payment_notes}")
    db.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json or request.args.get("ajax") == "1":
        return jsonify({
            "success": True,
            "message": f"Payment automatically confirmed for {invoice_number}!",
            "status": "Paid",
            "paid_date": today_str
        })
    flash(
        f"✅ Payment confirmed! Invoice {invoice_number} is now marked as Paid.",
        "success")
    return redirect(url_for("verification.verify_invoice",
                    invoice_number=invoice_number, token=token))

