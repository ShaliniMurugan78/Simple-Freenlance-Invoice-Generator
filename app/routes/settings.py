from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from app.database.db import get_db, log_activity, create_backup, seed_demo_data
from app.config import Config
settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(
        ".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@settings_bp.route("/", methods=["GET", "POST"])
def index():
    """Manage Freelancer Business Profile, defaults, and system settings."""
    db = get_db()
    profile = db.execute(
        "SELECT * FROM freelancer_profile WHERE id = 1").fetchone()
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        business_name = request.form.get("business_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        website = request.form.get("website", "").strip()
        tax_number = request.form.get("tax_number", "").strip()
        upi_id = request.form.get("upi_id", "").strip()
        default_currency = request.form.get("default_currency", "INR")
        default_tax_percent = float(
            request.form.get(
                "default_tax_percent",
                18.0) or 0.0)
        default_payment_terms = request.form.get(
            "default_payment_terms", "").strip()
        default_template = request.form.get("default_template", "classic")
        logo_path = profile["logo_path"]if profile else None
        if request.form.get("remove_logo") == "1":
            logo_path = None
        if "logo_file" in request.files:
            file = request.files["logo_file"]
            if file and file.filename and allowed_file(file.filename):
                filename = f"logo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
                upload_dir = Path(Config.UPLOAD_FOLDER)
                upload_dir.mkdir(parents=True, exist_ok=True)
                save_path = upload_dir / filename
                file.save(save_path)
                logo_path = f"uploads/{filename}"
        db.execute("""
            UPDATE freelancer_profile
            SET full_name = ?, business_name = ?, email = ?, phone = ?, address = ?, website = ?,
                tax_number = ?, upi_id = ?, logo_path = ?, default_currency = ?, default_tax_percent = ?,
                default_payment_terms = ?, default_template = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """, (
            full_name, business_name, email, phone, address, website,
            tax_number, upi_id, logo_path, default_currency, default_tax_percent,
            default_payment_terms, default_template
        ))
        log_activity(
            "UPDATE",
            "SETTINGS",
            1,
            "Updated freelancer business profile settings")
        db.commit()
        flash("Business profile & billing preferences updated.", "success")
        return redirect(url_for("settings.index"))
    activity_logs = db.execute("""
        SELECT * FROM activity_logs
        ORDER BY created_at DESC
        LIMIT 15
    """).fetchall()
    return render_template(
        "settings/index.html",
        profile=profile,
        activity_logs=activity_logs,
        currencies=Config.SUPPORTED_CURRENCIES,
        templates=Config.AVAILABLE_TEMPLATES
    )


@settings_bp.route("/backup")
def backup_db():
    """Generates and downloads a timestamped backup of the SQLite database."""
    try:
        backup_file = create_backup()
        log_activity(
            "BACKUP",
            "DATABASE",
            1,
            f"Generated database backup: {backup_file.name}")
        return send_file(
            backup_file,
            as_attachment=True,
            download_name=backup_file.name
        )
    except Exception as e:
        flash(f"Backup failed: {str(e)}", "error")
        return redirect(url_for("settings.index"))


@settings_bp.route("/seed-demo", methods=["POST"])
def seed_demo():
    """Seeds rich demo data for interview demonstrations."""
    success, msg = seed_demo_data()
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return redirect(url_for("main.home"))
