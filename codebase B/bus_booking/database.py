"""SQLite connection handling, transactions and tiny query helpers."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path):
    # isolation_level=None -> we control transactions explicitly.
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@contextmanager
def transaction(conn):
    """BEGIN IMMEDIATE takes the write lock up front, so check-then-insert is safe."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def init_db(conn):
    conn.executescript(SCHEMA_PATH.read_text())


def fetch_all(conn, sql, params=()):
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetch_one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None
