from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import io
import qrcode
from PIL import Image, ImageDraw
import os

from database import close_db, query_db, execute_db, get_db, ensure_initialized, log_audit
from models import User, Member, Trainer, StudioClass, MembershipPlan, CheckInManager
from chatbot import DreamSportCopilot
from agents import StudioSimulationAgents

app = Flask(__name__)
app.config["SECRET_KEY"] = "dreamsport-secret-enterprise-key-2026"
app.teardown_appcontext(close_db)

ensure_initialized()
copilot = DreamSportCopilot()

# ================= AUTHENTICATION ROUTES =================

@app.route("/")
def home():
    if "user_id" in session:
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_dashboard"))
        elif role == "coach":
            return redirect(url_for("coach_dashboard"))
        else:
            return redirect(url_for("member_portal"))
    return redirect(url_for("member_login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("member_login"))

@app.route("/member/login", methods=["GET", "POST"])
def member_login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pwd = request.form.get("password", "")
        user = User.authenticate(email, pwd)
        if user and user["role"] == "member":
            session["user_id"] = user["id"]
            session["role"] = "member"
            session["linked_id"] = user["linked_id"]
            session["username"] = user["username"]
            log_audit("MEMBER_LOGIN", "member", user["username"], "Signed in to Member Portal")
            return redirect(url_for("member_portal"))
        error = "Invalid member email or password."
    sample_members = query_db("SELECT u.email, m.fname || ' ' || m.lname as name, p.name as plan FROM users u JOIN members m ON u.linked_id = m.id JOIN membership_plans p ON m.plan_id = p.id WHERE u.role = 'member' LIMIT 3")
    return render_template("member_login.html", error=error, samples=sample_members)

@app.route("/coach/login", methods=["GET", "POST"])
def coach_login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pwd = request.form.get("password", "")
        user = User.authenticate(email, pwd)
        if user and user["role"] == "coach":
            session["user_id"] = user["id"]
            session["role"] = "coach"
            session["linked_id"] = user["linked_id"]
            session["username"] = user["username"]
            log_audit("COACH_LOGIN", "coach", user["username"], "Signed in to Coach Cockpit")
            return redirect(url_for("coach_dashboard"))
        error = "Invalid coach credentials or unauthorized staff role."
    sample_coaches = query_db("SELECT u.email, t.fname || ' ' || t.lname as name, t.specialty FROM users u JOIN trainers t ON u.linked_id = t.id WHERE u.role = 'coach' LIMIT 3")
    return render_template("coach_login.html", error=error, samples=sample_coaches)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pwd = request.form.get("password", "")
        user = User.authenticate(email, pwd)
        if user and user["role"] == "admin":
            session["user_id"] = user["id"]
            session["role"] = "admin"
            session["linked_id"] = None
            session["username"] = user["username"]
            log_audit("ADMIN_LOGIN", "admin", user["username"], "Signed in to Studio Executive Console")
            return redirect(url_for("admin_dashboard"))
        error = "Invalid administrative credentials."
    return render_template("admin_login.html", error=error)

# ================= PORTAL VIEWS =================

@app.route("/member/portal")
def member_portal():
    if session.get("role") != "member":
        return redirect(url_for("member_login"))
    member_id = session.get("linked_id")
    member = Member.find_by_id(member_id)
    if not member:
        return redirect(url_for("member_login"))
    all_classes = StudioClass.get_all()
    all_coaches = Trainer.get_all()
    all_plans = MembershipPlan.get_all()
    return render_template("member_portal.html", member=member, classes=all_classes, coaches=all_coaches, plans=all_plans)

@app.route("/coach/dashboard")
def coach_dashboard():
    if session.get("role") != "coach":
        return redirect(url_for("coach_login"))
    trainer_id = session.get("linked_id")
    coach = Trainer.get_by_id(trainer_id)
    if not coach:
        return redirect(url_for("coach_login"))
    
    all_classes = StudioClass.get_all()
    my_classes = [c for c in all_classes if c["trainer_id"] == trainer_id]
    
    clients = query_db("""
        SELECT m.*, p.name as plan_name, p.price as plan_price
        FROM members m
        JOIN membership_plans p ON m.plan_id = p.id
        WHERE m.trainer_id = ?
    """, (trainer_id,))
    
    private_reqs = query_db("""
        SELECT ps.*, m.fname || ' ' || m.lname as member_name, m.email, m.phone, m.injury_notes
        FROM private_sessions ps
        JOIN members m ON ps.member_id = m.id
        WHERE ps.trainer_id = ?
        ORDER BY ps.session_datetime ASC
    """, (trainer_id,))
    
    client_vol = sum([c["plan_price"] for c in clients if c["status"] == "Active"])
    completed_private = len([r for r in private_reqs if r["status"] == "Completed"])
    earned_comm = (client_vol * coach["commission_rate"]) + (completed_private * coach["private_session_rate"] * 0.70)
    
    return render_template(
        "coach_dashboard.html",
        coach=coach,
        classes=my_classes,
        clients=[dict(c) for c in clients],
        requests=[dict(r) for r in private_reqs],
        earned_comm=earned_comm,
        client_vol=client_vol,
        completed_private=completed_private
    )

@app.route("/admin/overview")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("admin_login"))
    plans = MembershipPlan.get_all()
    trainers = Trainer.get_all()
    classes = StudioClass.get_all()
    audit_events = query_db("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 15")
    return render_template("dashboard.html", active_page="dashboard", plans=plans, trainers=trainers, classes=classes, audit_events=audit_events)

@app.route("/admin/finances")
def admin_finances():
    if session.get("role") != "admin":
        return redirect(url_for("admin_login"))
    trainers = Trainer.get_all()
    plans = MembershipPlan.get_all()
    
    gross_rev = query_db("SELECT COALESCE(SUM(amount), 0) as s FROM payments", one=True)["s"]
    total_staff_payroll = sum([t["total_payout"] for t in trainers])
    total_commissions = sum([t["earned_commission"] for t in trainers])
    total_retainers = sum([t["base_retainer"] for t in trainers])
    locked_pct = round((total_staff_payroll / gross_rev * 100), 1) if gross_rev > 0 else 50.0

    execute_db("""
        CREATE TABLE IF NOT EXISTS budget_allocations (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            clean REAL DEFAULT 8,
            rent REAL DEFAULT 18,
            equip REAL DEFAULT 12,
            emerg REAL DEFAULT 7,
            profit REAL DEFAULT 5
        )
    """)
    row = query_db("SELECT * FROM budget_allocations WHERE id = 1", one=True)
    if not row:
        execute_db("INSERT INTO budget_allocations (id, clean, rent, equip, emerg, profit) VALUES (1, 8, 18, 12, 7, 5)")
        row = query_db("SELECT * FROM budget_allocations WHERE id = 1", one=True)
    budget = dict(row)
    
    return render_template(
        "admin_finances.html",
        active_page="finances",
        trainers=trainers,
        plans=plans,
        gross_rev=gross_rev,
        total_staff_payroll=total_staff_payroll,
        total_commissions=total_commissions,
        total_retainers=total_retainers,
        locked_pct=locked_pct,
        budget=budget
    )
@app.route("/admin/studio")
def admin_studio():
    if session.get("role") != "admin":
        return redirect(url_for("admin_login"))
    plans = MembershipPlan.get_all()
    trainers = Trainer.get_all()
    classes = StudioClass.get_all()
    # Ensure enrolled_members alias is present for studio.html
    for c in classes:
        c["enrolled_members"] = c.get("roster", [])
    members = Member.search("")
    return render_template("studio.html", active_page="studio", plans=plans, trainers=trainers, classes=classes, members=members)

@app.route("/admin/members")
def admin_members():
    if session.get("role") != "admin":
        return redirect(url_for("admin_login"))
    members = Member.search("")
    plans = MembershipPlan.get_all()
    trainers = Trainer.get_all()
    classes = StudioClass.get_all()
    return render_template("members.html", active_page="members", members=members, plans=plans, trainers=trainers, classes=classes)

@app.route("/terminal")
def terminal_page():
    members = Member.search("")[:8]
    return render_template("terminal.html", active_page="terminal", sample_members=members)

# ================= REST APIS (FIXED & COMPLETE) =================

@app.route("/api/live-sync")
def api_live_sync():
    total_active = query_db("SELECT COUNT(*) as c FROM members WHERE status = 'Active'", one=True)["c"]
    total_checkins = query_db("SELECT COUNT(*) as c FROM checkins WHERE DATE(checkin_time) = DATE('now')", one=True)["c"]
    total_enrollments = query_db("SELECT COUNT(*) as c FROM class_enrollments", one=True)["c"]
    return jsonify({
        "total_active": total_active,
        "total_checkins": total_checkins,
        "total_enrollments": total_enrollments,
        "timestamp": query_db("SELECT CURRENT_TIMESTAMP as t", one=True)["t"]
    })

@app.route("/api/metrics")
def api_metrics():
    """Populates KPI cards and Studio Class Schedule table on /admin/overview."""
    total_active = query_db("SELECT COUNT(*) as c FROM members WHERE status = 'Active'", one=True)["c"]
    total_enrollments = query_db("SELECT COUNT(*) as c FROM class_enrollments", one=True)["c"]
    monthly_rev = query_db("SELECT COALESCE(SUM(amount), 0) as s FROM payments", one=True)["s"]
    active_trainers = query_db("SELECT COUNT(*) as c FROM trainers WHERE is_active = 1", one=True)["c"]
    classes = StudioClass.get_all()
    return jsonify({
        "total_active": total_active,
        "total_enrollments": total_enrollments,
        "monthly_rev": float(monthly_rev or 0),
        "active_trainers": active_trainers,
        "classes": classes
    })

@app.route("/api/charts/revenue")
def api_charts_revenue():
    """Populates Revenue by Membership Tier chart on /admin/overview."""
    rows = query_db("""
        SELECT p.name,
               COALESCE(SUM(CASE WHEN m.status = 'Active' THEN p.price ELSE 0 END), 0) as rev
        FROM membership_plans p
        LEFT JOIN members m ON m.plan_id = p.id
        GROUP BY p.id, p.name
        ORDER BY p.price ASC
    """)
    labels = [r["name"].replace(" (", "\n(") for r in rows]
    values = [float(r["rev"]) for r in rows]
    return jsonify({"labels": labels, "values": values})

@app.route("/api/charts/traffic")
def api_charts_traffic():
    """Populates 7-Day Studio Attendance chart on /admin/overview."""
    labels = []
    values = []
    now = datetime.now()
    for i in range(6, -1, -1):
        day_dt = now - timedelta(days=i)
        day_str = day_dt.strftime("%Y-%m-%d")
        label = day_dt.strftime("%a %d")
        row = query_db(
            "SELECT COUNT(*) as c FROM checkins WHERE DATE(checkin_time) = ?",
            (day_str,),
            one=True
        )
        labels.append(label)
        values.append(int(row["c"]) if row else 0)
    return jsonify({"labels": labels, "values": values})

@app.route("/api/members", methods=["GET", "POST"])
def api_members():
    """Handles searching the Member Roster (GET) and onboarding new members (POST)."""
    if request.method == "GET":
        q = request.args.get("q", "").strip()
        members = Member.search(q)
        return jsonify({"members": members})

    data = request.json or {}
    fname = (data.get("fname") or "").strip()
    lname = (data.get("lname") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "+216 00 000 000").strip()
    gender = data.get("gender") or "Female"
    plan_id = int(data.get("plan_id") or 1)
    trainer_id = data.get("trainer_id")
    trainer_id = int(trainer_id) if trainer_id not in (None, "", "null") else None
    class_id = data.get("class_id")
    class_id = int(class_id) if class_id not in (None, "", "null") else None

    if not fname or not lname or not email:
        return jsonify({"success": False, "error": "First name, last name, and email are required."}), 400

    existing = query_db("SELECT id FROM members WHERE LOWER(email) = ?", (email,), one=True)
    if existing:
        return jsonify({"success": False, "error": "A member with this email already exists."}), 400

    try:
        mid = execute_db("""
            INSERT INTO members (fname, lname, gender, date_birth, email, phone, plan_id, trainer_id, status, injury_notes)
            VALUES (?, ?, ?, '1996-05-15', ?, ?, ?, ?, 'Active', '')
        """, (fname, lname, gender, email, phone, plan_id, trainer_id))

        username = f"{fname.lower()}_{lname.lower()}_{mid}"
        execute_db("""
            INSERT INTO users (username, email, password_hash, role, linked_id)
            VALUES (?, ?, ?, 'member', ?)
        """, (username, email, generate_password_hash("member123"), mid))

        plan_row = query_db("SELECT price FROM membership_plans WHERE id = ?", (plan_id,), one=True)
        plan_price = plan_row["price"] if plan_row else 159.0
        execute_db(
            "INSERT INTO payments (member_id, amount, pay_method) VALUES (?, ?, 'card')",
            (mid, plan_price)
        )

        if class_id:
            StudioClass.enroll_member(class_id, mid)

        log_audit("ADMIN_ONBOARD_MEMBER", "admin", session.get("username", "admin"), f"Onboarded {fname} {lname} (#{mid})")
        return jsonify({"success": True, "member_id": mid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/members/<int:member_id>/update", methods=["POST"])
def api_member_update(member_id):
    """Handles inline edits for Plan Tier, Assigned Coach, and Status in /admin/members."""
    data = request.json or {}
    if "plan_id" in data and data["plan_id"] not in (None, ""):
        execute_db("UPDATE members SET plan_id = ? WHERE id = ?", (int(data["plan_id"]), member_id))
    if "trainer_id" in data:
        tid = int(data["trainer_id"]) if str(data["trainer_id"]).strip() != "" else None
        execute_db("UPDATE members SET trainer_id = ? WHERE id = ?", (tid, member_id))
    if "status" in data and data["status"]:
        execute_db("UPDATE members SET status = ? WHERE id = ?", (data["status"], member_id))
    log_audit("ADMIN_UPDATE_MEMBER", "admin", session.get("username", "admin"), f"Updated Member #{member_id}: {data}")
    return jsonify({"success": True})

@app.route("/api/trainers/<int:trainer_id>/update", methods=["POST"])
def api_trainer_update(trainer_id):
    """Updates coach tier assignment in /admin/studio."""
    data = request.json or {}
    plan_id = data.get("plan_id")
    Trainer.update_settings(trainer_id, plan_id=plan_id if plan_id is not None else "")
    log_audit("ADMIN_UPDATE_COACH", "admin", session.get("username", "admin"), f"Updated Coach #{trainer_id} tier")
    return jsonify({"success": True})

@app.route("/api/classes/<int:class_id>/update", methods=["POST"])
def api_class_update(class_id):
    """Updates class lead instructor and target tier in /admin/studio."""
    data = request.json or {}
    if "trainer_id" in data:
        tid = int(data["trainer_id"]) if data["trainer_id"] not in (None, "", "null") else None
        execute_db("UPDATE studio_classes SET trainer_id = ? WHERE id = ?", (tid, class_id))
    if "plan_id" in data and data["plan_id"] is not None:
        pid = int(data["plan_id"]) if str(data["plan_id"]).strip() not in ("", "null") else None
        execute_db("UPDATE studio_classes SET plan_id = ? WHERE id = ?", (pid, class_id))
    log_audit("ADMIN_UPDATE_CLASS", "admin", session.get("username", "admin"), f"Updated Class #{class_id}")
    return jsonify({"success": True})

@app.route("/api/plans", methods=["POST"])
def api_create_plan():
    """Creates a new membership tier from /admin/studio."""
    data = request.json or {}
    name = (data.get("name") or "").strip()
    price = float(data.get("price") or 140)
    duration = int(data.get("duration_months") or 1)
    perks = data.get("perks") or "Custom Studio Tier"
    if not name:
        return jsonify({"success": False, "error": "Tier name required"}), 400
    pid = MembershipPlan.create(name, duration, price, 8, perks)
    log_audit("ADMIN_CREATE_PLAN", "admin", session.get("username", "admin"), f"Created Plan Tier {name} (${price})")
    return jsonify({"success": True, "plan_id": pid})

@app.route("/api/plans/<int:plan_id>/update", methods=["POST"])
def api_update_plan(plan_id):
    data = request.json or {}
    name = (data.get("name") or "").strip()
    price = float(data.get("price") or 0)
    if not name or price <= 0:
        return jsonify({"success": False, "error": "Valid name and price required"}), 400
    execute_db("UPDATE membership_plans SET name = ?, price = ? WHERE id = ?", (name, price, plan_id))
    log_audit("ADMIN_UPDATE_PLAN", "admin", session.get("username", "admin"), f"Updated Plan #{plan_id} to {name} (${price}/mo)")
    return jsonify({"success": True})

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json or {}
    user_msg = data.get("message", "")
    role = session.get("role", "admin")
    user_id = session.get("user_id")
    linked_id = session.get("linked_id")
    res = copilot.handle_query(user_msg, {"role": role, "user_id": user_id, "linked_id": linked_id})
    return jsonify(res)

@app.route("/api/checkin", methods=["POST"])
def api_checkin():
    data = request.json or {}
    mid = data.get("member_id")
    if not mid:
        return jsonify({"success": False, "error": "Member ID required"}), 400
    try:
        mid = int(mid)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid format"}), 400
    result = CheckInManager.record_checkin(mid)
    return jsonify(result), (200 if result["success"] else 400)

@app.route("/api/members/switch-coach", methods=["POST"])
def api_switch_coach():
    data = request.json or {}
    mid = session.get("linked_id") if session.get("role") == "member" else data.get("member_id")
    target_coach_id = data.get("trainer_id")
    res = Member.switch_coach(mid, target_coach_id)
    return jsonify(res), (200 if res["success"] else 400)

@app.route("/api/members/update-health", methods=["POST"])
def api_update_health():
    data = request.json or {}
    mid = session.get("linked_id") if session.get("role") == "member" else data.get("member_id")
    notes = data.get("injury_notes", "")
    res = Member.update_injury_notes(mid, notes)
    return jsonify(res)

@app.route("/api/classes/enroll", methods=["POST"])
def api_classes_enroll():
    data = request.json or {}
    mid = session.get("linked_id") if session.get("role") == "member" else data.get("member_id")
    cid = data.get("class_id")
    res = StudioClass.enroll_member(int(cid), int(mid))
    return jsonify(res), (200 if res["success"] else 400)

@app.route("/api/classes/unenroll", methods=["POST"])
def api_classes_unenroll():
    data = request.json or {}
    mid = session.get("linked_id") if session.get("role") == "member" else data.get("member_id")
    cid = data.get("class_id")
    res = StudioClass.unenroll_member(int(cid), int(mid))
    return jsonify(res)

@app.route("/api/classes/attendance", methods=["POST"])
def api_classes_attendance():
    data = request.json or {}
    res = StudioClass.mark_attendance(int(data["class_id"]), int(data["member_id"]), data["status"])
    return jsonify(res)

@app.route("/api/private-session/book", methods=["POST"])
def api_private_book():
    data = request.json or {}
    mid = session.get("linked_id") if session.get("role") == "member" else data.get("member_id")
    tid = data.get("trainer_id")
    dt = data.get("datetime")
    focus = data.get("focus_area", "1-on-1 Personalized Barre Alignment")
    sid = execute_db("""
        INSERT INTO private_sessions (member_id, trainer_id, session_datetime, focus_area, status)
        VALUES (?, ?, ?, ?, 'Pending')
    """, (mid, tid, dt, focus))
    log_audit("PRIVATE_BOOK_REQUEST", "member", f"Member #{mid}", f"Requested private slot #{sid} with Coach #{tid}")
    return jsonify({"success": True, "session_id": sid})

@app.route("/api/private-session/respond", methods=["POST"])
def api_private_respond():
    data = request.json or {}
    sid = data.get("session_id")
    status = data.get("status")
    execute_db("UPDATE private_sessions SET status = ? WHERE id = ?", (status, sid))
    log_audit("PRIVATE_BOOK_STATUS", session.get("role", "coach"), session.get("username", "coach"), f"Set private session #{sid} status to {status}")
    return jsonify({"success": True})

@app.route("/api/coach/availability", methods=["POST"])
def api_coach_availability():
    tid = session.get("linked_id")
    accepting = request.json.get("accepting", 1)
    Trainer.update_settings(tid, accepting=accepting)
    return jsonify({"success": True})

@app.route("/api/admin/rates", methods=["POST"])
def api_admin_rates():
    data = request.json or {}
    tid = data.get("trainer_id")
    rate = data.get("commission_rate")
    retainer = data.get("base_retainer")
    Trainer.update_settings(tid, commission_rate=rate, base_retainer=retainer)
    log_audit("UPDATE_COACH_COMPENSATION", "admin", session.get("username", "admin"), f"Updated Coach #{tid} rate to {rate} and retainer to {retainer}")
    return jsonify({"success": True})

@app.route("/api/admin/budget", methods=["POST"])
def api_save_budget():
    data = request.json or {}
    clean = float(data.get("clean", 8))
    rent = float(data.get("rent", 18))
    equip = float(data.get("equip", 12))
    emerg = float(data.get("emerg", 7))
    profit = float(data.get("profit", 5))
    execute_db("""
        CREATE TABLE IF NOT EXISTS budget_allocations (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            clean REAL DEFAULT 8,
            rent REAL DEFAULT 18,
            equip REAL DEFAULT 12,
            emerg REAL DEFAULT 7,
            profit REAL DEFAULT 5
        )
    """)
    execute_db("""
        INSERT INTO budget_allocations (id, clean, rent, equip, emerg, profit)
        VALUES (1, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            clean = excluded.clean,
            rent = excluded.rent,
            equip = excluded.equip,
            emerg = excluded.emerg,
            profit = excluded.profit
    """, (clean, rent, equip, emerg, profit))
    log_audit("SAVE_BUDGET_ALLOCATION", "admin", session.get("username", "admin"), f"Saved budget allocation: Clean {clean}%, Rent {rent}%, Equip {equip}%, Emerg {emerg}%, Profit {profit}%")
    return jsonify({"success": True})

@app.route("/api/agents/run", methods=["POST"])
def api_run_agent():
    agent_type = request.json.get("agent", "all")
    db = get_db()
    if agent_type == "coaches":
        res = StudioSimulationAgents.run_coach_and_class_agent(db, count=2)
        msg = f"Coach Agent spawned {res['created_coaches']} instructors & schedule!"
    elif agent_type == "members":
        res = StudioSimulationAgents.run_member_onboarding_agent(db, count=5)
        msg = f"Member Agent onboarded {res['created_members']} members with logins and history!"
    elif agent_type == "enrollments":
        res = StudioSimulationAgents.run_class_enrollment_agent(db, count=8)
        msg = f"Enrollment Agent linked {res['new_enrollments']} class reservations!"
    else:
        c = StudioSimulationAgents.run_coach_and_class_agent(db, count=2)
        m = StudioSimulationAgents.run_member_onboarding_agent(db, count=6)
        e = StudioSimulationAgents.run_class_enrollment_agent(db, count=10)
        msg = f"Agent Swarm Deployed: +{c['created_coaches']} Coaches, +{m['created_members']} Members, +{e['new_enrollments']} Bookings!"
    log_audit("DEPLOY_AGENT_SWARM", "admin", session.get("username", "admin"), msg)
    return jsonify({"success": True, "message": msg})

@app.route("/member/<int:member_id>/badge")
def member_badge(member_id):
    member = Member.find_by_id(member_id)
    if not member:
        return "Member not found", 404

    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(f"DREAMSPORT-PASS:{member_id}:{member['fname']}_{member['lname']}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#141414", back_color="#FAF8F5").convert("RGBA")

    card_w, card_h = 440, 250
    card = Image.new("RGBA", (card_w, card_h), "#FAF8F5")
    draw = ImageDraw.Draw(card)

    draw.rectangle([(0, 0), (card_w, 14)], fill="#C8102E")
    draw.rectangle([(0, card_h - 8), (card_w, card_h)], fill="#141414")

    draw.text((28, 28), "DREAM SPORT  |  OFFICIAL PASS", fill="#C8102E")
    draw.text((28, 56), f"{member['fname']} {member['lname']}", fill="#141414")
    draw.text((28, 96), f"TIER: {member['plan_name'].upper()}", fill="#525252")
    draw.text((28, 126), f"MEMBER ID: #{member['id']:04d}", fill="#141414")
    draw.text((28, 156), f"COACH: {member['trainer_name'] or 'STUDIO STAFF'}", fill="#525252")
    draw.text((28, 186), f"STATUS: {member['status'].upper()}", fill="#1E6F50" if member['status'] == 'Active' else "#C8102E")

    qr_resized = qr_img.resize((165, 165))
    card.paste(qr_resized, (250, 42))

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"dreamsport_pass_{member_id}.png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
