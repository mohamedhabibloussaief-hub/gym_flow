"""
Database connection and session lifecycle management for GymFlow.
Configures SQLite with WAL (Write-Ahead-Logging) for concurrent read performance
and provides secure query helper utilities with row-factory mapping.
"""

import sqlite3
import os
from flask import g, current_app

DATABASE_FILE = "gymflow.db"

def get_db():
    """Retrieves or opens a thread-local SQLite connection."""
    if "db" not in g:
        g.db = sqlite3.connect(
            DATABASE_FILE,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        g.db.row_factory = sqlite3.Row
        # Enable WAL mode and foreign key constraints
        g.db.execute("PRAGMA journal_mode = WAL;")
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db

def close_db(e=None):
    """Closes the current database connection if open."""
    db = g.pop("db", None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    """Safely executes a read query with parameterized arguments."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    """Safely executes a write/mutation query with parameterized arguments."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id

def init_db(schema_path="schema.sql"):
    """Initializes tables from the schema file."""
    conn = sqlite3.connect(DATABASE_FILE)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
