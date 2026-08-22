# Dayflow — Human Resource Management System

A modern, full-stack HRMS built with **Flask + SQLite + Jinja2** for a hackathon.

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
├── init_db.py          ← Schema creation + seed data
├── requirements.txt
├── templates/
│   ├── base.html       ← Sidebar layout, topbar, flash messages
│   ├── index.html      ← Public landing page
│   ├── login.html      ← Sign-in form
│   ├── signup.html     ← Registration form
│   └── ...             ← Dashboard placeholders (Step 3+)
└── static/css/
    └── main.css        ← Full dark-mode design system
```

## Features Completed

- ✅ Step 1: Scaffold — folder structure, schema, seed data, landing page
- ✅ Step 2: Auth — login, signup, logout, `login_required`, `admin_required`

## Seeded Data

- 1 admin + 5 employees (EMP001–EMP005)
- 7 days of attendance history per employee
- Sample leave requests (Paid / Sick / Unpaid, Pending / Approved)
