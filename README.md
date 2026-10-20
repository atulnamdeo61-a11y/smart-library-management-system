# Smart Library Management System 📚

A modern, full-stack, automated web application for college library operations, book circulation, overdue fine accounting, QR-code book identification, and personalized recommendations.

Built with **Python 3**, **Flask**, **SQLAlchemy ORM**, **MySQL 8.0**, **Bootstrap 5**, and **Chart.js**.

---

## 1. Project Introduction
The **Smart Library Management System** digitizes everyday college library workflows. It bridges student discovery with automated administrative governance, providing dedicated portals for Administrators, Librarians, and Students. The platform eliminates paper circulation logs, automates overdue fine tracking in Indian Rupees (₹2.00/day), tracks stock availability with atomic transactions, generates physical shelf QR labels, and powers explainable book recommendations.

---

## 2. Key Features

### Role-Based Access Control (RBAC)
* **Administrator Portal:** System health metrics, Chart.js analytics, books CRUD with safe soft-deletion, categories, user staff accounts, reports, audit logs, and circulation policy rules.
* **Librarian Portal:** Counter circulation desk, borrow request approval queue, direct issuing, book returns, overdue fines tracking, and receipt recording.
* **Student Portal:** Self-service catalog browsing, one-click borrow requests, active loan countdowns, past borrowing history, fine statements, and personalized reading recommendations.

### Smart Features
* **Scannable QR Codes:** Every book title has an automatically generated QR code linking directly to `/books/<book_id>` for instant smartphone scanning, downloadable PNGs, and printable shelf labels.
* **Personalized Recommendation Engine:** Content-based recommendation algorithm leveraging explicit student category preferences, historical borrow frequencies, and college popularity.
* **Overdue Fine Engine:** Date-only arithmetic ensuring no fine before the due date, freezing fine accrual upon return, and enforcing valid payment limits.
* **Smart In-App Alerts:** Prominent notices for students and librarians displaying days overdue, fine amounts, and return counter instructions.
* **Interactive Dashboard Analytics:** Real-time Chart.js charts for category distributions, 6-month borrowing trends, and loan statuses.

---

## 3. Technology Stack

* **Backend:** Python 3 (3.8+ / 3.14), Flask 3.0.3, Flask-SQLAlchemy 3.1.1, Flask-Login, Flask-WTF, Werkzeug
* **Database:** MySQL 8.0 (Relational database with InnoDB engine, transactions, and foreign keys) / SQLite for zero-config local runs & automated testing
* **Frontend:** HTML5, CSS3 Variables, JavaScript (ES6), Bootstrap 5.3.3, Bootstrap Icons, Jinja2 Templates
* **Visualizations:** Chart.js
* **Book Identification:** Python `qrcode`, `Pillow`
* **Automated Testing:** `pytest` (26 automated test cases)

---

## 4. Architecture Overview

Follows a 5-layer enterprise architecture:
1. **Presentation Layer:** Jinja2 templates, Bootstrap 5, custom CSS design system, and Chart.js.
2. **Application Layer:** Flask Application Factory (`create_app`), Blueprints (`auth`, `books`, `student`, `librarian`, `admin`), CSRF protection, and RBAC decorators.
3. **Service Layer:** Decoupled business logic (`CirculationService`, `FineService`, `RecommendationService`, `QRService`, `AnalyticsService`).
4. **Data Access Layer:** SQLAlchemy ORM models, transaction management, and Alembic database migrations.
5. **Database Layer:** MySQL 8.0 normalized schema with primary keys, foreign keys, and indexes.

Detailed architecture diagrams are available in [`docs/architecture.md`](file:///d:/minor%20project/docs/architecture.md).

---

## 5. Project Folder Structure

```
smart-library/
|-- app/
|   |-- __init__.py                # Application Factory (create_app)
|   |-- extensions.py              # db, login_manager, migrate, csrf
|   |-- config.py                  # Configuration loader
|   |-- cli.py                     # Custom CLI commands (init-db, seed-data, create-admin)
|   |-- models/                    # SQLAlchemy ORM Models
|   |   |-- __init__.py
|   |   |-- user.py                # User & Staff model with password hashing
|   |   |-- category.py            # Academic categories
|   |   |-- book.py                # Book catalog & inventory stock
|   |   |-- book_request.py        # Student borrow request queue
|   |   |-- book_loan.py           # Active & historical circulation loans
|   |   |-- fine.py                # Fine & FinePayment records
|   |   |-- student_preference.py  # Student category interests
|   |   |-- audit_log.py           # Administrative action audit trail
|   |-- auth/                      # Authentication Blueprint
|   |-- books/                     # Book Catalog & QR Blueprint
|   |-- student/                   # Student Self-Service Blueprint
|   |-- librarian/                 # Librarian Counter Desk Blueprint
|   |-- admin/                     # Administrative Control Blueprint
|   |-- services/                  # Business Service Layer
|   |   |-- circulation_service.py # Loans, requests, returns, limit checks
|   |   |-- fine_service.py        # Penalty calculation & payments
|   |   |-- qr_service.py          # QR Code matrix generation
|   |   |-- recommendation_service.py # Smart recommendation algorithm
|   |   |-- analytics_service.py   # Aggregated metrics & Chart.js data
|   |-- templates/                 # Jinja2 Layout & View Templates
|   |-- static/                    # CSS, JS, Uploads, and Generated QR Codes
|-- migrations/                    # Flask-Migrate / Alembic Schema History
|-- tests/                         # Pytest Automated Test Suite
|   |-- conftest.py                # Test fixtures & isolated in-memory DB
|   |-- test_auth.py               # Authentication & password tests
|   |-- test_authorization.py      # RBAC security tests
|   |-- test_books.py              # Book CRUD & validation tests
|   |-- test_circulation.py        # Circulation workflow tests
|   |-- test_fines.py              # Overdue fines & payment tests
|   |-- test_recommendations.py    # Recommendation algorithm tests
|-- docs/                          # Architecture & Database documentation
|-- .env                           # Local environment configuration
|-- .env.example                   # Environment configuration template
|-- requirements.txt               # Pinned Python package dependencies
|-- config.py                      # Root configuration settings
|-- run.py                         # Application entrypoint
|-- README.md                      # Project setup & usage guide
|-- PROJECT_REPORT.md              # Academic minor project report
```

---

## 6. One-Click Run (Recommended)

Simply double-click:
👉 **[`run.bat`](file:///d:/minor%20project/run.bat)** (or [`start_server.bat`](file:///d:/minor%20project/start_server.bat))

What the one-click launcher does automatically:
1. Detects and starts **WampServer** (`C:\wamp64`) in the background if installed.
2. Checks and activates the Python virtual environment (`.venv`).
3. Verifies and initializes the database tables and sample academic data.
4. Automatically opens the website in your default browser.
5. Provides access links:
   * 🌐 **Custom Domain Link:** `http://smartlibrary.local`
   * 🌐 **Localhost Link:** `http://localhost:5000`
   * 🌐 **WampServer Portal:** `http://localhost/smart-library`
   * 🗄️ **phpMyAdmin GUI:** `http://localhost/phpmyadmin`

*(Optional) To enable `http://smartlibrary.local` custom domain mapping:*
Right-click [`setup_custom_domain.bat`](file:///d:/minor%20project/setup_custom_domain.bat) and choose **"Run as Administrator"**.

---

## 7. Manual Installation & Setup Guide

### Step 1: Prerequisites
* Python 3.8 or higher installed on your system.
* MySQL Server 8.0 running locally (or SQLite for immediate testing).

### Step 2: Clone / Open Project
```powershell
cd "d:\minor project"
```

### Step 3: Create & Activate Virtual Environment
```powershell
# Create virtual environment
python -m venv .venv

# Activate on Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

### Step 4: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```

Open `.env` and configure your database settings:
```ini
# Flask Configuration
FLASK_APP=run.py
FLASK_DEBUG=1
SECRET_KEY=college-smart-library-secret-key-2026-production-token

# For MySQL Database:
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/smart_library_db

# Or for zero-config quickstart / testing:
# DATABASE_URL=sqlite:///smart_library.db

# Circulation & Fine Rules
DEFAULT_BORROW_DAYS=14
MAX_ACTIVE_LOANS_PER_STUDENT=3
FINE_RATE_PER_DAY=2.00
FINE_GRACE_PERIOD_DAYS=0
CURRENCY_SYMBOL=₹
```

### Step 6: Create MySQL Database (If using MySQL)
Log into your MySQL client and create the database:
```sql
CREATE DATABASE smart_library_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Step 7: Initialize Database & Seed Demonstration Data
Run the custom CLI commands:
```powershell
# 1. Initialize tables
python -m flask --app run.py init-db

# 2. Seed realistic academic demo books, categories, users, loans, and QR codes
python -m flask --app run.py seed-data
```

*(Optional) Create your custom administrator:*
```powershell
python -m flask --app run.py create-admin
```

### Step 8: Start the Application
```powershell
python run.py
```
Open your browser and navigate to:
👉 **`http://127.0.0.1:5000`**

---

## 7. Evaluator & Viva Demonstration Accounts

The database comes pre-seeded with realistic demonstration accounts:

| Portal | Email | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@college.edu` | `Admin@123` | Full dashboard, Chart.js metrics, user control, book management, fine waivers |
| **Librarian** | `librarian@college.edu` | `Librarian@123` | Circulation counter, approve requests, issue books, process returns, record fine payments |
| **Student** | `aarav.student@college.edu` | `Student@123` | Demonstrates active loan, **6-day overdue alert with fine**, and personalized recommendations |
| **Student 2** | `priya.student@college.edu` | `Student@123` | Demonstrates returned history on-time and recommendations |

---

## 8. Executing Automated Tests

Run the full pytest suite:
```powershell
pytest -v
```

**Expected Result:**
```
======================= 26 passed in 10.43s =======================
```
All 26 automated tests covering authentication, authorization, stock consistency, loan workflows, overdue penalties, and recommendations execute in an isolated in-memory database.

---

## 9. Viva Demonstration Workflow Checklist

Follow this sequence during your college project presentation:
- [x] **1. Homepage:** Open `http://127.0.0.1:5000`. Show the modern hero banner, featured books, and category pills.
- [x] **2. Student Login:** Sign in as `aarav.student@college.edu` (`Student@123`).
- [x] **3. Smart Overdue Notice:** Show the red in-app alert with the **6-day overdue loan** calculated at ₹2/day (₹12.00 fine).
- [x] **4. Recommendations:** Show personalized recommendations matching the student's Computer Science & AI interests with transparent reason chips.
- [x] **5. Book Search & QR Code:** Open Catalog, search for "Algorithms", click Book Details, view stock availability bar, and open the printable Shelf QR Label.
- [x] **6. Request Borrowing:** Submit a borrow request for a book.
- [x] **7. Librarian Approval:** Log out, sign in as `librarian@college.edu` (`Librarian@123`), open Requests Queue, and click **Approve**. Show that available copies immediately decremented by 1.
- [x] **8. Process Return:** Under Active Loans, click **Return Book**. Show that the return date is saved, stock increments back, and the loan is moved to history.
- [x] **9. Record Fine Payment:** Under Fines, record a counter payment (e.g. ₹12.00 Cash) and show status update to **Paid**.
- [x] **10. Admin Analytics:** Sign in as `admin@college.edu` (`Admin@123`). Show the live Chart.js graphs, audit logs, and system rules settings.
- [x] **11. Run Pytest:** Open terminal and run `pytest -v` to prove 26/26 automated tests passing.
