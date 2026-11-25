"""This service's own database (SQLite, one file). No other service reads it directly.

Only this module talks to SQLite. Business code calls the helpers below.
"""
import os
import sqlite3
import threading
from contextlib import contextmanager

from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    phone TEXT,
    organisation TEXT NOT NULL,
    requested_role TEXT NOT NULL,
    role TEXT,
    status TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    totp_secret TEXT,
    failed_count INTEGER NOT NULL DEFAULT 0,
    first_failure_at TEXT,
    locked_until TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS email_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    family_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_refresh_family ON refresh_tokens(family_id);
CREATE INDEX IF NOT EXISTS ix_refresh_user ON refresh_tokens(user_id);
CREATE TABLE IF NOT EXISTS fields (
    id TEXT PRIMARY KEY,
    farm_name TEXT NOT NULL,
    region TEXT NOT NULL,
    anon_code TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS account_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    field_id TEXT NOT NULL REFERENCES fields(id),
    granted_by TEXT NOT NULL,
    reason TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_links_user ON account_links(user_id);
CREATE TABLE IF NOT EXISTS soil_samples (
    sample_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    supersedes_version INTEGER,
    field_id TEXT NOT NULL REFERENCES fields(id),
    owner_user_id TEXT NOT NULL,
    sample_date TEXT NOT NULL,
    depth_cm REAL NOT NULL,
    nitrogen_mg_kg REAL NOT NULL,
    phosphorus_mg_kg REAL NOT NULL,
    potassium_mg_kg REAL NOT NULL,
    ph REAL NOT NULL,
    moisture_pct REAL NOT NULL,
    lab_reference TEXT,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (sample_id, version)
);
CREATE INDEX IF NOT EXISTS ix_samples_field ON soil_samples(field_id, sample_date);
CREATE TABLE IF NOT EXISTS soil_flags (
    sample_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    measurement TEXT NOT NULL,
    level TEXT NOT NULL,
    severity TEXT,
    source TEXT NOT NULL,
    ai_level TEXT,
    ai_score REAL,
    model_version TEXT,
    disagreement INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sample_id, version, measurement)
);
CREATE TABLE IF NOT EXISTS health_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    health_status TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    model_version TEXT,
    ai_view TEXT NOT NULL,
    analysed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_health_sample ON health_results(sample_id, version);
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    job_status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    locked_by TEXT,
    locked_until TEXT,
    next_run_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON analysis_jobs(job_status, next_run_at);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id TEXT,
    actor_role TEXT,
    action TEXT NOT NULL,
    target_id TEXT,
    outcome TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- Append-only rules: the database itself refuses to change or delete these rows.
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS samples_no_change BEFORE UPDATE OF
    field_id, owner_user_id, sample_date, depth_cm, nitrogen_mg_kg, phosphorus_mg_kg,
    potassium_mg_kg, ph, moisture_pct ON soil_samples
BEGIN SELECT RAISE(ABORT, 'sample values are never overwritten; add a new version'); END;
CREATE TRIGGER IF NOT EXISTS samples_no_delete BEFORE DELETE ON soil_samples
BEGIN SELECT RAISE(ABORT, 'samples are append-only'); END;
"""


def connect():
    """Return this thread's connection, creating it on first use."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(config.DB_PATH, timeout=10, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        _local.conn = conn
    return conn


def rows(sql, args=()):
    return [dict(r) for r in connect().execute(sql, args).fetchall()]


def row(sql, args=()):
    found = connect().execute(sql, args).fetchone()
    return dict(found) if found else None


def run(sql, args=()):
    return connect().execute(sql, args)


@contextmanager
def tx():
    """Run a block as one all-or-nothing transaction. Do not nest it."""
    conn = connect()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def init_schema():
    connect().executescript(SCHEMA)


def ping():
    return row("SELECT 1 AS ok") is not None
