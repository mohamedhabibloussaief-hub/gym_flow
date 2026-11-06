from database import query_db, execute_db

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
    def create(name, duration_months, price, perks):
        return execute_db(
            "INSERT INTO membership_plans (name, duration_months, price, perks) VALUES (?, ?, ?, ?)",
            (name, int(duration_months), float(price), perks)
        )

class Trainer:
    @staticmethod
    def get_all():
        rows = query_db("""
            SELECT t.*, p.name as plan_name,
                   (SELECT COUNT(*) FROM members m WHERE m.trainer_id = t.id AND m.status = 'Active') as active_clients,
                   (SELECT COUNT(*) FROM studio_classes c WHERE c.trainer_id = t.id) as classes_led
            FROM trainers t
            LEFT JOIN membership_plans p ON t.plan_id = p.id
            ORDER BY t.id DESC
        """)
        return [dict(r) for r in rows]

    @staticmethod
    def update_assignment(trainer_id, plan_id=None, specialty=None, max_clients=None):
        if plan_id is not None:
            execute_db("UPDATE trainers SET plan_id = ? WHERE id = ?", (plan_id or None, trainer_id))
        if specialty:
            execute_db("UPDATE trainers SET specialty = ? WHERE id = ?", (specialty, trainer_id))
        if max_clients:
            execute_db("UPDATE trainers SET max_clients = ? WHERE id = ?", (int(max_clients), trainer_id))

class StudioClass:
    @staticmethod
    def get_all():
        rows = query_db("""
            SELECT c.*,
                   COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as trainer_name,
                   COALESCE(p.name, 'All Tiers') as plan_name,
                   (SELECT COUNT(*) FROM class_enrollments e WHERE e.class_id = c.id) as enrolled_count
            FROM studio_classes c
            LEFT JOIN trainers t ON c.trainer_id = t.id
            LEFT JOIN membership_plans p ON c.plan_id = p.id
            ORDER BY c.id ASC
        """)
        classes = [dict(r) for r in rows]
        for cl in classes:
            enr = query_db("""
                SELECT m.id, m.fname || ' ' || m.lname as full_name
                FROM class_enrollments ce
                JOIN members m ON ce.member_id = m.id
                WHERE ce.class_id = ?
            """, (cl["id"],))
            cl["enrolled_members"] = [dict(x) for x in enr]
        return classes

    @staticmethod
    def update_coach(class_id, trainer_id, plan_id=None):
        execute_db(
            "UPDATE studio_classes SET trainer_id = ?, plan_id = COALESCE(?, plan_id) WHERE id = ?",
            (trainer_id or None, plan_id, class_id)
        )

    @staticmethod
    def enroll_member(class_id, member_id):
        cl = query_db("SELECT capacity FROM studio_classes WHERE id = ?", (class_id,), one=True)
        if not cl:
            return {"success": False, "error": "Class not found"}
        curr = query_db("SELECT COUNT(*) as c FROM class_enrollments WHERE class_id = ?", (class_id,), one=True)["c"]
        if curr >= cl["capacity"]:
            return {"success": False, "error": "Studio class is at full capacity"}
        try:
            execute_db("INSERT INTO class_enrollments (class_id, member_id) VALUES (?, ?)", (class_id, member_id))
            return {"success": True}
        except Exception:
            return {"success": False, "error": "Member already enrolled in this class"}

    @staticmethod
    def unenroll_member(class_id, member_id):
        execute_db("DELETE FROM class_enrollments WHERE class_id = ? AND member_id = ?", (class_id, member_id))
        return {"success": True}

class Member:
    @staticmethod
    def create(fname, lname, gender, date_birth, email, phone, plan_id, trainer_id=None, status="Active"):
        mid = execute_db(
            """INSERT INTO members (fname, lname, gender, date_birth, email, phone, plan_id, trainer_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fname, lname, gender, date_birth, email, phone, int(plan_id), int(trainer_id) if trainer_id else None, status)
        )
        plan = query_db("SELECT price FROM membership_plans WHERE id = ?", (plan_id,), one=True)
        if plan:
            execute_db("INSERT INTO payments (member_id, amount, pay_method) VALUES (?, ?, 'card')", (mid, plan["price"]))
        return mid

    @staticmethod
    def update_relations(member_id, plan_id=None, trainer_id=None, status=None):
        if plan_id is not None:
            execute_db("UPDATE members SET plan_id = ? WHERE id = ?", (int(plan_id), member_id))
        if trainer_id is not None:
            val = int(trainer_id) if str(trainer_id).strip() != "" else None
            execute_db("UPDATE members SET trainer_id = ? WHERE id = ?", (val, member_id))
        if status is not None:
            execute_db("UPDATE members SET status = ? WHERE id = ?", (status, member_id))

    @staticmethod
    def find_by_id(member_id):
        row = query_db("""
            SELECT m.*, p.name as plan_name, p.price as plan_price,
                   t.fname || ' ' || t.lname as trainer_name
            FROM members m
            JOIN membership_plans p ON m.plan_id = p.id
            LEFT JOIN trainers t ON m.trainer_id = t.id
            WHERE m.id = ?
        """, (member_id,), one=True)
        if not row:
            return None
        d = dict(row)
        classes = query_db("""
            SELECT c.title, c.schedule_text
            FROM class_enrollments ce
            JOIN studio_classes c ON ce.class_id = c.id
            WHERE ce.member_id = ?
        """, (member_id,))
        d["classes"] = [dict(c) for c in classes]
        return d

    @staticmethod
    def search(term=""):
        search_term = f"%{term}%"
        rows = query_db("""
            SELECT m.id, m.fname, m.lname, m.email, m.phone, m.status, m.joined_date,
                   m.plan_id, m.trainer_id,
                   p.name as plan_name,
                   COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as trainer_name,
                   (SELECT COUNT(*) FROM class_enrollments ce WHERE ce.member_id = m.id) as class_count
            FROM members m
            JOIN membership_plans p ON m.plan_id = p.id
            LEFT JOIN trainers t ON m.trainer_id = t.id
            WHERE m.fname LIKE ? OR m.lname LIKE ? OR m.email LIKE ? OR CAST(m.id AS TEXT) LIKE ?
            ORDER BY m.id DESC
        """, (search_term, search_term, search_term, search_term))
        return [dict(r) for r in rows]

class CheckInManager:
    @staticmethod
    def record_checkin(member_id):
        member = Member.find_by_id(member_id)
        if not member:
            return {"success": False, "error": "Member credential not found"}
        if member["status"] != "Active":
            return {"success": False, "error": f"Studio Access Denied — Status: {member['status']}"}

        checkin_id = execute_db(
            "INSERT INTO checkins (member_id, terminal_point) VALUES (?, ?)",
            (member_id, "Pure Barre Studio Reception")
        )
        return {
            "success": True,
            "checkin_id": checkin_id,
            "member_id": member["id"],
            "name": f"{member['fname']} {member['lname']}",
            "plan": member["plan_name"],
            "trainer": member["trainer_name"] or "Unassigned",
            "classes": [c["title"] for c in member.get("classes", [])]
        }
