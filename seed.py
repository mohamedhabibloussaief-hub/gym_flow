"""
Mock production data seeder for GymFlow Pro.
Populates standard plans, trainers, realistic members, transactional payments,
and time-distributed check-in records for immediate dashboard visualization.
"""

from database import init_db, execute_db, query_db
import random
from datetime import datetime, timedelta

def run_seed():
    print("[*] Initializing fresh schema...")
    init_db("schema.sql")

    print("[*] Inserting membership plans...")
    plans = [
        ("Starter Basic", 1, 45.0, "Gym floor access, locker room"),
        ("Standard Pro", 3, 120.0, "Gym floor + sauna, group classes"),
        ("Athlete Tier", 6, 220.0, "Full access + 2 PT sessions/month"),
        ("Executive VIP", 12, 400.0, "Unlimited access, personal locker, private spa, unlimited PT")
    ]
    for p in plans:
        execute_db("INSERT INTO membership_plans (name, duration_months, price, perks) VALUES (?, ?, ?, ?)", p)

    print("[*] Inserting certified trainers...")
    trainers = [
        ("Khalil", "Hajlaoui", "Strength & Conditioning", "khalil.haj@gymflow.io", "+216 24 567 890", 12),
        ("Rania", "Missaoui", "Cardio & HIIT", "rania.m@gymflow.io", "+216 22 119 443", 15),
        ("Tarek", "Cherif", "Mobility & Clinical Rehab", "tarek.c@gymflow.io", "+216 55 882 109", 10),
        ("Sarra", "Belhaj", "Functional Movement & Pilates", "sarra.b@gymflow.io", "+216 98 401 772", 14)
    ]
    trainer_ids = []
    for t in trainers:
        tid = execute_db("INSERT INTO trainers (fname, lname, specialty, email, phone, max_clients) VALUES (?, ?, ?, ?, ?, ?)", t)
        trainer_ids.append(tid)

    print("[*] Inserting realistic members and payment histories...")
    first_names = ["Ahmed", "Samir", "Linda", "Yassine", "Mariem", "Ines", "Omar", "Selim", "Nour", "Karim", "Zied", "Cyrine"]
    last_names = ["Monji", "BenAli", "Ayachi", "Trabelsi", "Gharbi", "Mansour", "Kefi", "Bouazizi", "Driss", "Hammami", "Fourati", "Baccouche"]

    random.seed(42)
    member_ids = []

    for i in range(24):
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        gender = "Male" if i % 2 == 0 else "Female"
        birth_year = random.randint(1988, 2004)
        dob = f"{birth_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        email = f"{fname.lower()}.{lname.lower()}{random.randint(10, 999)}@example.com"
        phone = f"+216 {random.randint(20, 99)} {random.randint(100, 999)} {random.randint(100, 999)}"
        plan_id = random.randint(1, 4)
        trainer_id = random.choice(trainer_ids + [None])
        status = "Active" if random.random() > 0.1 else "Suspended"

        mid = execute_db(
            """INSERT INTO members (fname, lname, gender, date_birth, email, phone, plan_id, trainer_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fname, lname, gender, dob, email, phone, plan_id, trainer_id, status)
        )
        member_ids.append(mid)

        # Generate realistic payment
        plan_price = query_db("SELECT price FROM membership_plans WHERE id = ?", (plan_id,), one=True)["price"]
        pay_method = random.choice(["card", "cash", "transfer"])
        pay_days_ago = random.randint(1, 60)
        pay_date = (datetime.now() - timedelta(days=pay_days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        execute_db(
            "INSERT INTO payments (member_id, amount, pay_method, pay_date) VALUES (?, ?, ?, ?)",
            (mid, plan_price, pay_method, pay_date)
        )

    print("[*] Seeding historical check-in scans across past 7 days...")
    for day_offset in range(7, -1, -1):
        target_date = datetime.now() - timedelta(days=day_offset)
        # Generate 6 to 15 checkins per day
        scans_count = random.randint(8, 18)
        for _ in range(scans_count):
            scan_member = random.choice(member_ids)
            scan_hour = random.randint(7, 21)
            scan_minute = random.randint(0, 59)
            scan_time = target_date.replace(hour=scan_hour, minute=scan_minute, second=0).strftime("%Y-%m-%d %H:%M:%S")
            execute_db(
                "INSERT INTO checkins (member_id, checkin_time, terminal_point) VALUES (?, ?, ?)",
                (scan_member, scan_time, "Front Desk Scanner A")
            )

    print("[+] Database successfully seeded with production-grade test records!")

if __name__ == "__main__":
    run_seed()
