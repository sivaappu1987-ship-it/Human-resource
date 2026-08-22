import base64
import os
import sqlite3
import time
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, g, session,
    redirect, url_for, request, flash, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), "database.db")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))
        try:
            conn = sqlite3.connect(DATABASE)
            row = conn.execute("SELECT id FROM users WHERE id=?", (session["user_id"],)).fetchone()
            conn.close()
            if not row:
                session.clear()
                flash("Session expired. Please log in again.", "info")
                return redirect(url_for("login"))
        except Exception:
            pass
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
                "profile_picture_url": user["profile_picture_url"] if "profile_picture_url" in user.keys() else None,
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
        if not user:
            session.clear()
            flash("Session expired. Please log in again.", "info")
            return redirect(url_for("login"))

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
        # Ensure column exists if database was created prior
        try:
            db.execute("ALTER TABLE users ADD COLUMN profile_picture_url TEXT")
            db.commit()
        except Exception:
            pass

        if request.method == "POST":
            phone   = request.form.get("phone", "").strip()
            address = request.form.get("address", "").strip()
            pic_url = request.form.get("profile_picture_url", "").strip()
            db.execute("UPDATE users SET phone=?, address=?, profile_picture_url=? WHERE id=?",
                       (phone or None, address or None, pic_url or None, uid))
            db.commit()
            flash("Profile updated successfully!", "success")
            return redirect(url_for("profile"))
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not user:
            session.clear()
            flash("Session expired. Please log in again.", "info")
            return redirect(url_for("login"))
        return render_template("employee/profile.html", user=user)

    @app.route("/profile/upload-photo", methods=["POST"])
    @login_required
    def profile_upload_photo():
        uid = session["user_id"]
        db  = get_db()

        image_data = None
        if request.is_json:
            image_data = (request.json or {}).get("image_data")
        else:
            image_data = request.form.get("image_data")

        file = request.files.get("photo_file")

        uploads_dir = os.path.join(app.static_folder, "uploads", "avatars")
        os.makedirs(uploads_dir, exist_ok=True)

        filename = f"avatar_{uid}_{int(time.time())}.png"
        filepath = os.path.join(uploads_dir, filename)
        url_path = f"/static/uploads/avatars/{filename}"

        if image_data and "base64," in image_data:
            header, encoded = image_data.split("base64,", 1)
            data = base64.b64decode(encoded)
            with open(filepath, "wb") as f:
                f.write(data)
        elif file and file.filename:
            file.save(filepath)
        else:
            if request.is_json:
                return jsonify({"success": False, "error": "No image data provided"}), 400
            flash("No image provided for upload.", "error")
            return redirect(url_for("profile"))

        # Update DB & Session
        db.execute("UPDATE users SET profile_picture_url=? WHERE id=?", (url_path, uid))
        db.commit()
        session["profile_picture_url"] = url_path

        if request.is_json:
            return jsonify({"success": True, "url": url_path})

        flash("Profile photo updated successfully!", "success")
        return redirect(url_for("profile"))

    # ── Attendance status helper ──────────────────────────────────────────────

    def checkin_status(time_str):
        """Determine Present vs Half-day based on check-in time string HH:MM."""
        try:
            h, m = int(time_str[:2]), int(time_str[3:5])
            minutes = h * 60 + m
            return "Present" if minutes <= 9 * 60 + 30 else "Half-day"
        except Exception:
            return "Present"

    # ── Employee Attendance ───────────────────────────────────────────────────

    @app.route("/attendance")
    @login_required
    def attendance():
        db  = get_db()
        uid = session["user_id"]
        today_str = date.today().isoformat()
        today_att = db.execute(
            "SELECT * FROM attendance WHERE user_id=? AND date=?", (uid, today_str)
        ).fetchone()

        view = request.args.get("view", "week")   # "week" or "all"
        if view == "week":
            since = (date.today() - timedelta(days=6)).isoformat()
            records = db.execute(
                "SELECT * FROM attendance WHERE user_id=? AND date>=? ORDER BY date DESC",
                (uid, since)
            ).fetchall()
        else:
            records = db.execute(
                "SELECT * FROM attendance WHERE user_id=? ORDER BY date DESC", (uid,)
            ).fetchall()

        return render_template("employee/attendance.html",
                               today_att=today_att, records=records, view=view)

    @app.route("/attendance/checkin", methods=["POST"])
    @login_required
    def attendance_checkin():
        db  = get_db()
        uid = session["user_id"]
        today_str = date.today().isoformat()

        existing = db.execute(
            "SELECT * FROM attendance WHERE user_id=? AND date=?", (uid, today_str)
        ).fetchone()
        if existing:
            flash("You have already checked in today!", "info")
            return redirect(url_for("attendance"))

        now_time = datetime.now().strftime("%H:%M")
        status   = checkin_status(now_time)
        db.execute(
            "INSERT INTO attendance (user_id, date, check_in, status) VALUES (?,?,?,?)",
            (uid, today_str, now_time, status)
        )
        db.commit()
        flash(f"Checked in at {now_time}. Status: {status}.", "success")
        return redirect(url_for("attendance"))

    @app.route("/attendance/checkout", methods=["POST"])
    @login_required
    def attendance_checkout():
        db  = get_db()
        uid = session["user_id"]
        today_str = date.today().isoformat()

        existing = db.execute(
            "SELECT * FROM attendance WHERE user_id=? AND date=?", (uid, today_str)
        ).fetchone()
        if not existing or not existing["check_in"]:
            flash("Please check in first!", "error")
            return redirect(url_for("attendance"))
        if existing["check_out"]:
            flash("You have already checked out today.", "info")
            return redirect(url_for("attendance"))

        now_time = datetime.now().strftime("%H:%M")
        db.execute(
            "UPDATE attendance SET check_out=? WHERE user_id=? AND date=?",
            (now_time, uid, today_str)
        )
        db.commit()
        flash(f"Checked out at {now_time}. Have a great evening!", "success")
        return redirect(url_for("attendance"))

    # ── Employee Leaves ───────────────────────────────────────────────────────

    @app.route("/leaves")
    @login_required
    def leaves():
        db  = get_db()
        uid = session["user_id"]
        my_leaves = db.execute(
            "SELECT * FROM leaves WHERE user_id=? ORDER BY id DESC", (uid,)
        ).fetchall()
        return render_template("employee/leaves.html", leaves=my_leaves)

    @app.route("/leaves/apply", methods=["POST"])
    @login_required
    def leaves_apply():
        db = get_db()
        uid = session["user_id"]
        leave_type = request.form.get("leave_type", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date   = request.form.get("end_date", "").strip()
        reason     = request.form.get("reason", "").strip()

        if not all([leave_type, start_date, end_date, reason]):
            flash("All fields are required to submit a leave request.", "error")
            return redirect(url_for("leaves"))

        if leave_type not in ("Paid", "Sick", "Unpaid"):
            flash("Invalid leave type selected.", "error")
            return redirect(url_for("leaves"))

        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if e_dt < s_dt:
                flash("End date cannot be earlier than start date.", "error")
                return redirect(url_for("leaves"))
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for("leaves"))

        db.execute(
            """INSERT INTO leaves (user_id, leave_type, start_date, end_date, reason, status)
               VALUES (?, ?, ?, ?, ?, 'Pending')""",
            (uid, leave_type, start_date, end_date, reason)
        )
        db.commit()
        flash("Leave request submitted successfully!", "success")
        return redirect(url_for("leaves"))

    @app.route("/payroll")
    @login_required
    def payroll():
        db  = get_db()
        uid = session["user_id"]
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not user:
            session.clear()
            flash("Session expired. Please log in again.", "info")
            return redirect(url_for("login"))
        return render_template("employee/payroll.html", user=user)

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

    # ── Admin Attendance ──────────────────────────────────────────────────────

    @app.route("/admin/attendance")
    @login_required
    @admin_required
    def admin_attendance():
        db = get_db()
        filter_date = request.args.get("date", date.today().isoformat())

        records = db.execute(
            """SELECT a.*, u.name as emp_name, u.employee_id as emp_code
               FROM attendance a
               JOIN users u ON a.user_id = u.id
               WHERE a.date=?
               ORDER BY u.employee_id""",
            (filter_date,)
        ).fetchall()

        present_count  = sum(1 for r in records if r["status"] == "Present")
        halfday_count  = sum(1 for r in records if r["status"] == "Half-day")
        absent_count   = sum(1 for r in records if r["status"] == "Absent")
        leave_count    = sum(1 for r in records if r["status"] == "Leave")

        return render_template("admin/attendance.html",
                               records=records, filter_date=filter_date,
                               present_count=present_count, halfday_count=halfday_count,
                               absent_count=absent_count, leave_count=leave_count)

    # ── Admin Leaves ──────────────────────────────────────────────────────────

    @app.route("/admin/leaves")
    @login_required
    @admin_required
    def admin_leaves():
        db = get_db()
        filter_status = request.args.get("filter", "pending").lower()

        if filter_status == "pending":
            records = db.execute(
                """SELECT l.*, u.name as emp_name, u.employee_id as emp_code
                   FROM leaves l
                   JOIN users u ON l.user_id = u.id
                   WHERE l.status='Pending'
                   ORDER BY l.id DESC"""
            ).fetchall()
        else:
            records = db.execute(
                """SELECT l.*, u.name as emp_name, u.employee_id as emp_code
                   FROM leaves l
                   JOIN users u ON l.user_id = u.id
                   ORDER BY l.id DESC"""
            ).fetchall()

        pending_count = db.execute(
            "SELECT COUNT(*) as cnt FROM leaves WHERE status='Pending'"
        ).fetchone()["cnt"]
        all_count = db.execute("SELECT COUNT(*) as cnt FROM leaves").fetchone()["cnt"]

        return render_template("admin/leaves.html",
                               records=records, filter_status=filter_status,
                               pending_count=pending_count, all_count=all_count)

    @app.route("/admin/leaves/<int:leave_id>/approve", methods=["POST"])
    @login_required
    @admin_required
    def admin_leave_approve(leave_id):
        db = get_db()
        comment = request.form.get("admin_comment", "").strip() or None

        leave = db.execute("SELECT * FROM leaves WHERE id=?", (leave_id,)).fetchone()
        if not leave:
            flash("Leave request not found.", "error")
            return redirect(url_for("admin_leaves"))

        db.execute(
            "UPDATE leaves SET status='Approved', admin_comment=? WHERE id=?",
            (comment, leave_id)
        )
        db.commit()
        flash(f"Leave request #{leave_id} approved.", "success")
        return redirect(url_for("admin_leaves"))

    @app.route("/admin/leaves/<int:leave_id>/reject", methods=["POST"])
    @login_required
    @admin_required
    def admin_leave_reject(leave_id):
        db = get_db()
        comment = request.form.get("admin_comment", "").strip() or None

        leave = db.execute("SELECT * FROM leaves WHERE id=?", (leave_id,)).fetchone()
        if not leave:
            flash("Leave request not found.", "error")
            return redirect(url_for("admin_leaves"))

        db.execute(
            "UPDATE leaves SET status='Rejected', admin_comment=? WHERE id=?",
            (comment, leave_id)
        )
        db.commit()
        flash(f"Leave request #{leave_id} rejected.", "error")
        return redirect(url_for("admin_leaves"))

    # ── Admin Payroll ──────────────────────────────────────────────────────────

    @app.route("/admin/payroll")
    @login_required
    @admin_required
    def admin_payroll():
        db = get_db()
        payroll_sum = db.execute(
            "SELECT COALESCE(SUM(salary),0) as total FROM users WHERE role='employee'"
        ).fetchone()["total"]
        employees = db.execute(
            """SELECT id, employee_id, name, job_title, department, salary, status
               FROM users WHERE role='employee' ORDER BY employee_id"""
        ).fetchall()
        return render_template("admin/payroll.html",
                               payroll_sum=payroll_sum, employees=employees)

    @app.route("/admin")
    @login_required
    @admin_required
    def admin_panel():
        return redirect(url_for("admin_dashboard"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
