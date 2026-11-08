# Dream Sport Atelier — Studio Management, Multi-Agent Simulation & Portal Suite

An enterprise-grade, multi-portal studio platform built with **Flask**, **SQLite (WAL mode)**, **Autonomous Simulation Agents**, and a **Semantic Web / Gemini AI Copilot**.

## Multi-Portal Ecosystem
1. **Member Portal (`/member/login` -> `/member/portal`):**
   - Self-service class booking & cancellation
   - Tier-guarded personal coach matching
   - 1-on-1 private training request inbox
   - Clinical mobility & injury restrictions intake
   - Dynamic Apple-Wallet-styled digital QR pass (`/member/<id>/badge`)
   - AI Concierge with Gemini 2.5 Flash & tool calling
2. **Coach Cockpit (`/coach/login` -> `/coach/dashboard`):**
   - Live teaching flight deck & attendance check-ins (Present / No-Show)
   - 1-on-1 student dossier with clinical mobility notes
   - Private session request approval workflow
   - Dynamic commission & performance payout calculator
3. **Executive Console & Financial Ledger (`/admin/login` -> `/admin/overview`, `/admin/finances`):**
   - Studio telemetry and KPI metrics
   - Donut Budget Allocator Simulator with locked contractual payroll & discretionary sliders
   - Master relational matrix for instructors, classes, and tiers
   - Anti-pass-sharing optical reception terminal
   - Indelible studio audit logging

## Quickstart Setup
```bash
unzip dreamsport_complete_v4.zip
cd dreamsport
pip install -r requirements.txt
python app.py
```
Open `http://localhost:5000` (or `http://<your-ip>:5000` across your local Wi-Fi).
Demo logins are pre-loaded on each login portal.
