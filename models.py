from database import query_db, execute_db, log_audit
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta

class User:
    @staticmethod
    def authenticate(email, password):
        user = query_db("SELECT * FROM users WHERE email = ?", (email.strip().lower(),), one=True)
        if user and check_password_hash(user["password_hash"], password):
            return dict(user)
        return None

    @staticmethod
    def get_by_id(user_id):
        row = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
        return dict(row) if row else None

class MembershipPlan:
    @staticmethod
    def get_all():
        rows = query_db("""
            SELECT p.*,
                   (SELECT COUNT(*) FROM members m WHERE m.plan_id = p.id) as member_count,
                   (SELECT COUNT(*) FROM trainers t WHERE t.plan_id = p.id) as coach_count
            FROM membership_plans p
            ORDER BY p.price ASC
        """)
        return [dict(r) for r in rows]

    @staticmethod
    def create(name, duration_months, price, monthly_class_limit=8, perks="Full Barre Studio Access"):
        return execute_db(
            """INSERT INTO membership_plans (name, duration_months, price, monthly_class_limit, perks)
               VALUES (?, ?, ?, ?, ?)""",
            (name, int(duration_months), float(price), int(monthly_class_limit), perks)
        )

class Trainer:
    @staticmethod
    def get_all():
        rows = query_db("""
            SELECT t.*, p.name as plan_name, p.price as plan_price,
                   (SELECT COUNT(*) FROM members m WHERE m.trainer_id = t.id AND m.status = 'Active') as active_clients,
                   (SELECT COUNT(*) FROM studio_classes c WHERE c.trainer_id = t.id) as classes_led,
                   (SELECT COUNT(*) FROM private_sessions ps WHERE ps.trainer_id = t.id AND ps.status = 'Completed') as private_completed
            FROM trainers t
            LEFT JOIN membership_plans p ON t.plan_id = p.id
            ORDER BY t.id ASC
        """)
        trainers = [dict(r) for r in rows]
        for t in trainers:
            client_rev = query_db("""
                SELECT SUM(p.price) as total_client_vol
                FROM members m
                JOIN membership_plans p ON m.plan_id = p.id
                WHERE m.trainer_id = ? AND m.status = 'Active'
            """, (t["id"],), one=True)["total_client_vol"] or 0.0

            private_rev = t["private_completed"] * t["private_session_rate"] * 0.70
            t["client_volume"] = client_rev
            t["earned_commission"] = (client_rev * t["commission_rate"]) + private_rev
            t["base_retainer"] = t.get("base_retainer") if t.get("base_retainer") is not None else 800.0
            t["total_payout"] = t["base_retainer"] + t["earned_commission"]
        return trainers

    @staticmethod
    def get_by_id(trainer_id):
        row = query_db("""
            SELECT t.*, p.name as plan_name, p.price as plan_price,
                   (SELECT COUNT(*) FROM members m WHERE m.trainer_id = t.id AND m.status = 'Active') as active_clients
            FROM trainers t
            LEFT JOIN membership_plans p ON t.plan_id = p.id
            WHERE t.id = ?
        """, (trainer_id,), one=True)
        return dict(row) if row else None

    @staticmethod
    def update_settings(trainer_id, specialty=None, max_clients=None, commission_rate=None, accepting=None, plan_id=None, base_retainer=None):
        if specialty:
            execute_db("UPDATE trainers SET specialty = ? WHERE id = ?", (specialty, trainer_id))
        if max_clients is not None:
            execute_db("UPDATE trainers SET max_clients = ? WHERE id = ?", (int(max_clients), trainer_id))
        if commission_rate is not None:
            execute_db("UPDATE trainers SET commission_rate = ? WHERE id = ?", (float(commission_rate), trainer_id))
        if base_retainer is not None:
            try:
                execute_db("ALTER TABLE trainers ADD COLUMN base_retainer REAL DEFAULT 800.0")
            except Exception:
                pass
            execute_db("UPDATE trainers SET base_retainer = ? WHERE id = ?", (float(base_retainer), trainer_id))
        if accepting is not None:
            execute_db("UPDATE trainers SET accepting_clients = ? WHERE id = ?", (int(accepting), trainer_id))
        if plan_id is not None:
            val = int(plan_id) if str(plan_id).strip() != "" else None
            execute_db("UPDATE trainers SET plan_id = ? WHERE id = ?", (val, trainer_id))

class StudioClass:
    @staticmethod
    def get_all():
        rows = query_db("""
            SELECT c.*,
                   COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as trainer_name,
                   t.email as trainer_email,
                   COALESCE(p.name, 'All Studio Tiers') as plan_name,
                   (SELECT COUNT(*) FROM class_enrollments e WHERE e.class_id = c.id) as enrolled_count
            FROM studio_classes c
            LEFT JOIN trainers t ON c.trainer_id = t.id
            LEFT JOIN membership_plans p ON c.plan_id = p.id
            ORDER BY c.id ASC
        """)
        classes = [dict(r) for r in rows]
        for cl in classes:
            enr = query_db("""
                SELECT m.id, m.fname || ' ' || m.lname as full_name, m.email, m.phone, m.injury_notes,
                       p.name as plan_name,
                       (SELECT status FROM class_attendance a WHERE a.class_id = ? AND a.member_id = m.id AND a.attended_date = DATE('now')) as today_status
                FROM class_enrollments ce
                JOIN members m ON ce.member_id = m.id
                JOIN membership_plans p ON m.plan_id = p.id
                WHERE ce.class_id = ?
            """, (cl["id"], cl["id"]))
            cl["roster"] = [dict(x) for x in enr]
        return classes

    @staticmethod
    def enroll_member(class_id, member_id):
        member = Member.find_by_id(member_id)
        if not member:
            return {"success": False, "error": "Member not found."}
        if member["status"] != "Active":
            return {"success": False, "error": "Membership is not Active."}

        if member["monthly_class_limit"] > 0 and member["classes_used_this_month"] >= member["monthly_class_limit"]:
            return {"success": False, "error": f"Monthly class limit reached ({member['monthly_class_limit']} classes). Please upgrade your tier."}

        cl = query_db("SELECT capacity FROM studio_classes WHERE id = ?", (class_id,), one=True)
        if not cl:
            return {"success": False, "error": "Class not found."}
        curr = query_db("SELECT COUNT(*) as c FROM class_enrollments WHERE class_id = ?", (class_id,), one=True)["c"]
        if curr >= cl["capacity"]:
            return {"success": False, "error": "Studio class is fully booked."}

        try:
            execute_db("INSERT INTO class_enrollments (class_id, member_id) VALUES (?, ?)", (class_id, member_id))
            execute_db("UPDATE members SET classes_used_this_month = classes_used_this_month + 1 WHERE id = ?", (member_id,))
            log_audit("CLASS_ENROLL", "member", f"Member #{member_id}", f"Enrolled in class #{class_id}")
            return {"success": True}
        except Exception:
            return {"success": False, "error": "You are already enrolled in this class."}

    @staticmethod
    def unenroll_member(class_id, member_id):
        execute_db("DELETE FROM class_enrollments WHERE class_id = ? AND member_id = ?", (class_id, member_id))
        execute_db("UPDATE members SET classes_used_this_month = MAX(0, classes_used_this_month - 1) WHERE id = ?", (member_id,))
        log_audit("CLASS_UNENROLL", "member", f"Member #{member_id}", f"Cancelled enrollment in class #{class_id}")
        return {"success": True}

    @staticmethod
    def mark_attendance(class_id, member_id, status):
        existing = query_db(
            "SELECT id FROM class_attendance WHERE class_id = ? AND member_id = ? AND attended_date = DATE('now')",
            (class_id, member_id), one=True
        )
        if existing:
            execute_db("UPDATE class_attendance SET status = ?, marked_at = CURRENT_TIMESTAMP WHERE id = ?", (status, existing["id"]))
        else:
            execute_db("INSERT INTO class_attendance (class_id, member_id, status) VALUES (?, ?, ?)", (class_id, member_id, status))
        return {"success": True}

class Member:
    @staticmethod
    def find_by_id(member_id):
        row = query_db("""
            SELECT m.*, p.name as plan_name, p.price as plan_price, p.monthly_class_limit, p.perks,
                   t.fname || ' ' || t.lname as trainer_name, t.specialty as trainer_specialty,
                   t.email as trainer_email, t.phone as trainer_phone
            FROM members m
            JOIN membership_plans p ON m.plan_id = p.id
            LEFT JOIN trainers t ON m.trainer_id = t.id
            WHERE m.id = ?
        """, (member_id,), one=True)
        if not row:
            return None
        d = dict(row)

        classes = query_db("""
            SELECT c.id, c.title, c.category, c.schedule_text, c.room_name,
                   COALESCE(t.fname || ' ' || t.lname, 'Instructor') as coach_name
            FROM class_enrollments ce
            JOIN studio_classes c ON ce.class_id = c.id
            LEFT JOIN trainers t ON c.trainer_id = t.id
            WHERE ce.member_id = ?
        """, (member_id,))
        d["enrolled_classes"] = [dict(c) for c in classes]

        checkins = query_db("""
            SELECT * FROM checkins WHERE member_id = ? ORDER BY checkin_time DESC LIMIT 10
        """, (member_id,))
        d["recent_checkins"] = [dict(c) for c in checkins]

        sessions = query_db("""
            SELECT ps.*, t.fname || ' ' || t.lname as coach_name
            FROM private_sessions ps
            JOIN trainers t ON ps.trainer_id = t.id
            WHERE ps.member_id = ?
            ORDER BY ps.session_datetime DESC
        """, (member_id,))
        d["private_sessions"] = [dict(s) for s in sessions]

        return d

    @staticmethod
    def search(term=""):
        search_term = f"%{term}%"
        rows = query_db("""
            SELECT m.id, m.fname, m.lname, m.email, m.phone, m.status, 
            CAST(m.joined_date AS TEXT) as joined_date,
                   m.plan_id, m.trainer_id, m.injury_notes, m.classes_used_this_month,
                   p.name as plan_name, p.price as plan_price, p.monthly_class_limit,
                   COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as trainer_name,
                   (SELECT COUNT(*) FROM class_enrollments ce WHERE ce.member_id = m.id) as class_count
            FROM members m
            JOIN membership_plans p ON m.plan_id = p.id
            LEFT JOIN trainers t ON m.trainer_id = t.id
            WHERE m.fname LIKE ? OR m.lname LIKE ? OR m.email LIKE ? OR CAST(m.id AS TEXT) LIKE ?
            ORDER BY m.id DESC
        """, (search_term, search_term, search_term, search_term))
        return [dict(r) for r in rows]

    @staticmethod
    def switch_coach(member_id, target_coach_id):
        member = Member.find_by_id(member_id)
        if not member:
            return {"success": False, "error": "Member not found."}

        coach = Trainer.get_by_id(target_coach_id)
        if not coach:
            return {"success": False, "error": "Selected coach does not exist."}

        if coach["accepting_clients"] == 0:
            return {"success": False, "error": f"Coach {coach['fname']} is currently not accepting new 1-on-1 clients."}

        if coach["active_clients"] >= coach["max_clients"]:
            return {"success": False, "error": f"Coach {coach['fname']} has reached maximum client capacity ({coach['max_clients']})."}

        if coach["plan_id"]:
            coach_tier = query_db("SELECT price FROM membership_plans WHERE id = ?", (coach["plan_id"],), one=True)
            if coach_tier and coach_tier["price"] > member["plan_price"]:
                return {"success": False, "error": "This coach is reserved for higher membership tiers. Please upgrade your tier to select them."}

        execute_db("UPDATE members SET trainer_id = ? WHERE id = ?", (target_coach_id, member_id))
        log_audit("SWITCH_COACH", "member", f"Member #{member_id}", f"Switched coach to {coach['fname']} {coach['lname']} (#{target_coach_id})")
        return {"success": True, "coach_name": f"{coach['fname']} {coach['lname']}"}

    @staticmethod
    def update_injury_notes(member_id, notes):
        execute_db("UPDATE members SET injury_notes = ? WHERE id = ?", (notes.strip(), member_id))
        log_audit("UPDATE_HEALTH_NOTES", "member", f"Member #{member_id}", "Updated mobility & injury restrictions")
        return {"success": True}

class CheckInManager:
    @staticmethod
    def record_checkin(member_id):
        member = Member.find_by_id(member_id)
        if not member:
            return {"success": False, "error": "Member credential not found in Dream Sport database"}
        if member["status"] != "Active":
            return {"success": False, "error": f"Access Denied: Member status is {member['status']}"}

        recent_scan = query_db("""
            SELECT checkin_time FROM checkins
            WHERE member_id = ? AND checkin_time >= datetime('now', '-30 minutes')
            ORDER BY checkin_time DESC LIMIT 1
        """, (member_id,), one=True)

        is_flagged = 1 if recent_scan else 0

        checkin_id = execute_db(
            "INSERT INTO checkins (member_id, terminal_point, is_flagged_duplicate) VALUES (?, ?, ?)",
            (member_id, "Dream Sport Main Reception", is_flagged)
        )

        res = {
            "success": True,
            "checkin_id": checkin_id,
            "member_id": member["id"],
            "name": f"{member['fname']} {member['lname']}",
            "plan": member["plan_name"],
            "trainer": member["trainer_name"] or "Studio Staff",
            "classes": [c["title"] for c in member.get("enrolled_classes", [])],
            "injury_notes": member.get("injury_notes", ""),
            "duplicate_warning": bool(is_flagged)
        }
        if is_flagged:
            log_audit("GATE_SECURITY_ALERT", "terminal", "Reception Scanner", f"Possible pass sharing for Member #{member_id} (Scanned again within 30 min)")

        return res
