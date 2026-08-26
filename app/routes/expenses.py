import os
import csv
import io
from datetime import datetime, date
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from app.database.db import get_db, log_activity
from app.config import Config
from app.services.calculation_service import format_currency
expenses_bp = Blueprint("expenses", __name__, url_prefix="/expenses")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(
        ".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@expenses_bp.route("/")
def index():
    """Expenses list with search, category filtering, summary totals, and CSV export."""
    db = get_db()
    search = request.args.get("search", "").strip()
    category_filter = request.args.get("category", "").strip()
    query = "SELECT * FROM expenses WHERE 1=1"
    params = []
    if search:
        query += " AND (description LIKE ? OR merchant LIKE ? OR notes LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])
    if category_filter and category_filter.lower() != "all":
        query += " AND category = ?"
        params.append(category_filter)
    query += " ORDER BY date DESC, id DESC"
    expenses = db.execute(query, params).fetchall()
    category_stats = db.execute("""
        SELECT category, COUNT(*) as count, SUM(amount) as total
        FROM expenses
        GROUP BY category
        ORDER BY total DESC
    """).fetchall()
    total_expenses = sum(exp["amount"]for exp in expenses)
    return render_template(
        "expenses/index.html",
        expenses=expenses,
        categories=Config.EXPENSE_CATEGORIES,
        category_stats=category_stats,
        total_expenses=total_expenses,
        search=search,
        category_filter=category_filter,
        format_currency=format_currency
    )


@expenses_bp.route("/export.csv")
def export_csv():
    """Exports expenses dataset to CSV."""
    db = get_db()
    expenses = db.execute(
        "SELECT * FROM expenses ORDER BY date DESC").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date",
                      "Description",
                      "Merchant",
                      "Category",
                      "Amount",
                      "Currency",
                      "Payment Method",
                      "Notes"])
    for exp in expenses:
        writer.writerow([
            exp["date"],
            exp["description"],
            exp["merchant"] or "",
            exp["category"],
            f"{exp['amount']:.2f}",
            exp["currency"],
            exp["payment_method"] or "",
            exp["notes"] or ""
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=expenses_export_{date.today().isoformat()}.csv"}
    )


@expenses_bp.route("/new", methods=["GET", "POST"])
def create():
    """Manually add an expense or save a scanned receipt."""
    if request.method == "POST":
        db = get_db()
        date_val = request.form.get("date", date.today().isoformat())
        description = request.form.get("description", "").strip()
        merchant = request.form.get("merchant", "").strip()
        category = request.form.get("category", "Other")
        amount = float(request.form.get("amount", 0.0) or 0.0)
        currency = request.form.get("currency", "INR")
        payment_method = request.form.get("payment_method", "Bank Transfer")
        notes = request.form.get("notes", "").strip()
        receipt_path = None
        if not description:
            flash("Description is required.", "error")
            return redirect(url_for("expenses.create"))
        if amount <= 0:
            flash("Please enter a valid expense amount greater than 0.", "error")
            return redirect(url_for("expenses.create"))
        if "receipt_file" in request.files:
            file = request.files["receipt_file"]
            if file and file.filename and allowed_file(file.filename):
                filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
                upload_dir = Path(Config.UPLOAD_FOLDER)
                upload_dir.mkdir(parents=True, exist_ok=True)
                save_path = upload_dir / filename
                file.save(save_path)
                receipt_path = f"uploads/{filename}"
        cur = db.execute("""
            INSERT INTO expenses (date, description, merchant, category, amount, currency, payment_method, receipt_path, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_val, description, merchant, category, amount, currency, payment_method, receipt_path, notes))
        expense_id = cur.lastrowid
        log_activity(
            "CREATE",
            "EXPENSE",
            expense_id,
            f"Added expense {description} ({format_currency(amount, currency)})")
        db.commit()
        flash("Expense recorded successfully.", "success")
        return redirect(url_for("expenses.index"))
    return render_template(
        "expenses/form.html",
        mode="create",
        today=date.today().isoformat(),
        categories=Config.EXPENSE_CATEGORIES,
        currencies=Config.SUPPORTED_CURRENCIES
    )


@expenses_bp.route("/<int:expense_id>/edit", methods=["GET", "POST"])
def edit(expense_id: int):
    """Edit existing expense."""
    db = get_db()
    expense = db.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        flash("Expense not found.", "error")
        return redirect(url_for("expenses.index"))
    if request.method == "POST":
        date_val = request.form.get("date", expense["date"])
        description = request.form.get("description", "").strip()
        merchant = request.form.get("merchant", "").strip()
        category = request.form.get("category", expense["category"])
        amount = float(request.form.get("amount", 0.0) or 0.0)
        currency = request.form.get("currency", expense["currency"])
        payment_method = request.form.get(
            "payment_method", expense["payment_method"])
        notes = request.form.get("notes", "").strip()
        receipt_path = expense["receipt_path"]
        if not description or amount <= 0:
            flash("Valid description and positive amount are required.", "error")
            return redirect(url_for("expenses.edit", expense_id=expense_id))
        if "receipt_file" in request.files:
            file = request.files["receipt_file"]
            if file and file.filename and allowed_file(file.filename):
                filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
                upload_dir = Path(Config.UPLOAD_FOLDER)
                upload_dir.mkdir(parents=True, exist_ok=True)
                save_path = upload_dir / filename
                file.save(save_path)
                receipt_path = f"uploads/{filename}"
        db.execute("""
            UPDATE expenses
            SET date = ?, description = ?, merchant = ?, category = ?, amount = ?,
                currency = ?, payment_method = ?, receipt_path = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (date_val, description, merchant, category, amount, currency, payment_method, receipt_path, notes, expense_id))
        log_activity("UPDATE", "EXPENSE", expense_id,
                     f"Updated expense {description}")
        db.commit()
        flash("Expense updated successfully.", "success")
        return redirect(url_for("expenses.index"))
    return render_template(
        "expenses/form.html",
        mode="edit",
        expense=expense,
        categories=Config.EXPENSE_CATEGORIES,
        currencies=Config.SUPPORTED_CURRENCIES
    )


@expenses_bp.route("/<int:expense_id>/delete", methods=["POST"])
def delete(expense_id: int):
    """Deletes an expense."""
    db = get_db()
    expense = db.execute(
        "SELECT description FROM expenses WHERE id = ?",
        (expense_id,
         )).fetchone()
    if expense:
        desc = expense["description"]
        db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        log_activity(
            "DELETE",
            "EXPENSE",
            expense_id,
            f"Deleted expense {desc}")
        db.commit()
        flash(f"Expense '{desc}' was deleted.", "success")
    return redirect(url_for("expenses.index"))
