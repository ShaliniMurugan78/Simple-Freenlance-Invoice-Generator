import os
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "smart_freelance_invoice_secret_key_default")
    DATABASE_PATH = BASE_DIR / "instance" / "smart_invoice.db"
    UPLOAD_FOLDER = BASE_DIR / "app" / "static" / "uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    BACKUP_FOLDER = BASE_DIR / "backups"
    AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
    AI_API_KEY = os.getenv("AI_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "gemini-1.5-flash")
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "invoices@freelance.local")
    SMTP_USE_TLS = os.getenv(
        "SMTP_USE_TLS",
        "True").lower() in (
        "true",
        "1",
        "yes")
    SUPPORTED_CURRENCIES = {
        "INR": {"symbol": "₹", "name": "Indian Rupee"},
        "USD": {"symbol": "$", "name": "US Dollar"},
        "EUR": {"symbol": "€", "name": "Euro"},
        "GBP": {"symbol": "£", "name": "British Pound"}
    }
    AVAILABLE_TEMPLATES = ["classic", "modern", "minimal"]
    EXPENSE_CATEGORIES = [
        "Software",
        "Travel",
        "Equipment",
        "Internet",
        "Marketing",
        "Office",
        "Utilities",
        "Other"
    ]
