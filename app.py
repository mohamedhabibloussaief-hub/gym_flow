"""
GymFlow Pro - Core Web Application Server.
Provides RESTful JSON endpoints, page routes, digital badge generation with QR codes,
and live analytical telemetry.
"""

from flask import Flask, render_template, request, jsonify, send_file
import io
import qrcode
from PIL import Image, ImageDraw, ImageFont

from database import close_db, query_db, execute_db
from models import Member, CheckInManager, MembershipPlan, Trainer
from chatbot import GymAssistant

app = Flask(__name__)
app.config["SECRET_KEY"] = "gymflow-secret-key-2026-production"
app.teardown_appcontext(close_db)

copilot = GymAssistant()

# ================= PAGE ROUTES =================

@app.route("/")
def index():
    return render_template("dashboard.html", active_page="dashboard")

@app.route("/members")
def members_page():
    plans = MembershipPlan.get_all()
    trainers = Trainer.get_all()
    return render_template("members.html", active_page="members", plans=plans, trainers=trainers)

@app.route("/terminal")
def terminal_page():
    return render_template("terminal.html", active_page="terminal")

# ================= REST API ROUTES =================

@app.route("/api/metrics")
def api_metrics():
    total_active = query_db("SELECT COUNT(*) as c FROM members WHERE status = 'Active'", one=True)["c"]
    today_checkins = query_db("SELECT COUNT(*) as c FROM checkins WHERE DATE(checkin_time) = DATE('now')", one=True)["c"]
    monthly_rev = query_db("SELECT SUM(amount) as c FROM payments WHERE pay_date >= DATE('now', 'start of month')", one=True)["c"] or 0.0
    active_trainers = query_db("SELECT COUNT(*) as c FROM trainers WHERE is_active = 1", one=True)["c"]

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
        "monthly_rev": monthly_rev,
        "active_trainers": active_trainers,
        "recent_checkins": [dict(r) for r in recent_checkins]
    })

@app.route("/api/charts/revenue")
def api_chart_revenue():
    rows = query_db("""
        SELECT p.name as plan_name, SUM(pay.amount) as revenue
        FROM payments pay
        JOIN members m ON pay.member_id = m.id
        JOIN membership_plans p ON m.plan_id = p.id
        GROUP BY p.id
        ORDER BY revenue DESC
    """)
    return jsonify({
        "labels": [r["plan_name"] for r in rows],
        "values": [r["revenue"] for r in rows]
    })

@app.route("/api/charts/traffic")
def api_chart_traffic():
    rows = query_db("""
        SELECT DATE(checkin_time) as scan_date, COUNT(*) as scan_count
        FROM checkins
        WHERE checkin_time >= DATE('now', '-6 days')
        GROUP BY DATE(checkin_time)
        ORDER BY scan_date ASC
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
        gender = data.get("gender", "Unspecified")
        dob = data.get("date_birth", "2000-01-01")

        if not fname or not lname or not email or not plan_id:
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        member = Member(fname, lname, gender, dob, email, phone, plan_id, trainer_id)
        try:
            new_id = member.save()
            # Log initial payment
            plan_price = query_db("SELECT price FROM membership_plans WHERE id = ?", (plan_id,), one=True)["price"]
            execute_db("INSERT INTO payments (member_id, amount, pay_method) VALUES (?, ?, ?)", (new_id, plan_price, "card"))
            return jsonify({"success": True, "member_id": new_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    query = request.args.get("q", "")
    members = Member.search(query)
    return jsonify({"members": members})

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
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json or {}
    user_msg = data.get("message", "")
    res = copilot.execute_copilot(user_msg)
    return jsonify(res)

@app.route("/member/<int:member_id>/badge")
def member_badge(member_id):
    """Generates an Apple-Wallet-styled digital badge pass with embedded QR code."""
    member = Member.find_by_id(member_id)
    if not member:
        return "Member not found", 404

    # Generate QR Code
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(f"GYMFLOW-PASS:{member_id}:{member['fname']}_{member['lname']}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF").convert("RGBA")

    # Generate Card Canvas
    card_w, card_h = 420, 240
    card = Image.new("RGBA", (card_w, card_h), "#0F172A")
    draw = ImageDraw.Draw(card)

    # Accent Header Bar
    draw.rectangle([(0, 0), (card_w, 10)], fill="#3B82F6")

    # Brand Title
    draw.text((25, 25), "GYMFLOW PRO PASS", fill="#94A3B8")
    draw.text((25, 50), f"{member['fname']} {member['lname']}", fill="#F8FAFC")
    draw.text((25, 95), f"TIER: {member['plan_name'].upper()}", fill="#38BDF8")
    draw.text((25, 125), f"ID: #{member['id']:05d}", fill="#E2E8F0")
    draw.text((25, 155), f"STATUS: {member['status'].upper()}", fill="#22C55E" if member['status'] == 'Active' else "#EF4444")
    draw.text((25, 185), f"TRAINER: {member['trainer_name'] or 'None'}", fill="#94A3B8")

    # Paste QR Code on Right
    qr_size = 170
    qr_resized = qr_img.resize((qr_size, qr_size))
    card.paste(qr_resized, (225, 40))

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"gymflow_pass_{member_id}.png")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
