# GymFlow Pro — Enterprise Facility Management & Operational Telemetry Suite

GymFlow Pro is a production-engineered, full-stack gym management platform and operational telemetry system built with Python, Flask, SQLite (WAL mode), Chart.js, and an intent-driven AI operational copilot.

Designed as an end-to-end portfolio masterpiece, this system demonstrates clean relational database design, asynchronous REST API architecture, secure parameterized data layers, automated Apple-Wallet-styled digital badge generation with QR verification, and real-time front desk gate scanning.

---

## System Architecture & Technical Stack

```
GymFlow Pro Architecture
├── Presentation Layer: Responsive HTML5 / CSS3 / Vanilla JS (No bloated frontend frameworks)
│   ├── Executive Telemetry Dashboard (Chart.js visualizations, live gate feed)
│   ├── Member Management Hub (Debounced real-time search, registration modal)
│   └── Front Desk Terminal (Simulated optical/NFC scanner & instant clearance card)
├── Application Layer: Modular Flask REST API
│   ├── Route Controllers (Page rendering with Jinja2 inheritance)
│   ├── RESTful JSON Endpoints (/api/metrics, /api/charts, /api/members, /api/checkin, /api/chat)
│   ├── Dynamic Media Engine (Pillow + qrcode generating on-the-fly digital member passes)
│   └── AI Operational Copilot (Intent classification, entity extraction, parameterized SQL dispatch)
└── Persistence Layer: SQLite in WAL (Write-Ahead-Logging) Mode
    ├── Strict Foreign Key Constraints (PRAGMA foreign_keys = ON)
    ├── High-concurrency read throughput
    └── Index optimization on emails, timestamps, and foreign keys
```

### Why Each Technology Was Selected

| Component | Selected Technology | Engineering Rationale |
| :--- | :--- | :--- |
| **Backend Framework** | **Flask (Python 3)** | Lightweight, highly modular microframework without ORM bloat, allowing explicit control over SQL queries, connection pools, and memory efficiency. |
| **Database Engine** | **SQLite with WAL Mode** | Zero-configuration, serverless, atomic transactions. Configured with `PRAGMA journal_mode = WAL;` to enable concurrent readers alongside writer locks, perfect for operational terminal workloads. |
| **Data Access Layer** | **Raw Parameterized SQL** | Prevents SQL injection vulnerabilities while ensuring total transparency of query execution plans and database joins over heavy ORM abstractions. |
| **AI Copilot** | **Regex & Intent Classification** | Clean, deterministic intent parsing engine mapped directly to safe parameter queries, providing instant query responses without costly external LLM latency. |
| **Digital Badge Engine** | **Pillow + qrcode** | Generates dynamic 2D Apple-Wallet-styled membership passes rendered directly in memory as PNG streams (`io.BytesIO`) without filesystem bottlenecks. |
| **Frontend Visuals** | **Chart.js & CSS Grid** | Hardware-accelerated canvas rendering for high-DPI telemetry charts and sub-millisecond DOM responsiveness. |

---

## Security Implementation

1. **SQL Injection Immunity:** Every single database interaction utilizes prepared statements with parameter placeholders (`?`). No string interpolation (`f"SELECT ... {input}"`) is permitted anywhere in the codebase.
2. **Referential Integrity Enforcement:** SQLite defaults to ignoring foreign keys unless explicitly turned on. `database.py` enforces `PRAGMA foreign_keys = ON;` upon connection instantiation.
3. **Thread-Safe Connection Lifecycle:** Utilizes Flask's application context `g` object (`g.db`), ensuring connections are thread-local and safely torn down via `@app.teardown_appcontext`.
4. **Input Sanitization & Validation:** Registration payloads validate required fields, enforce unique email constraints, and ensure clean integer casting on IDs to prevent type-juggling attacks.
5. **In-Memory Buffer Streaming:** QR badges are generated and transmitted via `io.BytesIO` buffers, avoiding persistent temporary file leaks on the host server.

---

## File Structure & Directory Layout

```text
gym_flow/
├── app.py                 # Core Flask application and RESTful API endpoints
├── database.py            # SQLite connection lifecycle, WAL mode, query helpers
├── models.py              # OOP domain models (Member, Trainer, Plan, CheckIn)
├── chatbot.py             # Intent-driven operational AI Copilot engine
├── schema.sql             # Relational DDL schema with foreign keys and indexes
├── seed.py                # Realistic mock data generator (24 members, 4 plans, 4 coaches, scans)
├── requirements.txt       # Production dependencies
├── README.md              # Complete technical documentation
└── templates/
    ├── base.html          # Global layout template with dark UI, sidebar, and Toastify
    ├── dashboard.html     # Live KPI metrics, Chart.js telemetry, and Copilot drawer
    ├── members.html       # Member roster, live search, onboarding modal, pass export
    └── terminal.html      # Front desk gate scanner simulator with visual clearance card
```

---

## Quickstart & Installation Guide

### 1. Clone or Extract the Suite
```bash
unzip gym_flow_suite.zip
cd gym_flow
```

### 2. Set Up a Python Virtual Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Initialize and Seed the Database
Run the seed script to automatically build `gymflow.db` and populate realistic members, trainers, payment histories, and 7 days of gate check-ins:
```bash
python seed.py
```

### 5. Launch the Application Server
```bash
python app.py
```
Open your browser and navigate to `http://localhost:5000`.

---

## Key Features & Walkthrough

### 1. Operational Command Center (`/`)
* **KPI Metrics:** Live calculation of active enrollments, today's gate check-ins, month-to-date processed revenue, and active instructors.
* **Interactive Data Visualizations:** Dynamic revenue breakdown by tier and weekly check-in frequency powered by Chart.js.
* **Live Facility Stream:** Chronological feed displaying verified gate check-ins in real time.
* **AI Copilot Drawer:** Interactive terminal capable of responding to operational queries (e.g., *"who are the trainers"*, *"summary stats"*, *"revenue"*).

### 2. Member Management Hub (`/members`)
* **Debounced Instant Search:** Search members by first name, last name, email, or badge ID without reloading the page.
* **Onboarding Modal:** Dynamic modal form to register new members, assign certified trainers, select membership plans, and automatically record initial billing.
* **Pass Export:** Direct link to `/member/<id>/badge` which renders a customized Apple-Wallet-styled digital pass with a scannable QR code.

### 3. Front Desk Terminal (`/terminal`)
* **Optical / NFC Scanner Simulator:** Simulates real-world hardware badge readers.
* **Instant Clearance Validation:** Checks membership status, validity, and plan tier in under 15ms. Displays immediate visual status (Access Granted vs Access Denied) accompanied by notification alerts.
