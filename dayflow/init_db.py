"""
init_db.py — Run once to initialise the schema and seed fake data.
Usage:  python init_db.py
"""

import os
import sqlite3
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT    UNIQUE NOT NULL,
    name        TEXT    NOT NULL,
    email       TEXT    UNIQUE NOT NULL,
    password_hash TEXT  NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'employee',
    phone       TEXT,
    address     TEXT,
    job_title   TEXT,
    department  TEXT,
    salary      INTEGER,
    status      TEXT    NOT NULL DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS attendance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    date        DATE    NOT NULL,
    check_in    TIME,
    check_out   TIME,
    status      TEXT    NOT NULL  -- Present | Absent | Half-day | Leave
);

CREATE TABLE IF NOT EXISTS leaves (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    leave_type    TEXT    NOT NULL,  -- Paid | Sick | Unpaid
    start_date    DATE    NOT NULL,
    end_date      DATE    NOT NULL,
    reason        TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'Pending',  -- Pending | Approved | Rejected
    admin_comment TEXT
);
"""

# ── Seed data ─────────────────────────────────────────────────────────────────

EMPLOYEES = [
    {
        "employee_id": "EMP000",
        "name": "Admin User",
        "email": "admin@dayflow.com",
        "password": "admin123",
        "role": "admin",
        "phone": "9876500000",
        "address": "12, Admin Colony, Chennai",
        "job_title": "HR Administrator",
        "department": "Human Resources",
        "salary": 75000,
        "status": "Active",
    },
    {
        "employee_id": "EMP001",
        "name": "Ananya Krishnan",
        "email": "ananya.k@dayflow.com",
        "password": "emp001pass",
        "role": "employee",
        "phone": "9876501001",
        "address": "45, Anna Nagar, Chennai",
        "job_title": "Software Engineer",
        "department": "Engineering",
        "salary": 45000,
        "status": "Active",
    },
    {
        "employee_id": "EMP002",
        "name": "Rahul Mehta",
        "email": "rahul.m@dayflow.com",
        "password": "emp002pass",
        "role": "employee",
        "phone": "9876501002",
        "address": "78, Koramangala, Bengaluru",
        "job_title": "UI/UX Designer",
        "department": "Design",
        "salary": 38000,
        "status": "Active",
    },
    {
        "employee_id": "EMP003",
        "name": "Priya Sharma",
        "email": "priya.s@dayflow.com",
        "password": "emp003pass",
        "role": "employee",
        "phone": "9876501003",
        "address": "22, Banjara Hills, Hyderabad",
        "job_title": "Data Analyst",
        "department": "Analytics",
        "salary": 42000,
        "status": "Active",
    },
    {
        "employee_id": "EMP004",
        "name": "Vikram Nair",
        "email": "vikram.n@dayflow.com",
        "password": "emp004pass",
        "role": "employee",
        "phone": "9876501004",
        "address": "5, Marine Drive, Kochi",
        "job_title": "DevOps Engineer",
        "department": "Infrastructure",
        "salary": 48000,
        "status": "Active",
    },
    {
        "employee_id": "EMP005",
        "name": "Sneha Iyer",
        "email": "sneha.i@dayflow.com",
        "password": "emp005pass",
        "role": "employee",
        "phone": "9876501005",
        "address": "90, T. Nagar, Chennai",
        "job_title": "Business Analyst",
        "department": "Operations",
        "salary": 35000,
        "status": "Active",
    },
]

# Last 7 calendar days (Mon–Sun mix)
def last_7_days():
    today = date.today()
    return [today - timedelta(days=i) for i in range(6, -1, -1)]

# Attendance pattern per employee index (0=admin skipped, 1-5 seeded)
# P=Present, A=Absent, H=Half-day
ATTENDANCE_PATTERNS = {
    "EMP001": ["P", "P", "P", "A", "P", "P", "P"],
    "EMP002": ["P", "H", "P", "P", "P", "A", "P"],
    "EMP003": ["P", "P", "A", "P", "P", "P", "H"],
    "EMP004": ["A", "P", "P", "P", "H", "P", "P"],
    "EMP005": ["P", "P", "P", "P", "P", "P", "A"],
}

STATUS_MAP = {"P": "Present", "A": "Absent", "H": "Half-day"}
CHECK_IN_MAP  = {"P": "09:00", "H": "13:00", "A": None}
CHECK_OUT_MAP = {"P": "18:00", "H": "18:00", "A": None}


def seed_attendance(conn, user_id, emp_id):
    days = last_7_days()
    pattern = ATTENDANCE_PATTERNS.get(emp_id, ["P"] * 7)
    for day, code in zip(days, pattern):
        conn.execute(
            """INSERT INTO attendance (user_id, date, check_in, check_out, status)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, day.isoformat(), CHECK_IN_MAP[code], CHECK_OUT_MAP[code], STATUS_MAP[code]),
        )


LEAVE_SEEDS = [
    # (emp_id_index, leave_type, start_offset, end_offset, reason, status, comment)
    ("EMP002", "Sick",   -10, -9,  "High fever and flu",            "Approved", "Approved. Get well soon!"),
    ("EMP003", "Paid",    3,   5,  "Family function in hometown",    "Pending",  None),
    ("EMP005", "Unpaid", -3,  -3,  "Personal errand",               "Approved", "Approved as per leave balance"),
    ("EMP001", "Paid",    7,  10,  "Annual vacation — Ooty trip",   "Pending",  None),
]


def seed_leaves(conn, emp_id_to_user_id):
    today = date.today()
    for emp_id, ltype, sd_off, ed_off, reason, status, comment in LEAVE_SEEDS:
        uid = emp_id_to_user_id.get(emp_id)
        if uid is None:
            continue
        start = (today + timedelta(days=sd_off)).isoformat()
        end   = (today + timedelta(days=ed_off)).isoformat()
        conn.execute(
            """INSERT INTO leaves
               (user_id, leave_type, start_date, end_date, reason, status, admin_comment)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uid, ltype, start, end, reason, status, comment),
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[init_db] Removed old {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    print("[init_db] Schema created.")

    emp_id_to_user_id = {}

    for emp in EMPLOYEES:
        cur = conn.execute(
            """INSERT INTO users
               (employee_id, name, email, password_hash, role,
                phone, address, job_title, department, salary, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                emp["employee_id"],
                emp["name"],
                emp["email"],
                generate_password_hash(emp["password"]),
                emp["role"],
                emp["phone"],
                emp["address"],
                emp["job_title"],
                emp["department"],
                emp["salary"],
                emp["status"],
            ),
        )
        user_id = cur.lastrowid
        emp_id_to_user_id[emp["employee_id"]] = user_id
        print(f"  + User {emp['employee_id']} ({emp['name']}) -> id={user_id}")

    # Seed attendance for EMP001–EMP005 only
    for emp in EMPLOYEES[1:]:
        seed_attendance(conn, emp_id_to_user_id[emp["employee_id"]], emp["employee_id"])
    print("[init_db] Attendance seeded for EMP001–EMP005.")

    seed_leaves(conn, emp_id_to_user_id)
    print("[init_db] Leave requests seeded.")

    conn.commit()
    conn.close()
    print(f"\nDone! Database ready at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
