import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, g, session,
    redirect, url_for, request, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash


DATABASE = os.path.join(os.path.dirname(__file__), "database.db")


# ── Decorators ─────────────────────────────────────────────────────────────────

def login_required(f):
    """Redirect to /login if no active session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Return 403 if the logged-in user is not an admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── App factory ────────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)
    app.secret_key = "dayflow-secret-key-change-in-production"

    # ── Database helpers ──────────────────────────────────────────────────────

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(exception):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    app.get_db = get_db

    # ── Context processors ────────────────────────────────────────────────────

    @app.context_processor
    def inject_globals():
        return {"app_name": "Dayflow", "now": datetime.now()}

    # ── Error handlers ────────────────────────────────────────────────────────

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC ROUTES
    # ═══════════════════════════════════════════════════════════════════════════

    @app.route("/")
    def index():
        # Already logged in → skip landing page, go straight to dashboard
        if "user_id" in session:
            if session.get("role") == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("dashboard"))
        return render_template("index.html")

    # ── Login ─────────────────────────────────────────────────────────────────

    @app.route("/login", methods=["GET", "POST"])
    def login():
        # Already logged in
        if "user_id" in session:
            return redirect(url_for("admin_dashboard" if session["role"] == "admin" else "dashboard"))

        if request.method == "POST":
            email    = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not email or not password:
                flash("Please fill in all fields.", "error")
                return render_template("login.html")

            db   = get_db()
            user = db.execute(
                "SELECT * FROM users WHERE LOWER(email) = ?", (email,)
            ).fetchone()

            # Single generic error — don't reveal which field is wrong
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Invalid email or password.", "error")
                return render_template("login.html")

            if user["status"] != "Active":
                flash("Your account is inactive. Please contact HR.", "error")
                return render_template("login.html")

            # Populate session
            session.clear()
            session["user_id"]     = user["id"]
            session["employee_id"] = user["employee_id"]
            session["name"]        = user["name"]
            session["role"]        = user["role"]
            session["email"]       = user["email"]

            flash(f"Welcome back, {user['name'].split()[0]}!", "success")

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    # ── Logout ────────────────────────────────────────────────────────────────

    @app.route("/logout")
    def logout():
        name = session.get("name", "").split()[0]
        session.clear()
        flash(f"You've been logged out{', ' + name if name else ''}. See you soon!", "info")
        return redirect(url_for("login"))

    # ── Sign Up ───────────────────────────────────────────────────────────────

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            employee_id      = request.form.get("employee_id", "").strip().upper()
            name             = request.form.get("name", "").strip()
            email            = request.form.get("email", "").strip().lower()
            password         = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            role             = request.form.get("role", "employee")

            # ── Validation ────────────────────────────────────────────────────
            errors = []

            if not all([employee_id, name, email, password, confirm_password]):
                errors.append("All fields are required.")

            if len(password) < 8:
                errors.append("Password must be at least 8 characters.")

            if password != confirm_password:
                errors.append("Passwords do not match.")

            if role not in ("employee", "admin"):
                errors.append("Invalid role selected.")

            if errors:
                for err in errors:
                    flash(err, "error")
                return render_template("signup.html",
                                       form=request.form)

            db = get_db()

            # Uniqueness checks
            if db.execute("SELECT 1 FROM users WHERE employee_id = ?", (employee_id,)).fetchone():
                flash("Employee ID already exists. Choose a different one.", "error")
                return render_template("signup.html", form=request.form)

            if db.execute("SELECT 1 FROM users WHERE LOWER(email) = ?", (email,)).fetchone():
                flash("An account with that email already exists.", "error")
                return render_template("signup.html", form=request.form)

            # Insert new user
            db.execute(
                """INSERT INTO users
                   (employee_id, name, email, password_hash, role, status)
                   VALUES (?, ?, ?, ?, ?, 'Active')""",
                (employee_id, name, email, generate_password_hash(password), role),
            )
            db.commit()

            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("signup.html", form={})

    # ═══════════════════════════════════════════════════════════════════════════
    # PROTECTED ROUTES  (Step 3 will replace these placeholders)
    # ═══════════════════════════════════════════════════════════════════════════

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("placeholder_dashboard.html")

    @app.route("/admin/dashboard")
    @login_required
    @admin_required
    def admin_dashboard():
        return render_template("placeholder_admin.html")

    # Stub routes referenced in base.html sidebar (prevents BuildError)
    @app.route("/profile")
    @login_required
    def profile():
        return render_template("placeholder_dashboard.html")

    @app.route("/attendance")
    @login_required
    def attendance():
        return render_template("placeholder_dashboard.html")

    @app.route("/leaves")
    @login_required
    def leaves():
        return render_template("placeholder_dashboard.html")

    @app.route("/payroll")
    @login_required
    def payroll():
        return render_template("placeholder_dashboard.html")

    @app.route("/admin")
    @login_required
    @admin_required
    def admin_panel():
        return render_template("placeholder_admin.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
