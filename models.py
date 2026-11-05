"""
Domain entity models implementing object-oriented business logic.
Provides structured entity abstraction and validation over SQLite tables.
"""

from database import query_db, execute_db

class MembershipPlan:
    def __init__(self, plan_id, name, duration_months, price, perks):
        self.id = plan_id
        self.name = name
        self.duration_months = duration_months
        self.price = price
        self.perks = perks

    @staticmethod
    def get_all():
        rows = query_db("SELECT * FROM membership_plans ORDER BY price ASC")
        return [dict(r) for r in rows]

class Trainer:
    def __init__(self, trainer_id, fname, lname, specialty, email, phone, max_clients=15):
        self.id = trainer_id
        self.fname = fname
        self.lname = lname
        self.specialty = specialty
        self.email = email
        self.phone = phone
        self.max_clients = max_clients

    @property
    def full_name(self):
        return f"{self.fname} {self.lname}"

    @staticmethod
    def get_all():
        rows = query_db("""
            SELECT t.*, COUNT(m.id) as active_clients
            FROM trainers t
            LEFT JOIN members m ON t.id = m.trainer_id AND m.status = 'Active'
            GROUP BY t.id
        """)
        return [dict(r) for r in rows]

class PersonalTrainer(Trainer):
    def __init__(self, trainer_id, fname, lname, specialty, email, phone, max_clients, hourly_rate=45.0):
        super().__init__(trainer_id, fname, lname, specialty, email, phone, max_clients)
        self.hourly_rate = hourly_rate

    def calculate_commission(self, sessions_completed):
        return sessions_completed * (self.hourly_rate * 0.70)

class Member:
    def __init__(self, fname, lname, gender, date_birth, email, phone, plan_id, trainer_id=None, status="Active", member_id=None):
        self.id = member_id
        self.fname = fname
        self.lname = lname
        self.gender = gender
        self.date_birth = date_birth
        self.email = email
        self.phone = phone
        self.plan_id = plan_id
        self.trainer_id = trainer_id
        self.status = status

    def save(self):
        if self.id is None:
            self.id = execute_db(
                """INSERT INTO members (fname, lname, gender, date_birth, email, phone, plan_id, trainer_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.fname, self.lname, self.gender, self.date_birth, self.email, self.phone, self.plan_id, self.trainer_id, self.status)
            )
        return self.id

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
        return dict(row) if row else None

    @staticmethod
    def search(term=""):
        search_term = f"%{term}%"
        rows = query_db("""
            SELECT m.id, m.fname, m.lname, m.email, m.phone, m.status, m.joined_date,
                   p.name as plan_name,
                   COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as trainer_name
            FROM members m
            JOIN membership_plans p ON m.plan_id = p.id
            LEFT JOIN trainers t ON m.trainer_id = t.id
            WHERE m.fname LIKE ? OR m.lname LIKE ? OR m.email LIKE ? OR m.id LIKE ?
            ORDER BY m.id DESC
        """, (search_term, search_term, search_term, search_term))
        return [dict(r) for r in rows]

class CheckInManager:
    @staticmethod
    def record_checkin(member_id):
        member = Member.find_by_id(member_id)
        if not member:
            return {"success": False, "error": "Member record not found"}
        if member["status"] != "Active":
            return {"success": False, "error": f"Access Denied: Member status is {member['status']}"}

        checkin_id = execute_db(
            "INSERT INTO checkins (member_id, terminal_point) VALUES (?, ?)",
            (member_id, "Front Desk Scanner A")
        )
        return {
            "success": True,
            "checkin_id": checkin_id,
            "member_id": member["id"],
            "name": f"{member['fname']} {member['lname']}",
            "plan": member["plan_name"],
            "trainer": member["trainer_name"] or "None"
        }
