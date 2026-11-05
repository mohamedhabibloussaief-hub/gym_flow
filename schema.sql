-- GymFlow Pro Relational Schema
-- Enforces strict referential integrity and SQLite WAL performance

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS checkins;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS trainers;
DROP TABLE IF EXISTS membership_plans;

CREATE TABLE membership_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    duration_months INTEGER NOT NULL,
    price REAL NOT NULL,
    perks TEXT NOT NULL
);

CREATE TABLE trainers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fname TEXT NOT NULL,
    lname TEXT NOT NULL,
    specialty TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    max_clients INTEGER DEFAULT 15,
    is_active INTEGER DEFAULT 1
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
    FOREIGN KEY (plan_id) REFERENCES membership_plans(id) ON DELETE RESTRICT,
    FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE SET NULL
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
    terminal_point TEXT DEFAULT 'Front Desk Alpha',
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE INDEX idx_members_email ON members(email);
CREATE INDEX idx_checkins_time ON checkins(checkin_time);
CREATE INDEX idx_payments_date ON payments(pay_date);
