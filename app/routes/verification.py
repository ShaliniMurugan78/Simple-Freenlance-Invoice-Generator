import json
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.database.db import get_db, log_activity
from app.services.calculation_service import format_currency
from app.services.invoice_service import calculate_document_hash, update_overdue_statuses
from app.services.qr_service import generate_payment_qr_code
from app.services.payment_service import (
    is_razorpay_configured,
    get_razorpay_key_id,
    create_razorpay_order,
    verify_payment_signature,
    verify_webhook_signature
)

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
               c.name as client_name, c.company_name as client_company, c.email as client_email, c.phone as client_phone,
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
        is_razorpay_enabled=is_razorpay_configured(),
        razorpay_key_id=get_razorpay_key_id(),
        format_currency=format_currency
    )


@verification_bp.route("/<invoice_number>/<token>/create-order", methods=["POST"])
def create_order(invoice_number: str, token: str):
    """
    Creates a dynamic Razorpay order for this invoice.
    """
    db = get_db()
    inv = db.execute("""
        SELECT id, invoice_number, total, currency, status FROM invoices
        WHERE invoice_number = ? AND verification_token = ?
    """, (invoice_number.upper(), token)).fetchone()
    if not inv:
        return jsonify({"success": False, "message": "Invoice not found."}), 404
    if inv["status"] == "Paid":
        return jsonify({"success": False, "message": "Invoice is already paid."}), 400

    try:
        order = create_razorpay_order(
            invoice_id=inv["id"],
            invoice_number=inv["invoice_number"],
            amount=inv["total"],
            currency=inv["currency"]
        )
        return jsonify({
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": get_razorpay_key_id()
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@verification_bp.route("/<invoice_number>/<token>/verify-payment", methods=["POST"])
def verify_payment(invoice_number: str, token: str):
    """
    Validates Razorpay payment signature from client checkout callback.
    Authentically updates status to 'Paid' upon successful cryptographic check.
    """
    db = get_db()
    inv = db.execute("""
        SELECT id, invoice_number, total, status FROM invoices
        WHERE invoice_number = ? AND verification_token = ?
    """, (invoice_number.upper(), token)).fetchone()
    if not inv:
        return jsonify({"success": False, "message": "Invoice not found."}), 404

    data = request.get_json() or request.form or {}
    order_id = data.get("razorpay_order_id", "").strip()
    payment_id = data.get("razorpay_payment_id", "").strip()
    signature = data.get("razorpay_signature", "").strip()

    if not order_id or not payment_id or not signature:
        return jsonify({"success": False, "message": "Missing payment signature credentials."}), 400

    is_valid = verify_payment_signature(order_id, payment_id, signature)
    if not is_valid:
        return jsonify({"success": False, "message": "Invalid cryptographic payment signature."}), 400

    today_str = date.today().isoformat()
    payment_notes = f"Settled via Razorpay UPI/Card (Payment ID: {payment_id}, Order: {order_id})"
    
    db.execute("UPDATE invoices SET status = 'Paid', paid_date = ? WHERE id = ?", (today_str, inv["id"]))
    db.execute("""
        INSERT INTO payment_records (invoice_id, amount, payment_date, payment_method, notes)
        VALUES (?, ?, ?, 'Razorpay', ?)
    """, (inv["id"], inv["total"], today_str, payment_notes))
    log_activity("PAYMENT", "INVOICE", inv["id"], f"Razorpay Payment Verified: {inv['invoice_number']} — {payment_notes}")
    db.commit()

    return jsonify({
        "success": True,
        "message": f"Payment successfully verified for {invoice_number}!",
        "status": "Paid",
        "paid_date": today_str
    })


@verification_bp.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    """
    Server-to-server webhook endpoint for Razorpay.
    Listens for 'payment.captured' and 'order.paid' events, cryptographically verifies
    the payload signature, and automatically updates the database with 0 human interaction.
    """
    signature = request.headers.get("X-Razorpay-Signature", "")
    raw_body = request.get_data()

    if not verify_webhook_signature(raw_body, signature):
        return jsonify({"success": False, "message": "Invalid webhook signature."}), 400

    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return jsonify({"success": False, "message": "Invalid JSON payload."}), 400

    event_type = event_data.get("event", "")
    if event_type in ("payment.captured", "order.paid"):
        payload_entity = event_data.get("payload", {}).get("payment", {}).get("entity", {})
        if not payload_entity:
            payload_entity = event_data.get("payload", {}).get("order", {}).get("entity", {})
        
        notes = payload_entity.get("notes", {})
        invoice_id = notes.get("invoice_id")
        invoice_number = notes.get("invoice_number")
        payment_id = payload_entity.get("id", "N/A")

        db = get_db()
        inv = None
        if invoice_id:
            inv = db.execute("SELECT id, invoice_number, total, status FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        elif invoice_number:
            inv = db.execute("SELECT id, invoice_number, total, status FROM invoices WHERE invoice_number = ?", (invoice_number,)).fetchone()

        if inv and inv["status"] != "Paid":
            today_str = date.today().isoformat()
            payment_notes = f"Auto-settled via Razorpay Webhook ({event_type}, ID: {payment_id})"
            db.execute("UPDATE invoices SET status = 'Paid', paid_date = ? WHERE id = ?", (today_str, inv["id"]))
            db.execute("""
                INSERT INTO payment_records (invoice_id, amount, payment_date, payment_method, notes)
                VALUES (?, ?, ?, 'Razorpay Webhook', ?)
            """, (inv["id"], inv["total"], today_str, payment_notes))
            log_activity("PAYMENT", "INVOICE", inv["id"], f"Webhook settlement: {inv['invoice_number']} — {payment_notes}")
            db.commit()

    return jsonify({"status": "ok"}), 200


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


@verification_bp.route("/<invoice_number>/<token>/confirm-payment", methods=["POST"])
def confirm_payment(invoice_number: str, token: str):
    """
    Client payment confirmation endpoint.
    Called when client manually confirms payment or provides UPI reference/UTR number.
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
    payment_notes = f"Settled via UPI (Ref: {utr_ref})" if utr_ref else "Settled via Direct UPI Payment"
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
        f"Manual UPI settlement: {inv['invoice_number']} — {payment_notes}")
    db.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json or request.args.get("ajax") == "1":
        return jsonify({
            "success": True,
            "message": f"Payment successfully confirmed for {invoice_number}!",
            "status": "Paid",
            "paid_date": today_str
        })
    flash(
        f"✅ Payment confirmed! Invoice {invoice_number} is now marked as Paid.",
        "success")
    return redirect(url_for("verification.verify_invoice",
                    invoice_number=invoice_number, token=token))


