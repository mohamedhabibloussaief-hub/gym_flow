-- Dream Sport Enterprise Management & Multi-Portal Schema
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS private_sessions;
DROP TABLE IF EXISTS class_attendance;
DROP TABLE IF EXISTS class_enrollments;
DROP TABLE IF EXISTS studio_classes;
DROP TABLE IF EXISTS checkins;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS trainers;
DROP TABLE IF EXISTS membership_plans;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'coach', 'member')),
    linked_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE membership_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    duration_months INTEGER NOT NULL,
    price REAL NOT NULL,
    monthly_class_limit INTEGER DEFAULT 8,
    perks TEXT NOT NULL
);

CREATE TABLE trainers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fname TEXT NOT NULL,
    lname TEXT NOT NULL,
    specialty TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    plan_id INTEGER,
    commission_rate REAL DEFAULT 0.15,
    private_session_rate REAL DEFAULT 45.0,
    accepting_clients INTEGER DEFAULT 1,
    max_clients INTEGER DEFAULT 15,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (plan_id) REFERENCES membership_plans(id) ON DELETE SET NULL
);

CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fname TEXT NOT NULL,
    lname TEXT NOT NULL,
    gender TEXT NOT NULL,
    date_birth TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    plan_id INTEGER NOT NULL,
    trainer_id INTEGER,
    status TEXT DEFAULT 'Active',
    joined_date DATE DEFAULT (DATE('now')),
    injury_notes TEXT DEFAULT '',
    classes_used_this_month INTEGER DEFAULT 0,
    FOREIGN KEY (plan_id) REFERENCES membership_plans(id) ON DELETE RESTRICT,
    FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE SET NULL
);

CREATE TABLE studio_classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    schedule_text TEXT NOT NULL,
    day_of_week TEXT NOT NULL DEFAULT 'Monday',
    time_slot TEXT NOT NULL DEFAULT '09:00 AM',
    room_name TEXT NOT NULL,
    capacity INTEGER DEFAULT 16,
    trainer_id INTEGER,
    plan_id INTEGER,
    FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE SET NULL,
    FOREIGN KEY (plan_id) REFERENCES membership_plans(id) ON DELETE SET NULL
);

CREATE TABLE class_enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    status TEXT DEFAULT 'Confirmed',
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, member_id),
    FOREIGN KEY (class_id) REFERENCES studio_classes(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE class_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    attended_date DATE DEFAULT (DATE('now')),
    status TEXT NOT NULL CHECK(status IN ('Present', 'No-Show', 'Pending')),
    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES studio_classes(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE private_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    trainer_id INTEGER NOT NULL,
    session_datetime TEXT NOT NULL,
    focus_area TEXT NOT NULL,
    status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Declined', 'Completed')),
    coach_feedback TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE CASCADE
);

CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    pay_method TEXT NOT NULL CHECK(pay_method IN ('card', 'cash', 'transfer')),
    pay_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'Completed',
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    terminal_point TEXT DEFAULT 'Dream Sport Main Reception',
    is_flagged_duplicate INTEGER DEFAULT 0,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    actor_name TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_members_email ON members(email);
CREATE INDEX idx_checkins_time ON checkins(checkin_time);
CREATE INDEX idx_payments_date ON payments(pay_date);
CREATE INDEX idx_enrollments_class ON class_enrollments(class_id);
