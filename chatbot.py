import re
from database import query_db

class SemanticStudioCopilot:
    """
    Studio Ontology Nodes:
      - Member (Attributes: status, gender, joined_date)
      - Coach / Trainer (Attributes: specialty, max_clients)
      - Class (Attributes: title, category, schedule, room)
      - Plan / Tier (Attributes: name, price, duration)
      - Financial / Telemetry (Revenue, Check-ins)
    Semantic Predicates:
      - coached_by(Member, Coach)
      - enrolled_in(Member, Class)
      - subscribed_to(Member, Plan)
      - assigned_to_tier(Coach, Plan)
      - teaches(Coach, Class)
    """

    def analyze_semantics(self, query_text):
        q = query_text.lower().strip()
        tokens = set(re.findall(r"[a-z0-9]+", q))

        # Detect Ontology Classes mentioned
        has_member = bool(tokens & {"member", "members", "client", "clients", "student", "students", "who", "enrolled", "roster"})
        has_coach = bool(tokens & {"coach", "coaches", "trainer", "trainers", "instructor", "instructors", "teaching", "teaches", "taught"})
        has_class = bool(tokens & {"class", "classes", "barre", "session", "sessions", "empower", "classic", "align", "define", "schedule"})
        has_plan = bool(tokens & {"plan", "plans", "tier", "tiers", "vip", "unlimited", "subscription", "membership", "foundations", "lifestyle"})
        has_revenue = bool(tokens & {"revenue", "money", "sales", "financial", "financials", "income", "earned", "billing", "total"})
        has_summary = bool(tokens & {"summary", "overview", "stats", "kpi", "status", "report", "dashboard"})

        # Check for specific person/entity name in query
        all_trainers = query_db("SELECT id, fname, lname FROM trainers")
        matched_trainer = None
        for t in all_trainers:
            if t["fname"].lower() in tokens or t["lname"].lower() in tokens:
                matched_trainer = dict(t)
                break

        all_members = query_db("SELECT id, fname, lname FROM members")
        matched_member = None
        for m in all_members:
            if m["fname"].lower() in tokens or m["lname"].lower() in tokens:
                matched_member = dict(m)
                break

        # 1. Multi-hop: Members enrolled in classes or coached by a specific trainer
        if matched_trainer and (has_member or has_class):
            tid = matched_trainer["id"]
            tname = f"{matched_trainer['fname']} {matched_trainer['lname']}"
            clients = query_db("SELECT fname || ' ' || lname as name FROM members WHERE trainer_id = ?", (tid,))
            classes = query_db("SELECT title, schedule_text FROM studio_classes WHERE trainer_id = ?", (tid,))
            c_list = ", ".join([r["name"] for r in clients]) or "None assigned directly"
            cl_list = ", ".join([f"{r['title']} ({r['schedule_text']})" for r in classes]) or "No classes scheduled"
            return {
                "triple": f"Coach:{matched_trainer['fname']} ──[teaches / coaches]──> Classes & Members",
                "badge": "Semantic Graph Traversal",
                "message": f"**Coach {tname}** Ontology Profile:\n• **Classes Taught:** {cl_list}\n• **Assigned Clients ({len(clients)}):** {c_list}"
            }

        # 2. Specific Member semantic profile
        if matched_member:
            mid = matched_member["id"]
            m = query_db("""
                SELECT m.*, p.name as plan_name, COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as coach_name
                FROM members m
                JOIN membership_plans p ON m.plan_id = p.id
                LEFT JOIN trainers t ON m.trainer_id = t.id
                WHERE m.id = ?
            """, (mid,), one=True)
            enr = query_db("""
                SELECT c.title FROM class_enrollments ce
                JOIN studio_classes c ON ce.class_id = c.id
                WHERE ce.member_id = ?
            """, (mid,))
            cls_names = ", ".join([r["title"] for r in enr]) or "Not enrolled in classes yet"
            return {
                "triple": f"Member:{m['fname']} ──[subscribed_to / coached_by / enrolled_in]──> Studio Graph",
                "badge": "Entity Resolution",
                "message": f"**{m['fname']} {m['lname']}** (ID #{m['id']:04d}):\n• **Plan Tier:** {m['plan_name']}\n• **Personal Coach:** {m['coach_name']}\n• **Enrolled Classes:** {cls_names}"
            }

        # 3. Classes & Enrollments Graph
        if has_class:
            rows = query_db("""
                SELECT c.title, c.schedule_text, COALESCE(t.fname || ' ' || t.lname, 'TBA') as coach,
                       (SELECT COUNT(*) FROM class_enrollments e WHERE e.class_id = c.id) as enrolled,
                       c.capacity
                FROM studio_classes c
                LEFT JOIN trainers t ON c.trainer_id = t.id
            """)
            lines = [f"• **{r['title']}** ({r['schedule_text']}) — Led by *{r['coach']}* [{r['enrolled']}/{r['capacity']} enrolled]" for r in rows]
            return {
                "triple": "StudioClass ──[taught_by / has_enrollment]──> Coach & MemberRoster",
                "badge": "Class Ontology",
                "message": f"Active Pure Barre Studio Classes ({len(rows)}):\n" + "\n".join(lines)
            }

        # 4. Coaches / Trainers Graph
        if has_coach:
            rows = query_db("""
                SELECT t.fname || ' ' || t.lname as name, t.specialty, COALESCE(p.name, 'All Tiers') as tier,
                       (SELECT COUNT(*) FROM members m WHERE m.trainer_id = t.id) as clients,
                       (SELECT COUNT(*) FROM studio_classes c WHERE c.trainer_id = t.id) as classes_count
                FROM trainers t
                LEFT JOIN membership_plans p ON t.plan_id = p.id
            """)
            lines = [f"• **{r['name']}** ({r['specialty']}) — Tier: *{r['tier']}* | {r['clients']} clients, {r['classes_count']} classes" for r in rows]
            return {
                "triple": "Coach ──[assigned_to_tier / coaches / leads]──> PlanTier & Members",
                "badge": "Instructor Graph",
                "message": f"Studio Instructors & Relational Assignments ({len(rows)}):\n" + "\n".join(lines)
            }

        # 5. Plans / Tiers Graph
        if has_plan:
            rows = query_db("""
                SELECT p.name, p.price,
                       (SELECT COUNT(*) FROM members m WHERE m.plan_id = p.id) as m_cnt,
                       (SELECT COUNT(*) FROM trainers t WHERE t.plan_id = p.id) as t_cnt
                FROM membership_plans p
            """)
            lines = [f"• **{r['name']}** (${r['price']:.0f}/mo) — {r['m_cnt']} members, {r['t_cnt']} specialist coaches" for r in rows]
            return {
                "triple": "MembershipPlan ──[has_subscribers / has_specialists]──> Members & Coaches",
                "badge": "Tier Ontology",
                "message": "Studio Membership Tiers & Relational Distribution:\n" + "\n".join(lines)
            }

        # 6. Revenue & Financial Telemetry
        if has_revenue:
            rev_rows = query_db("""
                SELECT p.name, COALESCE(SUM(pay.amount), 0) as total
                FROM membership_plans p
                LEFT JOIN members m ON m.plan_id = p.id
                LEFT JOIN payments pay ON pay.member_id = m.id
                GROUP BY p.id
            """)
            total_all = sum(r["total"] for r in rev_rows)
            lines = [f"• **{r['name']}**: ${r['total']:,.2f}" for r in rev_rows]
            return {
                "triple": "Payment ──[generated_by / belongs_to]──> Member ──> PlanTier",
                "badge": "Financial Graph",
                "message": f"Total Studio Revenue: **${total_all:,.2f}**\n" + "\n".join(lines)
            }

        # 7. Members Roster Query (fixes 'who are my members')
        if has_member:
            rows = query_db("""
                SELECT m.id, m.fname || ' ' || m.lname as name, p.name as plan,
                       COALESCE(t.fname || ' ' || t.lname, 'Unassigned') as coach
                FROM members m
                JOIN membership_plans p ON m.plan_id = p.id
                LEFT JOIN trainers t ON m.trainer_id = t.id
                ORDER BY m.id DESC LIMIT 10
            """)
            total_m = query_db("SELECT COUNT(*) as c FROM members", one=True)["c"]
            lines = [f"• **#{r['id']:04d} {r['name']}** — *{r['plan']}* (Coach: {r['coach']})" for r in rows]
            return {
                "triple": "Member ──[subscribed_to / coached_by]──> PlanTier & Coach",
                "badge": "Member Roster Graph",
                "message": f"Showing latest {len(rows)} of **{total_m} studio members**:\n" + "\n".join(lines)
            }

        # 8. Default / Summary Graph
        m_cnt = query_db("SELECT COUNT(*) as c FROM members WHERE status='Active'", one=True)["c"]
        t_cnt = query_db("SELECT COUNT(*) as c FROM trainers", one=True)["c"]
        c_cnt = query_db("SELECT COUNT(*) as c FROM studio_classes", one=True)["c"]
        e_cnt = query_db("SELECT COUNT(*) as c FROM class_enrollments", one=True)["c"]
        rev = query_db("SELECT COALESCE(SUM(amount), 0) as s FROM payments", one=True)["s"]
        return {
            "triple": "StudioRoot ──[aggregates]──> {Members, Coaches, Classes, Enrollments, Revenue}",
            "badge": "Semantic Knowledge Graph",
            "message": (
                f"**Pure Barre Studio Knowledge Graph Summary:**\n"
                f"• **Active Members:** {m_cnt} enrolled across {e_cnt} class bookings\n"
                f"• **Certified Coaches:** {t_cnt} leading {c_cnt} scheduled barre classes\n"
                f"• **Processed Revenue:** ${rev:,.2f}\n"
                f"*Try asking: 'who are my members', 'show classes and enrollments', 'list coaches and tiers', or a specific name!*"
            )
        }
