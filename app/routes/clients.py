from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database.db import get_db, log_activity
from app.services.calculation_service import format_currency
from app.services.invoice_service import update_overdue_statuses
clients_bp = Blueprint("clients", __name__, url_prefix="/clients")


@clients_bp.route("/")
def index():
    """Clients list with search and summary metrics."""
    update_overdue_statuses()
    db = get_db()
    search = request.args.get("search", "").strip()
    query = """
        SELECT c.*,
               COUNT(i.id) as invoice_count,
               COALESCE(SUM(CASE WHEN i.status != 'Cancelled' THEN i.total ELSE 0 END), 0) as total_billed,
               COALESCE(SUM(CASE WHEN i.status = 'Paid' THEN i.total ELSE 0 END), 0) as total_paid,
               COALESCE(SUM(CASE WHEN i.status IN ('Pending', 'Overdue') THEN i.total ELSE 0 END), 0) as total_outstanding
        FROM clients c
        LEFT JOIN invoices i ON c.id = i.client_id
    """
    params = []
    if search:
        query += " WHERE c.name LIKE ? OR c.company_name LIKE ? OR c.email LIKE ?"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])
    query += " GROUP BY c.id ORDER BY c.name ASC"
    clients = db.execute(query, params).fetchall()
    return render_template(
        "clients/index.html",
        clients=clients,
        search=search,
        format_currency=format_currency
    )


@clients_bp.route("/new", methods=["GET", "POST"])
def create():
    """Add a new client."""
    if request.method == "POST":
        db = get_db()
        name = request.form.get("name", "").strip()
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        tax_number = request.form.get("tax_number", "").strip()
        notes = request.form.get("notes", "").strip()
        if not name:
            flash("Client name is required.", "error")
            return redirect(url_for("clients.create"))
        if not email:
            flash("Client email is required.", "error")
            return redirect(url_for("clients.create"))
        cur = db.execute("""
            INSERT INTO clients (name, company_name, email, phone, address, tax_number, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, company_name, email, phone, address, tax_number, notes))
        client_id = cur.lastrowid
        log_activity("CREATE", "CLIENT", client_id, f"Added client {name}")
        db.commit()
        flash(f"Client '{name}' added successfully.", "success")
        return redirect(url_for("clients.view", client_id=client_id))
    return render_template("clients/form.html", mode="create")


@clients_bp.route("/<int:client_id>")
def view(client_id: int):
    """View client details, complete invoice ledger, and payment behavior analysis."""
    update_overdue_statuses()
    db = get_db()
    client = db.execute(
        "SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        flash("Client not found.", "error")
        return redirect(url_for("clients.index"))
    invoices = db.execute("""
        SELECT * FROM invoices
        WHERE client_id = ?
        ORDER BY invoice_date DESC, id DESC
    """, (client_id,)).fetchall()
    total_billed = sum(inv["total"]
                       for inv in invoices if inv["status"] != "Cancelled")
    total_paid = sum(inv["total"]
                     for inv in invoices if inv["status"] == "Paid")
    outstanding = sum(
        inv["total"]for inv in invoices if inv["status"] in (
            "Pending", "Overdue"))
    overdue_count = sum(1 for inv in invoices if inv["status"] == "Overdue")
    if len(invoices) == 0:
        payment_behavior = "New Client (No invoices yet)"
        behavior_status = "neutral"
    elif overdue_count > 0:
        payment_behavior = f"Caution: {overdue_count} Overdue Invoice(s)"
        behavior_status = "warning"
    elif total_paid == total_billed:
        payment_behavior = "Excellent: All invoices settled on time"
        behavior_status = "success"
    else:
        payment_behavior = "Active: Invoices currently within payment terms"
        behavior_status = "info"
    stats = {
        "total_billed": total_billed,
        "total_paid": total_paid,
        "outstanding": outstanding,
        "overdue_count": overdue_count,
        "invoice_count": len(invoices),
        "payment_behavior": payment_behavior,
        "behavior_status": behavior_status
    }
    return render_template(
        "clients/view.html",
        client=client,
        invoices=invoices,
        stats=stats,
        format_currency=format_currency
    )


@clients_bp.route("/<int:client_id>/edit", methods=["GET", "POST"])
def edit(client_id: int):
    """Edit client details."""
    db = get_db()
    client = db.execute(
        "SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        flash("Client not found.", "error")
        return redirect(url_for("clients.index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        tax_number = request.form.get("tax_number", "").strip()
        notes = request.form.get("notes", "").strip()
        if not name or not email:
            flash("Name and email are required.", "error")
            return redirect(url_for("clients.edit", client_id=client_id))
        db.execute("""
            UPDATE clients
            SET name = ?, company_name = ?, email = ?, phone = ?, address = ?, tax_number = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (name, company_name, email, phone, address, tax_number, notes, client_id))
        log_activity("UPDATE", "CLIENT", client_id, f"Updated client {name}")
        db.commit()
        flash("Client updated successfully.", "success")
        return redirect(url_for("clients.view", client_id=client_id))
    return render_template("clients/form.html", mode="edit", client=client)


@clients_bp.route("/<int:client_id>/delete", methods=["POST"])
def delete(client_id: int):
    """Deletes a client if there are no associated invoices."""
    db = get_db()
    client = db.execute(
        "SELECT name FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        flash("Client not found.", "error")
        return redirect(url_for("clients.index"))
    invoice_count = db.execute(
        "SELECT COUNT(*) as c FROM invoices WHERE client_id = ?",
        (client_id,
         )).fetchone()["c"]
    if invoice_count > 0:
        flash(
            f"Cannot delete client '{client['name']}' because {invoice_count} invoice(s) are linked to them.Delete the invoices first or keep the client record.",
            "error")
        return redirect(url_for("clients.view", client_id=client_id))
    c_name = client["name"]
    db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    log_activity("DELETE", "CLIENT", client_id, f"Deleted client {c_name}")
    db.commit()
    flash(f"Client '{c_name}' was deleted.", "success")
    return redirect(url_for("clients.index"))
