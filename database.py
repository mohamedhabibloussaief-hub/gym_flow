import sqlite3
import os
from flask import g
from werkzeug.security import generate_password_hash

DATABASE_FILE = "dreamsport_studio.db"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            DATABASE_FILE,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode = WAL;")
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id

def log_audit(action_type, actor_role, actor_name, details):
    try:
        execute_db(
            "INSERT INTO audit_logs (action_type, actor_role, actor_name, details) VALUES (?, ?, ?, ?)",
            (action_type, actor_role, actor_name, details)
        )
    except Exception:
        pass

def init_db_schema():
    conn = sqlite3.connect(DATABASE_FILE)
    with open("schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

def ensure_initialized():
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    exists = cur.fetchone()
    conn.close()

    if not exists:
        init_db_schema()
        from agents import StudioSimulationAgents
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        StudioSimulationAgents.bootstrap_if_empty(conn)
        conn.close()
