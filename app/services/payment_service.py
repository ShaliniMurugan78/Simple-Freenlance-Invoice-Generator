import hmac
import hashlib
import json
import requests
from flask import current_app
from app.config import Config


def is_razorpay_configured() -> bool:
    """Checks if Razorpay API keys are configured in environment / config."""
    key_id = current_app.config.get("RAZORPAY_KEY_ID") or Config.RAZORPAY_KEY_ID
    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET") or Config.RAZORPAY_KEY_SECRET
    return bool(key_id and key_secret)


def get_razorpay_key_id() -> str:
    """Returns the configured public Razorpay Key ID."""
    return current_app.config.get("RAZORPAY_KEY_ID") or Config.RAZORPAY_KEY_ID or ""


def create_razorpay_order(invoice_id: int, invoice_number: str, amount: float, currency: str = "INR") -> dict:
    """
    Creates a dynamic order on Razorpay servers via the official REST API.
    Amount is converted to the lowest denomination (paise / cents).
    """
    key_id = current_app.config.get("RAZORPAY_KEY_ID") or Config.RAZORPAY_KEY_ID
    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET") or Config.RAZORPAY_KEY_SECRET

    if not key_id or not key_secret:
        raise ValueError("Razorpay credentials are not configured.")

    # Razorpay expects integer amount in paise (1 INR = 100 paise)
    amount_in_subunits = int(round(float(amount) * 100))
    receipt = f"rcpt_{invoice_number}_{invoice_id}"[:40]

    payload = {
        "amount": amount_in_subunits,
        "currency": currency.upper() if currency in ("INR", "USD", "EUR", "GBP") else "INR",
        "receipt": receipt,
        "notes": {
            "invoice_id": str(invoice_id),
            "invoice_number": str(invoice_number)
        }
    }

    response = requests.post(
        "https://api.razorpay.com/v1/orders",
        auth=(key_id, key_secret),
        json=payload,
        timeout=15
    )

    if response.status_code != 200:
        error_msg = response.json().get("error", {}).get("description", response.text)
        raise RuntimeError(f"Razorpay Order Creation Failed: {error_msg}")

    return response.json()


def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    """
    Cryptographically verifies the authenticity of client-side Razorpay payment response
    using HMAC-SHA256 signature algorithm.
    """
    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET") or Config.RAZORPAY_KEY_SECRET
    if not key_secret:
        return False

    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    generated_signature = hmac.new(
        key_secret.encode("utf-8"),
        msg,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(generated_signature, razorpay_signature)


def verify_webhook_signature(raw_body: bytes, webhook_signature: str) -> bool:
    """
    Verifies Razorpay Webhook signature (X-Razorpay-Signature) sent with webhook POST request.
    """
    webhook_secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET") or Config.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret:
        # Fallback to key secret if dedicated webhook secret is not set
        webhook_secret = current_app.config.get("RAZORPAY_KEY_SECRET") or Config.RAZORPAY_KEY_SECRET

    if not webhook_secret or not webhook_signature:
        return False

    generated_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(generated_signature, webhook_signature)
