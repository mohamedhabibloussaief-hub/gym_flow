from flask import Flask, render_template, request, jsonify, send_file
import io
import qrcode
from PIL import Image, ImageDraw

from database import close_db, query_db, execute_db, get_db, ensure_initialized
from models import Member, CheckInManager, MembershipPlan, Trainer, StudioClass
from chatbot import SemanticStudioCopilot
from agents import StudioSimulationAgents

app = Flask(__name__)
app.config["SECRET_KEY"] = "pure-barre-atelier-secret-2026"
app.teardown_appcontext(close_db)

# Guarantee database schema and seed data exist before any request
ensure_initialized()

copilot = SemanticStudioCopilot()

# ================= PAGE ROUTES =================

@app.route("/")
def index():
    return render_template("dashboard.html", active_page="dashboard")

@app.route("/members")
def members_page():
    plans = MembershipPlan.get_all()
    trainers = Trainer.get_all()
    classes = StudioClass.get_all()
    return render_template("members.html", active_page="members", plans=plans, trainers=trainers, classes=classes)

@app.route("/studio")
def studio_page():
    plans = MembershipPlan.get_all()
    trainers = Trainer.get_all()
    classes = StudioClass.get_all()
    members = Member.search("")
    return render_template("studio.html", active_page="studio", plans=plans, trainers=trainers, classes=classes, members=members)

@app.route("/terminal")
def terminal_page():
    members = Member.search("")[:6]
    return render_template("terminal.html", active_page="terminal", sample_members=members)

# ================= REST API & AGENT ENDPOINTS =================

@app.route("/api/metrics")
def api_metrics():
    total_active = query_db("SELECT COUNT(*) as c FROM members WHERE status = 'Active'", one=True)["c"]
    today_checkins = query_db("SELECT COUNT(*) as c FROM checkins WHERE DATE(checkin_time) = DATE('now')", one=True)["c"]
    total_rev = query_db("SELECT COALESCE(SUM(amount), 0) as c FROM payments", one=True)["c"]
    active_trainers = query_db("SELECT COUNT(*) as c FROM trainers", one=True)["c"]
    total_enrollments = query_db("SELECT COUNT(*) as c FROM class_enrollments", one=True)["c"]

    classes = StudioClass.get_all()
    recent_checkins = query_db("""
        SELECT c.id, c.checkin_time, m.id as member_id, m.fname || ' ' || m.lname as member_name,
               p.name as plan_name
        FROM checkins c
        JOIN members m ON c.member_id = m.id
        JOIN membership_plans p ON m.plan_id = p.id
        ORDER BY c.checkin_time DESC
        LIMIT 6
    """)

    return jsonify({
        "total_active": total_active,
        "today_checkins": today_checkins,
        "monthly_rev": total_rev,
        "active_trainers": active_trainers,
        "total_enrollments": total_enrollments,
        "classes": classes,
        "recent_checkins": [dict(r) for r in recent_checkins]
    })

@app.route("/api/charts/revenue")
def api_chart_revenue():
    rows = query_db("""
        SELECT p.name as plan_name, COALESCE(SUM(pay.amount), 0) as revenue
        FROM membership_plans p
        LEFT JOIN members m ON m.plan_id = p.id
        LEFT JOIN payments pay ON pay.member_id = m.id
        GROUP BY p.id
        ORDER BY p.price ASC
    """)
    return jsonify({
        "labels": [r["plan_name"].replace("Pure ", "") for r in rows],
        "values": [r["revenue"] for r in rows]
    })

@app.route("/api/charts/traffic")
def api_chart_traffic():
    rows = query_db("""
        SELECT DATE(checkin_time) as scan_date, COUNT(*) as scan_count
        FROM checkins
        GROUP BY DATE(checkin_time)
        ORDER BY scan_date ASC
        LIMIT 7
    """)
    return jsonify({
        "labels": [r["scan_date"] for r in rows],
        "values": [r["scan_count"] for r in rows]
    })

@app.route("/api/members", methods=["GET", "POST"])
def api_members():
    if request.method == "POST":
        data = request.json or {}
        fname = data.get("fname", "").strip()
        lname = data.get("lname", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        plan_id = data.get("plan_id")
        trainer_id = data.get("trainer_id") or None
        class_id = data.get("class_id") or None
        gender = data.get("gender", "Female")
        dob = data.get("date_birth", "1998-05-15")

        if not fname or not lname or not email or not plan_id:
            return jsonify({"success": False, "error": "Please fill in First Name, Last Name, Email, and Plan Tier."}), 400

        try:
            new_id = Member.create(fname, lname, gender, dob, email, phone, plan_id, trainer_id)
            if class_id:
                StudioClass.enroll_member(int(class_id), new_id)
            return jsonify({"success": True, "member_id": new_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    query = request.args.get("q", "")
    members = Member.search(query)
    return jsonify({"members": members})

@app.route("/api/members/<int:member_id>/update", methods=["POST"])
def api_update_member(member_id):
    data = request.json or {}
    Member.update_relations(
        member_id,
        plan_id=data.get("plan_id"),
        trainer_id=data.get("trainer_id"),
        status=data.get("status")
    )
    return jsonify({"success": True})

@app.route("/api/trainers/<int:trainer_id>/update", methods=["POST"])
def api_update_trainer(trainer_id):
    data = request.json or {}
    Trainer.update_assignment(
        trainer_id,
        plan_id=data.get("plan_id"),
        specialty=data.get("specialty"),
        max_clients=data.get("max_clients")
    )
    return jsonify({"success": True})

@app.route("/api/classes/<int:class_id>/update", methods=["POST"])
def api_update_class(class_id):
    data = request.json or {}
    StudioClass.update_coach(class_id, data.get("trainer_id"), data.get("plan_id"))
    return jsonify({"success": True})

@app.route("/api/classes/enroll", methods=["POST"])
def api_enroll_class():
    data = request.json or {}
    res = StudioClass.enroll_member(int(data["class_id"]), int(data["member_id"]))
    return jsonify(res), (200 if res["success"] else 400)

@app.route("/api/classes/unenroll", methods=["POST"])
def api_unenroll_class():
    data = request.json or {}
    res = StudioClass.unenroll_member(int(data["class_id"]), int(data["member_id"]))
    return jsonify(res)

@app.route("/api/plans", methods=["POST"])
def api_create_plan():
    data = request.json or {}
    pid = MembershipPlan.create(
        data.get("name", "Custom Studio Tier"),
        data.get("duration_months", 1),
        data.get("price", 120.0),
        data.get("perks", "Full Barre Studio Access")
    )
    return jsonify({"success": True, "plan_id": pid})

@app.route("/api/agents/run", methods=["POST"])
def api_run_agent():
    """Triggers autonomous simulation agents to populate coaches, members, and class enrollments."""
    data = request.json or {}
    agent_type = data.get("agent", "all")
    db = get_db()

    if agent_type == "coaches":
        res = StudioSimulationAgents.run_coach_and_class_agent(db, count=2)
        msg = f"Coach Agent spawned {res['created_coaches']} instructors & {res['assigned_classes']} studio class!"
    elif agent_type == "members":
        res = StudioSimulationAgents.run_member_onboarding_agent(db, count=5)
        msg = f"Member Agent onboarded {res['created_members']} members with tier & coach assignments!"
    elif agent_type == "enrollments":
        res = StudioSimulationAgents.run_class_enrollment_agent(db, enrollments_to_create=8)
        msg = f"Enrollment Agent linked {res['new_enrollments']} class bookings!"
    else:
        c_res = StudioSimulationAgents.run_coach_and_class_agent(db, count=2)
        m_res = StudioSimulationAgents.run_member_onboarding_agent(db, count=6)
        e_res = StudioSimulationAgents.run_class_enrollment_agent(db, enrollments_to_create=10)
        msg = f"Full Multi-Agent Swarm: +{c_res['created_coaches']} Coaches, +{m_res['created_members']} Members, +{e_res['new_enrollments']} Bookings!"

    return jsonify({"success": True, "message": msg})

@app.route("/api/checkin", methods=["POST"])
def api_checkin():
    data = request.json or {}
    member_id = data.get("member_id")
    if not member_id:
        return jsonify({"success": False, "error": "Member ID is required"}), 400
    try:
        member_id = int(member_id)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid Member ID format"}), 400

    result = CheckInManager.record_checkin(member_id)
    return jsonify(result), (200 if result["success"] else 400)

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json or {}
    user_msg = data.get("message", "")
    res = copilot.analyze_semantics(user_msg)
    return jsonify(res)

@app.route("/member/<int:member_id>/badge")
def member_badge(member_id):
    """Generates a Pure Barre editorial luxury digital pass with embedded QR verification."""
    member = Member.find_by_id(member_id)
    if not member:
        return "Member not found", 404

    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(f"DreamSport-PASS:{member_id}:{member['fname']}_{member['lname']}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#141414", back_color="#FAF8F5").convert("RGBA")

    card_w, card_h = 440, 250
    card = Image.new("RGBA", (card_w, card_h), "#FAF8F5")
    draw = ImageDraw.Draw(card)

    # Pure Barre Crimson Editorial Header Bar
    draw.rectangle([(0, 0), (card_w, 14)], fill="#C8102E")
    draw.rectangle([(0, card_h - 6), (card_w, card_h)], fill="#141414")

    draw.text((28, 28), "PURE BARRE  |  ATELIER PASS", fill="#C8102E")
    draw.text((28, 56), f"{member['fname']} {member['lname']}", fill="#141414")
    draw.text((28, 96), f"TIER: {member['plan_name'].upper()}", fill="#525252")
    draw.text((28, 126), f"MEMBER ID: #{member['id']:04d}", fill="#141414")
    draw.text((28, 156), f"COACH: {member['trainer_name'] or 'STUDIO STAFF'}", fill="#525252")
    draw.text((28, 186), f"STATUS: {member['status'].upper()}", fill="#15803D" if member['status'] == 'Active' else "#C8102E")

    qr_resized = qr_img.resize((165, 165))
    card.paste(qr_resized, (250, 42))

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"DreamSport_pass_{member_id}.png")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
