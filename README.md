# Dayflow — Human Resource Management System

A modern, full-stack HRMS built with **Flask + SQLite + Jinja2** for a hackathon.

## 👥 Team & Roles
- 🗄️ **Database (DB):** `santhosh-p653`
- 🎨 **Frontend:** `rajasekaranmuthuchamy2006-cell`
- ⚙️ **Backend:** `sivaappu1987-ship-it`

## Stack
- **Backend:** Flask 3.0 (app factory pattern)
- **Database:** SQLite via `init_db.py`
- **Templates:** Jinja2
- **Auth:** Flask sessions + Werkzeug password hashing
- **Frontend:** Vanilla HTML / CSS / JS (dark-mode design system)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialise & seed the database
python init_db.py

# 3. Run the development server
python app.py
# → http://127.0.0.1:5000
```

## Demo Credentials

| Role  | Email                  | Password  |
|-------|------------------------|-----------|
| Admin | admin@dayflow.com      | admin123  |
| Employee | ananya.k@dayflow.com | emp001pass |

## Project Structure

```
dayflow/
├── app.py              ← Flask app factory + all routes
├── init_db.py          ← Schema creation + seed data (SQLite)
├── requirements.txt
├── templates/
│   ├── base.html       ← Sidebar layout, topbar, flash messages
│   ├── index.html      ← Public landing page
│   ├── login.html      ← Sign-in form
│   ├── signup.html     ← Registration form
│   ├── admin/          ← Admin dashboard & employee detail editor
│   └── employee/       ← Employee dashboard & profile view
└── static/css/
    └── main.css        ← Full dark-mode design system
```

## Features Completed

- ✅ **Step 1: Scaffold** — folder structure, SQLite schema, seed script, landing page
- ✅ **Step 2: Auth** — login, signup, logout, `login_required`, `admin_required`, custom 403 page
- ✅ **Step 3: Dashboards & Profiles** — Employee dashboard with stats/activity, editable profile (contact only), Admin dashboard with directory & payroll total, Admin employee editor (salary/role/status editing)

## Seeded Data

- 1 admin + 5 employees (EMP001–EMP005)
- 7 days of attendance history per employee
- Sample leave requests (Paid / Sick / Unpaid, Pending / Approved)
