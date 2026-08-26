from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import check_password_hash, generate_password_hash
from app.database.db import get_db, log_activity
auth_bp = Blueprint("auth", __name__)


def login_required(view_func):
    """Decorator to require authenticated session on protected routes."""
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if "user_id"not in session:
            flash("Please sign in to access your financial dashboard.", "info")
            return redirect(url_for("auth.login", next=request.url))
        return view_func(*args, **kwargs)
    return decorated_view


@auth_bp.before_app_request
def load_logged_in_user():
    """Loads user from session into flask global g before each request."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = db.execute(
            "SELECT id, email, full_name, role FROM users WHERE id = ?",
            (user_id,
             )).fetchone()


@auth_bp.app_context_processor
def inject_current_user():
    """Injects current_user into all Jinja2 templates."""
    return {"current_user": g.user if hasattr(g, "user")else None}


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """User Registration / Signup Page."""
    if session.get("user_id"):
        return redirect(url_for("main.home"))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        business_name = request.form.get("business_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not full_name or not email or not password:
            flash("Please fill in all required fields.", "error")
            return render_template(
                "auth/register.html", full_name=full_name, business_name=business_name, email=email)
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template(
                "auth/register.html", full_name=full_name, business_name=business_name, email=email)
        if password != confirm_password:
            flash("Passwords do not match.Please re-enter.", "error")
            return render_template(
                "auth/register.html", full_name=full_name, business_name=business_name, email=email)
        db = get_db()
        existing_user = db.execute(
            "SELECT id FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
        if existing_user:
            flash(
                "An account with this email already exists.Please sign in.",
                "error")
            return redirect(url_for("auth.login"))
        hashed_pw = generate_password_hash(password)
        cur = db.execute("""
            INSERT INTO users (email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
        """, (email, hashed_pw, full_name, 'admin'))
        user_id = cur.lastrowid
        if business_name:
            db.execute("""
                UPDATE freelancer_profile SET full_name = ?, business_name = ?, email = ?
                WHERE id = 1
            """, (full_name, business_name, email))
        else:
            db.execute("""
                UPDATE freelancer_profile SET full_name = ?, email = ?
                WHERE id = 1
            """, (full_name, email))
        db.commit()
        log_activity(
            "REGISTER",
            "USER",
            user_id,
            f"Registered new account {email}")
        session.clear()
        session["user_id"] = user_id
        session["user_email"] = email
        session["user_name"] = full_name
        flash(
            f"Account created successfully! Welcome to your workspace, {full_name}.",
            "success")
        return redirect(url_for("main.home"))
    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User Login Page."""
    if session.get("user_id"):
        return redirect(url_for("main.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "1"
        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("auth/login.html", email=email)
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_name"] = user["full_name"]
            if remember:
                session.permanent = True
            log_activity(
                "LOGIN",
                "USER",
                user["id"],
                f"User {user['email']} logged in successfully")
            flash(f"Welcome back, {user['full_name']}!", "success")
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("main.home"))
        else:
            flash("Invalid email address or password.Please try again.", "error")
            return render_template("auth/login.html", email=email)
    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """User Logout Endpoint."""
    user_id = session.get("user_id")
    if user_id:
        log_activity("LOGOUT", "USER", user_id, "User logged out")
    session.clear()
    flash("You have been signed out safely.", "success")
    return redirect(url_for("auth.login"))
