import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask, render_template, g, session,
    redirect, url_for, request, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), "database.db")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def create_app():
    app = Flask(__name__)
    app.secret_key = "dayflow-secret-key-change-in-production"

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

    # ── Template filters ──────────────────────────────────────────────────────

    @app.template_filter("inr")
    def format_inr(value):
        if value is None:
            return "—"
        return f"\u20b9{int(value):,}"

    @app.template_filter("status_badge")
    def status_badge(status):
        m = {
            "Present": "green", "Absent": "red", "Half-day": "amber",
            "Leave": "purple", "Approved": "green", "Pending": "amber",
            "Rejected": "red", "Active": "green", "Inactive": "red",
        }
        return m.get(status, "muted")

    @app.template_filter("friendly_date")
    def friendly_date(val):
        if not val:
            return "—"
        try:
            return datetime.strptime(str(val), "%Y-%m-%d").strftime("%d %b %Y")
        except Exception:
            return str(val)

    # ── Context processors ────────────────────────────────────────────────────

    @app.context_processor
    def inject_globals():
        return {"app_name": "Dayflow", "now": datetime.now(), "today": date.today()}

    # ── Error handlers ────────────────────────────────────────────────────────

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("403.html"), 404   # reuse style, change copy later

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC ROUTES
    # ═══════════════════════════════════════════════════════════════════════════

    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("admin_dashboard" if session["role"] == "admin" else "dashboard"))
        return render_template("index.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if "user_id" in session:
            return redirect(url_for("admin_dashboard" if session["role"] == "admin" else "dashboard"))
        if request.method == "POST":
            email    = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not email or not password:
                flash("Please fill in all fields.", "error")
                return render_template("login.html")
            db   = get_db()
            user = db.execute("SELECT * FROM users WHERE LOWER(email)=?", (email,)).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Invalid email or password.", "error")
                return render_template("login.html")
            if user["status"] != "Active":
                flash("Your account is inactive. Please contact HR.", "error")
                return render_template("login.html")
            session.clear()
            session.update({
                "user_id": user["id"], "employee_id": user["employee_id"],
                "name": user["name"], "role": user["role"], "email": user["email"],
            })
            flash(f"Welcome back, {user['name'].split()[0]}!", "success")
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "dashboard"))
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        name = session.get("name", "").split()[0]
        session.clear()
        flash(f"Logged out{(', ' + name) if name else ''}. See you soon!", "info")
        return redirect(url_for("login"))

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            eid  = request.form.get("employee_id", "").strip().upper()
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            pw   = request.form.get("password", "")
            pw2  = request.form.get("confirm_password", "")
            role = request.form.get("role", "employee")
            if not all([eid, name, email, pw, pw2]):
                flash("All fields are required.", "error")
                return render_template("signup.html", form=request.form)
            if len(pw) < 8:
                flash("Password must be at least 8 characters.", "error")
                return render_template("signup.html", form=request.form)
            if pw != pw2:
                flash("Passwords do not match.", "error")
                return render_template("signup.html", form=request.form)
            if role not in ("employee", "admin"):
                flash("Invalid role.", "error")
                return render_template("signup.html", form=request.form)
            db = get_db()
            if db.execute("SELECT 1 FROM users WHERE employee_id=?", (eid,)).fetchone():
                flash("Employee ID already exists.", "error")
                return render_template("signup.html", form=request.form)
            if db.execute("SELECT 1 FROM users WHERE LOWER(email)=?", (email,)).fetchone():
                flash("Email already registered.", "error")
                return render_template("signup.html", form=request.form)
            db.execute(
                "INSERT INTO users (employee_id,name,email,password_hash,role,status) VALUES(?,?,?,?,?,'Active')",
                (eid, name, email, generate_password_hash(pw), role),
            )
            db.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        return render_template("signup.html", form={})

    # ═══════════════════════════════════════════════════════════════════════════
    # EMPLOYEE ROUTES
    # ═══════════════════════════════════════════════════════════════════════════

    @app.route("/dashboard")
    @login_required
    def dashboard():
        db  = get_db()
        uid = session["user_id"]
        today_str = date.today().isoformat()

        user         = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        today_att    = db.execute(
            "SELECT * FROM attendance WHERE user_id=? AND date=?", (uid, today_str)
        ).fetchone()
        pending_leaves = db.execute(
            "SELECT COUNT(*) as cnt FROM leaves WHERE user_id=? AND status='Pending'", (uid,)
        ).fetchone()["cnt"]
        recent_att   = db.execute(
            "SELECT * FROM attendance WHERE user_id=? ORDER BY date DESC LIMIT 5", (uid,)
        ).fetchall()

        return render_template("employee/dashboard.html",
                               user=user, today_att=today_att,
                               pending_leaves=pending_leaves, recent_att=recent_att)

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        db  = get_db()
        uid = session["user_id"]
        if request.method == "POST":
            phone   = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()
            db.execute("UPDATE users SET phone=?, address=? WHERE id=?",
                       (phone or None, address or None, uid))
            db.commit()
            flash("Profile updated successfully!", "success")
            return redirect(url_for("profile"))
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return render_template("employee/profile.html", user=user)

    # Stubs for Step 4 / 5
    @app.route("/attendance")
    @login_required
    def attendance():
        return render_template("employee/dashboard.html",
                               user=get_db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone(),
                               today_att=None, pending_leaves=0, recent_att=[])

    @app.route("/leaves")
    @login_required
    def leaves():
        return redirect(url_for("dashboard"))

    @app.route("/payroll")
    @login_required
    def payroll():
        return redirect(url_for("dashboard"))

    # ═══════════════════════════════════════════════════════════════════════════
    # ADMIN ROUTES
    # ═══════════════════════════════════════════════════════════════════════════

    @app.route("/admin/dashboard")
    @login_required
    @admin_required
    def admin_dashboard():
        db = get_db()
        today_str = date.today().isoformat()

        total_emp    = db.execute("SELECT COUNT(*) as cnt FROM users WHERE role='employee'").fetchone()["cnt"]
        present_today = db.execute(
            "SELECT COUNT(*) as cnt FROM attendance WHERE date=? AND status='Present'", (today_str,)
        ).fetchone()["cnt"]
        pending_leaves = db.execute(
            "SELECT COUNT(*) as cnt FROM leaves WHERE status='Pending'"
        ).fetchone()["cnt"]
        payroll_sum  = db.execute(
            "SELECT COALESCE(SUM(salary),0) as total FROM users WHERE role='employee'"
        ).fetchone()["total"]
        employees    = db.execute(
            "SELECT id,employee_id,name,job_title,department,salary,status FROM users WHERE role='employee' ORDER BY employee_id"
        ).fetchall()

        return render_template("admin/dashboard.html",
                               total_emp=total_emp, present_today=present_today,
                               pending_leaves=pending_leaves, payroll_sum=payroll_sum,
                               employees=employees)

    @app.route("/admin/employee/<int:emp_id>", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_employee_detail(emp_id):
        db  = get_db()
        emp = db.execute("SELECT * FROM users WHERE id=?", (emp_id,)).fetchone()
        if emp is None:
            abort(404)

        if request.method == "POST":
            name       = request.form.get("name", "").strip()
            email      = request.form.get("email", "").strip().lower()
            phone      = request.form.get("phone", "").strip()
            address    = request.form.get("address", "").strip()
            job_title  = request.form.get("job_title", "").strip()
            department = request.form.get("department", "").strip()
            status     = request.form.get("status", "Active")
            salary_raw = request.form.get("salary", "").strip()

            try:
                salary = int(salary_raw)
                if salary < 0:
                    raise ValueError
            except (ValueError, TypeError):
                flash("Salary must be a positive whole number.", "error")
                return render_template("admin/employee_detail.html", emp=emp)

            conflict = db.execute(
                "SELECT id FROM users WHERE LOWER(email)=? AND id!=?", (email, emp_id)
            ).fetchone()
            if conflict:
                flash("That email is already in use.", "error")
                return render_template("admin/employee_detail.html", emp=emp)

            db.execute(
                """UPDATE users SET name=?,email=?,phone=?,address=?,
                   job_title=?,department=?,salary=?,status=? WHERE id=?""",
                (name, email, phone or None, address or None,
                 job_title or None, department or None, salary, status, emp_id)
            )
            db.commit()
            flash(f"{name}'s profile updated successfully!", "success")
            return redirect(url_for("admin_employee_detail", emp_id=emp_id))

        return render_template("admin/employee_detail.html", emp=emp)

    @app.route("/admin")
    @login_required
    @admin_required
    def admin_panel():
        return redirect(url_for("admin_dashboard"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
