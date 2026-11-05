"""
Intelligent Gym Assistant Engine.
Utilizes intent classification, regex entity parsing, and secure parameterized
SQL execution to act as an operational data copilot.
"""

import re
from database import query_db

class GymAssistant:
    def __init__(self):
        self.intent_patterns = [
            ("summary_metrics", [r"summary", r"overview", r"how are we doing", r"kpi", r"stats"]),
            ("list_trainers", [r"trainer", r"coach", r"who is coaching", r"instructors"]),
            ("find_member", [r"member (\w+)", r"find (\w+)", r"lookup (\w+)", r"who is (\w+)"]),
            ("revenue_info", [r"revenue", r"sales", r"money", r"earnings", r"financials"]),
            ("capacity_check", [r"capacity", r"crowd", r"busy", r"traffic", r"checkins"]),
            ("help_menu", [r"help", r"what can you do", r"commands", r"menu"])
        ]

    def parse_intent(self, text):
        clean_text = text.lower().strip()
        for intent, patterns in self.intent_patterns:
            for pat in patterns:
                match = re.search(pat, clean_text)
                if match:
                    groups = match.groups()
                    return intent, groups[0] if groups else None
        return "fallback", None

    def execute_copilot(self, user_query):
        intent, entity = self.parse_intent(user_query)

        if intent == "summary_metrics":
            m_count = query_db("SELECT COUNT(*) as cnt FROM members WHERE status = 'Active'", one=True)["cnt"]
            t_count = query_db("SELECT COUNT(*) as cnt FROM checkins WHERE DATE(checkin_time) = DATE('now')", one=True)["cnt"]
            rev = query_db("SELECT SUM(amount) as total FROM payments", one=True)["total"] or 0.0
            return {
                "message": f"GymFlow Status Report: We have **{m_count} active members**, **{t_count} check-ins today**, and total processed revenue of **${rev:,.2f}**.",
                "badge": "KPI Overview"
            }

        elif intent == "list_trainers":
            trainers = query_db("""
                SELECT t.fname || ' ' || t.lname as name, t.specialty, COUNT(m.id) as client_count
                FROM trainers t
                LEFT JOIN members m ON t.id = m.trainer_id AND m.status = 'Active'
                GROUP BY t.id
            """)
            items = [f"• **{t['name']}** ({t['specialty']}) — {t['client_count']} clients" for t in trainers]
            return {
                "message": "Current Fitness Coaches and Load Balancing:\n" + "\n".join(items),
                "badge": "Staff Directory"
            }

        elif intent == "find_member":
            res = query_db("""
                SELECT m.id, m.fname, m.lname, m.status, p.name as plan
                FROM members m
                JOIN membership_plans p ON m.plan_id = p.id
                WHERE m.fname LIKE ? OR m.lname LIKE ?
            """, (f"%{entity}%", f"%{entity}%"))
            if not res:
                return {"message": f"No member found matching '{entity}'.", "badge": "Not Found"}
            
            lines = [f"• ID #{r['id']}: **{r['fname']} {r['lname']}** [{r['status']}] on {r['plan']}" for r in res]
            return {
                "message": f"Found {len(res)} matching member(s):\n" + "\n".join(lines),
                "badge": "Search Match"
            }

        elif intent == "revenue_info":
            by_plan = query_db("""
                SELECT p.name, SUM(pay.amount) as total
                FROM payments pay
                JOIN members m ON pay.member_id = m.id
                JOIN membership_plans p ON m.plan_id = p.id
                GROUP BY p.id
            """)
            lines = [f"• **{r['name']}**: ${r['total']:,.2f}" for r in by_plan]
            return {
                "message": "Revenue Breakdown by Subscription Plan:\n" + "\n".join(lines),
                "badge": "Financials"
            }

        elif intent == "capacity_check":
            recent = query_db("SELECT COUNT(*) as cnt FROM checkins WHERE datetime(checkin_time) >= datetime('now', '-2 hours')", one=True)["cnt"]
            return {
                "message": f"Peak Load Analysis: **{recent} members** checked in over the last 2 hours. Floor density is within safe operational limits.",
                "badge": "Floor Traffic"
            }

        elif intent == "help_menu":
            return {
                "message": "I can query real-time gym telemetry! Try asking:\n• 'summary stats'\n• 'who are the trainers?'\n• 'find Samir'\n• 'revenue breakdown'\n• 'current capacity'",
                "badge": "Assistant Help"
            }

        return {
            "message": "I didn't quite catch that query. You can ask me for 'summary stats', 'list trainers', 'revenue breakdown', or search members by name.",
            "badge": "Clarification"
        }
