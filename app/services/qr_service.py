import io
import base64
import secrets
import urllib.parse
import qrcode
from typing import Optional
from flask import url_for, request


def generate_verification_token() -> str:
    """Generates a secure, unpredictable 32-character hexadecimal token."""
    return secrets.token_hex(16)


def generate_payment_qr_code(
    upi_id: str,
    payee_name: str,
    amount: float,
    currency: str = "INR",
    invoice_number: str = ""
) -> str:
    """
    Generates a high-resolution Direct Payment QR Code (UPI specification).
    When scanned by Google Pay, PhonePe, Paytm, BHIM, or any banking app:
    - Pre-fills Payee Name
    - Pre-fills UPI VPA ID
    - Pre-fills Exact Invoice Amount
    - Sets Transaction Note with Invoice Number
    """
    clean_upi = (upi_id or "").strip()
    clean_name = (payee_name or "Freelancer").strip()
    clean_note = f"Invoice {invoice_number}".strip()
    amt_val = f"{float(amount or 0.0):.2f}"
    params = {
        "pa": clean_upi,
        "pn": clean_name,
        "am": amt_val,
        "cu": currency.upper()if currency else "INR",
        "tn": clean_note
    }
    upi_uri = f"upi://pay?{urllib.parse.urlencode(params)}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_b64}"


def generate_invoice_qr_code(
    invoice_number: str,
    verification_token: str,
    base_url: Optional[str] = None
) -> str:
    """
    Generates a QR code image linking to the public invoice verification page.
    """
    if base_url:
        verify_url = f"{base_url.rstrip('/')}/verify/{invoice_number}/{verification_token}"
    else:
        try:
            verify_url = url_for(
                "verification.verify_invoice",
                invoice_number=invoice_number,
                token=verification_token,
                _external=True)
        except RuntimeError:
            verify_url = f"http://127.0.0.1:5000/verify/{invoice_number}/{verification_token}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1E293B", back_color="#FFFFFF")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_b64}"
