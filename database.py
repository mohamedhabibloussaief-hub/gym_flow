import sqlite3
import os
from flask import g

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

def init_db_schema(schema_path="schema.sql"):
    if not os.path.exists(schema_path) and os.path.exists("schema-v2.sql"):
        schema_path = "schema-v2.sql"
    conn = sqlite3.connect(DATABASE_FILE)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

def ensure_initialized():
    """Guarantees tables and baseline membership plans exist on server startup."""
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='membership_plans'")
    exists = cur.fetchone()
    conn.close()

    if not exists:
        init_db_schema()
        from agents import StudioSimulationAgents
        # Run full initial studio population automatically
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        StudioSimulationAgents.bootstrap_if_empty(conn)
        conn.close()
