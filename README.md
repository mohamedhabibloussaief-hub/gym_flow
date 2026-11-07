# Dream Sports Atelier — Studio Management, Multi-Agent Simulation & Semantic Web Suite

Dream Sport Atelier is an editorial luxury studio management platform engineered with **Python (Flask)**, **SQLite (WAL Mode)**, **Autonomous Simulation Agents**, and a **Semantic Web Triplestore Copilot**.

---

## System Architecture & Engineering Stack

* **Backend Framework:** Flask (Python 3) with RESTful JSON API controllers and Jinja2 template inheritance.
* **Database Layer:** SQLite configured with `PRAGMA journal_mode = WAL;` and `PRAGMA foreign_keys = ON;`. Includes automatic startup bootstrapping (`ensure_initialized()`) so tables, Membership Plan Tiers, Coaches, Classes, and Members are immediately available on first launch.
* **Autonomous Simulation Engine (`agents.py`):**
  * **Agent 01 (`Coach & Curriculum Agent`):** Generates certified Barre instructors, assigns them to specialized Membership Tiers, and schedules studio classes they lead.
  * **Agent 02 (`Member Onboarding Agent`):** Generates realistic members, assigns them to a Membership Tier and Personal Coach, and records payments and check-in history.
  * **Agent 03 (`Class Enrollment Agent`):** Automatically enrolls active members into scheduled Barre classes while respecting room capacity limits.
* **Semantic Web Copilot (`chatbot.py`):** Tokenizes natural language queries into ontology concepts (`Subject -> Predicate -> Object`) and resolves multi-hop queries across Members, Coaches, Classes, Tiers, and Financials.
* **Editorial Design System:** Inspired by Pure Barre (`#FAF8F5` Alabaster Cream, `#FFFFFF` Pure White, `#141414` Deep Charcoal, `#C8102E` Pure Barre Crimson) paired with `Cormorant Garamond` + `DM Sans` typography.

---

## Quickstart & Local Setup

### 1. Create Virtual Environment & Install Dependencies
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```
Open `http://127.0.0.1:5000` in your browser.
