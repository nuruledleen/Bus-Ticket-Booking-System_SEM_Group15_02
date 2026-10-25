"""Database access: connection handling, transactions, schema and sample data."""
import os, sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from flask import current_app, g

def now_str(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@contextmanager
def transaction(db):
    """Run a block inside BEGIN IMMEDIATE; commit on success, roll back on any error."""
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.execute("ROLLBACK"); raise
    db.execute("COMMIT")

SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules(
 id INTEGER PRIMARY KEY AUTOINCREMENT, operator TEXT NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL,
 travel_date TEXT NOT NULL, departure_time TEXT NOT NULL, arrival_time TEXT NOT NULL,
 fare REAL NOT NULL CHECK(fare>0), total_seats INTEGER NOT NULL CHECK(total_seats BETWEEN 4 AND 60),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN('active','cancelled')));
CREATE TABLE IF NOT EXISTS bookings(
 id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT UNIQUE NOT NULL,
 schedule_id INTEGER NOT NULL REFERENCES schedules(id), email TEXT NOT NULL, phone TEXT NOT NULL,
 fare_total REAL NOT NULL, fee_total REAL NOT NULL, total REAL NOT NULL, refund_amount REAL NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN('confirmed','cancelled')),
 payment_method TEXT NOT NULL, payment_ref TEXT NOT NULL, created_at TEXT NOT NULL, cancelled_at TEXT);
CREATE TABLE IF NOT EXISTS tickets(
 id INTEGER PRIMARY KEY AUTOINCREMENT, booking_id INTEGER NOT NULL REFERENCES bookings(id),
 schedule_id INTEGER NOT NULL REFERENCES schedules(id), seat_no TEXT NOT NULL, passenger_name TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'booked' CHECK(status IN('booked','cancelled')));
-- Rule 9: a seat can only be 'booked' once per schedule (enforced by the database itself)
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_seat ON tickets(schedule_id, seat_no) WHERE status='booked';
CREATE INDEX IF NOT EXISTS idx_search ON schedules(origin, destination, travel_date);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], isolation_level=None)  # autocommit; we BEGIN manually
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

def close_db(_):
    db = g.pop("db", None)
    if db: db.close()

def init_db(app, reset=False):
    """Create tables and load sample data (only when no schedules exist)."""
    if reset and os.path.exists(app.config["DATABASE"]):
        os.remove(app.config["DATABASE"])
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        if db.execute("SELECT COUNT(*) FROM schedules").fetchone()[0]:
            return
        routes = [("Kuala Lumpur", "Penang", 45, 5, "Sri Express", ["08:00", "14:30", "22:00"]),
                  ("Kuala Lumpur", "Johor Bahru", 38, 4.5, "Metro Coach", ["07:30", "13:00", "21:30"]),
                  ("Kuala Lumpur", "Ipoh", 25, 3, "Aman Liner", ["09:00", "16:00"]),
                  ("Kuala Lumpur", "Melaka", 17, 2, "Metro Coach", ["10:00", "15:30", "19:00"])]
        today = date.today()
        for off in range(10):
            d = (today + timedelta(days=off)).isoformat()
            for a, b, fare, hrs, op, times in routes:
                for o, de in ((a, b), (b, a)):
                    for t in times:
                        arr = (datetime.strptime(t, "%H:%M") + timedelta(hours=hrs)).strftime("%H:%M")
                        db.execute("INSERT INTO schedules(operator,origin,destination,travel_date,departure_time,"
                                   "arrival_time,fare,total_seats) VALUES(?,?,?,?,?,?,?,40)", (op, o, de, d, t, arr, fare))
        # one demo booking so some seats show as taken
        s = db.execute("SELECT * FROM schedules WHERE origin='Kuala Lumpur' AND destination='Penang' AND "
                       "travel_date=? AND departure_time='08:00'", ((today + timedelta(days=1)).isoformat(),)).fetchone()
        cur = db.execute("INSERT INTO bookings(reference,schedule_id,email,phone,fare_total,fee_total,total,payment_method,"
                         "payment_ref,created_at) VALUES('BKDEMO01',?,'demo@example.com','0123456789',90,2,92,'card',"
                         "'SIM-DEMO',?)", (s["id"], now_str()))
        for seat, name in (("1A", "Demo Passenger One"), ("1B", "Demo Passenger Two")):
            db.execute("INSERT INTO tickets(booking_id,schedule_id,seat_no,passenger_name) VALUES(?,?,?,?)",
                       (cur.lastrowid, s["id"], seat, name))

