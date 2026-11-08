import os
import re
import json
import urllib.request
import urllib.error
from database import query_db

class DreamSportCopilot:
    def __init__(self):
        # Reads GEMINI_API_KEY from environment (must be a valid AIzaSy... key from Google AI Studio)
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    def handle_query(self, user_msg, context=None):
        context = context or {}
        role = context.get("role", "admin")
        user_id = context.get("user_id")
        linked_id = context.get("linked_id")

        # Validate that a real Google AI Studio key (starts with AIza) is configured
        if self.api_key and self.api_key.startswith("AIza"):
            try:
                return self._gemini_llm_query(user_msg, role, user_id, linked_id)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                res = self._semantic_ontology_query(user_msg, role, user_id, context)
                res["message"] = f"(Gemini API HTTP {e.code} — check GEMINI_API_KEY) " + res["message"]
                return res
            except Exception as e:
                res = self._semantic_ontology_query(user_msg, role, user_id, context)
                res["message"] = f"(Gemini Connection Fallback: {str(e)}) " + res["message"]
                return res
        else:
            res = self._semantic_ontology_query(user_msg, role, user_id, context)
            return res

    def analyze_semantics(self, query_text):
        """Backward-compatibility alias."""
        return self._semantic_ontology_query(query_text, "admin", None, {})

    def _build_full_studio_context(self, role, user_id, linked_id):
        """Gathers live SQLite telemetry so Gemini can answer detailed Admin & Member questions."""
        classes = query_db("""
            SELECT c.title, c.schedule_text, c.room_name, c.capacity,
                   COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as coach,
                   (SELECT COUNT(*) FROM class_enrollments e WHERE e.class_id = c.id) as enrolled
            FROM studio_classes c
            LEFT JOIN trainers t ON c.trainer_id = t.id
        """)
        plans = query_db("""
            SELECT p.name, p.price, p.perks,
                   (SELECT COUNT(*) FROM members m WHERE m.plan_id = p.id AND m.status = 'Active') as active_members
            FROM membership_plans p
            ORDER BY p.price ASC
        """)
        coaches = query_db("""
            SELECT t.fname || ' ' || t.lname as name, t.specialty, t.commission_rate,
                   (SELECT COUNT(*) FROM members m WHERE m.trainer_id = t.id AND m.status = 'Active') as client_count,
                   t.max_clients
            FROM trainers t
        """)
        members = query_db("""
            SELECT m.id, m.fname || ' ' || m.lname as name, m.status, m.injury_notes,
                   p.name as plan_name, COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as coach_name
            FROM members m
            JOIN membership_plans p ON m.plan_id = p.id
            LEFT JOIN trainers t ON m.trainer_id = t.id
            ORDER BY m.id ASC
        """)
        gross_rev = query_db("SELECT COALESCE(SUM(amount), 0) as s FROM payments", one=True)["s"]
        today_checkins = query_db("SELECT COUNT(*) as c FROM checkins WHERE DATE(checkin_time) = DATE('now')", one=True)["c"]
        total_enrollments = query_db("SELECT COUNT(*) as c FROM class_enrollments", one=True)["c"]

        class_summary = "; ".join([
            f"{c['title']} ({c['schedule_text']} in {c['room_name']}, Coach: {c['coach']}, {c['enrolled']}/{c['capacity']} booked)"
            for c in classes
        ])
        plan_summary = "; ".join([
            f"{p['name']} (${p['price']:.0f}/mo, {p['active_members']} active members, Perks: {p['perks']})"
            for p in plans
        ])
        coach_summary = "; ".join([
            f"{t['name']} ({t['specialty']}, {t['client_count']}/{t['max_clients']} clients, {int(t['commission_rate']*100)}% commission)"
            for t in coaches
        ])
        member_summary = "; ".join([
            f"#{m['id']:04d} {m['name']} [Tier: {m['plan_name']}, Coach: {m['coach_name']}, Status: {m['status']}"
            + (f", Injury: {m['injury_notes']}" if m["injury_notes"] else "") + "]"
            for m in members[:30]
        ])

        return f"""You are the official AI Studio Executive Copilot & Concierge for Dream Sport Atelier.
You are speaking with a user logged in with role: {role.upper()}.
Be warm, conversational, articulate, and insightful. You can handle casual small talk naturally as well as provide deep, accurate operational breakdowns using the live studio data below:

LIVE STUDIO TELEMETRY:
- Total Active Members: {len([m for m in members if m['status'] == 'Active'])} (Total in roster: {len(members)})
- Total Class Enrollments: {total_enrollments}
- Gross Studio Revenue (MTD): ${gross_rev:,.2f}
- Today's Reception Check-Ins: {today_checkins}
- Studio Classes ({len(classes)}): {class_summary}
- Membership Plan Tiers ({len(plans)}): {plan_summary}
- Certified Coaches ({len(coaches)}): {coach_summary}
- Studio Member Roster: {member_summary}

Guidelines:
- If the admin greets you or makes small talk, respond naturally like an executive chief-of-staff and offer a quick pulse check of the studio.
- When asked about members, revenue, coaches, classes, or injuries, cite the exact names, numbers, and tiers from the live telemetry above.
- Format key highlights with clean bullet points or bold text when helpful.
"""

    def _gemini_llm_query(self, user_msg, role, user_id, linked_id):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        system_context = self._build_full_studio_context(role, user_id, linked_id)

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_context}]
            },
            "contents": [
                {"role": "user", "parts": [{"text": user_msg}]}
            ],
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 1024,
                "thinkingConfig": {
                    "thinkingBudget": 0
                }
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            parts = res_data["candidates"][0]["content"]["parts"]
            answer = "".join([p.get("text", "") for p in parts]).strip()
            return {
                "badge": "Gemini 2.5 Flash Engine",
                "triple": "Admin ──[converses_with]──> Gemini2.5Flash ──[live_telemetry]──> Insight",
                "message": answer
            }

    def _semantic_ontology_query(self, text, role, user_id, context):
        q = text.lower().strip()
        tokens = set(re.findall(r"[a-z0-9]+", q))

        has_greeting = bool(tokens & {"hi", "hello", "hey", "morning", "evening", "status", "overview", "summary", "how"})
        has_member = bool(tokens & {"member", "members", "client", "clients", "student", "who", "roster"})
        has_coach = bool(tokens & {"coach", "coaches", "trainer", "trainers", "instructor", "teaching", "teaches"})
        has_class = bool(tokens & {"class", "classes", "barre", "schedule", "empower", "classic", "align", "define", "enrollments"})
        has_plan = bool(tokens & {"plan", "plans", "tier", "tiers", "vip", "subscription", "price", "cost"})
        has_revenue = bool(tokens & {"revenue", "money", "sales", "finance", "finances", "budget", "payroll"})

        all_trainers = query_db("SELECT id, fname, lname, specialty FROM trainers")
        for t in all_trainers:
            if t["fname"].lower() in tokens or t["lname"].lower() in tokens:
                classes = query_db("SELECT title, schedule_text FROM studio_classes WHERE trainer_id = ?", (t["id"],))
                clients = query_db("SELECT fname || ' ' || lname as name FROM members WHERE trainer_id = ?", (t["id"],))
                c_str = ", ".join([c["title"] for c in classes]) or "None scheduled"
                cl_str = ", ".join([m["name"] for m in clients]) or "None assigned"
                return {
                    "badge": "Semantic Entity Match",
                    "triple": f"Coach:{t['fname']} ──[leads / coaches]──> Classes & Clients",
                    "message": f"**Coach {t['fname']} {t['lname']}** ({t['specialty']}):\n• **Classes Led:** {c_str}\n• **Personal Clients ({len(clients)}):** {cl_str}"
                }

        if has_member:
            rows = query_db("""
                SELECT m.id, m.fname || ' ' || m.lname as name, p.name as plan_name,
                       COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as coach, m.status
                FROM members m
                JOIN membership_plans p ON m.plan_id = p.id
                LEFT JOIN trainers t ON m.trainer_id = t.id
                ORDER BY m.id ASC
            """)
            lines = [f"• **#{r['id']:04d} {r['name']}** — {r['plan_name']} (Coach: *{r['coach']}*) [{r['status']}]" for r in rows[:12]]
            more = f"\n...and {len(rows) - 12} more members in the directory." if len(rows) > 12 else ""
            return {
                "badge": "Member Directory Graph",
                "triple": "Studio ──[enrolls]──> ActiveMembers",
                "message": f"Dream Sport currently has **{len(rows)} enrolled studio members**:\n" + "\n".join(lines) + more
            }

        if has_class:
            rows = query_db("""
                SELECT c.title, c.schedule_text, COALESCE(t.fname || ' ' || t.lname, 'TBA') as coach,
                       (SELECT COUNT(*) FROM class_enrollments e WHERE e.class_id = c.id) as enrolled,
                       c.capacity
                FROM studio_classes c
                LEFT JOIN trainers t ON c.trainer_id = t.id
            """)
            lines = [f"• **{r['title']}** ({r['schedule_text']}) — Instructor: *{r['coach']}* [{r['enrolled']}/{r['capacity']} booked]" for r in rows]
            return {
                "badge": "Studio Class Ontology",
                "triple": "Class ──[instructed_by / has_capacity]──> Coach & Roster",
                "message": f"Active Studio Sessions ({len(rows)}):\n" + "\n".join(lines)
            }

        if has_coach:
            rows = query_db("SELECT t.fname || ' ' || t.lname as name, t.specialty, (SELECT COUNT(*) FROM members m WHERE m.trainer_id = t.id) as clients FROM trainers t")
            lines = [f"• **{r['name']}** ({r['specialty']}) — {r['clients']} assigned clients" for r in rows]
            return {
                "badge": "Staff Graph",
                "triple": "Coach ──[certified_in / mentors]──> Specialty & Members",
                "message": "Dream Sport Certified Coaching Staff:\n" + "\n".join(lines)
            }

        if has_plan:
            rows = query_db("""
                SELECT p.name, p.price, p.perks,
                       (SELECT COUNT(*) FROM members m WHERE m.plan_id = p.id AND m.status = 'Active') as cnt
                FROM membership_plans p ORDER BY p.price ASC
            """)
            lines = [f"• **{r['name']}** (${r['price']:.0f}/mo) — {r['cnt']} members — {r['perks']}" for r in rows]
            return {
                "badge": "Tier Catalog",
                "triple": "MembershipPlan ──[offers / charges]──> Benefits & Pricing",
                "message": "Dream Sport Membership Options:\n" + "\n".join(lines)
            }

        if has_revenue:
            rev = query_db("SELECT COALESCE(SUM(amount), 0) as s FROM payments", one=True)["s"]
            by_tier = query_db("""
                SELECT p.name, COALESCE(SUM(CASE WHEN m.status = 'Active' THEN p.price ELSE 0 END), 0) as rev
                FROM membership_plans p LEFT JOIN members m ON m.plan_id = p.id
                GROUP BY p.id, p.name ORDER BY p.price ASC
            """)
            breakdown = "\n".join([f"• **{r['name']}**: ${r['rev']:,.0f}/mo" for r in by_tier])
            return {
                "badge": "Financial Telemetry",
                "triple": "Payments ──[aggregate_to]──> TotalStudioRevenue",
                "message": f"Total Studio Processed Volume: **${rev:,.2f}**\n{breakdown}"
            }

        if has_greeting:
            total_m = query_db("SELECT COUNT(*) as c FROM members WHERE status = 'Active'", one=True)["c"]
            total_c = query_db("SELECT COUNT(*) as c FROM trainers", one=True)["c"]
            total_e = query_db("SELECT COUNT(*) as c FROM class_enrollments", one=True)["c"]
            rev = query_db("SELECT COALESCE(SUM(amount), 0) as s FROM payments", one=True)["s"]
            return {
                "badge": "Executive Pulse Summary",
                "triple": "StudioOntology ──[summarizes]──> ExecutivePulse",
                "message": f"Hello! Here is your quick Dream Sport Atelier pulse check:\n• **Active Members:** {total_m} enrolled\n• **Certified Coaches:** {total_c} on staff\n• **Active Seat Reservations:** {total_e} bookings\n• **Processed Revenue:** ${rev:,.2f}\n\nWhat would you like to inspect in detail?"
            }

        return {
            "badge": "Dream Sport Knowledge Graph",
            "triple": "StudioOntology ──[status]──> Operational",
            "message": "Welcome to Dream Sport Atelier AI Concierge! Ask me anything about your members, coaches, class occupancy, membership tiers, or studio revenue."
        }

SemanticStudioCopilot = DreamSportCopilot
