"""BusGo MY - simple monolithic bus ticket booking system (Flask + SQLite).
Routes, validation, fares, SQL, booking and cancellation logic all live here on purpose."""
import os, re, sqlite3, secrets
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, g

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["DATABASE"] = os.environ.get("BUS_DB", os.path.join(app.root_path, "busbooking.db"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SERVICE_FEE, MAX_SEATS = 1.00, 4          # RM per ticket, seats per booking
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'/@-]{1,59}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^(\+?60|0)1\d{8,9}$")   # Malaysian mobile
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

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

# ---------- database ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"], isolation_level=None)  # autocommit; we BEGIN manually
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db: db.close()

def init_db(reset=False):
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

@app.cli.command("init-db")
def init_db_cmd():
    """flask --app app init-db  (add --reset via env RESET=1 to rebuild)"""
    init_db(reset=os.environ.get("RESET") == "1")
    print("Database ready:", app.config["DATABASE"])

# ---------- helpers ----------
def now_str(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def parse_date(v):
    try: return datetime.strptime(v or "", "%Y-%m-%d").date()
    except ValueError: return None
def dep_dt(s): return datetime.strptime(f"{s['travel_date']} {s['departure_time']}", "%Y-%m-%d %H:%M")
def seat_labels(n): return [f"{i // 4 + 1}{'ABCD'[i % 4]}" for i in range(n)]   # 2+2 layout
def seat_rows(n): l = seat_labels(n); return [l[i:i + 4] for i in range(0, n, 4)]
def taken_seats(db, sid):
    return {r[0] for r in db.execute("SELECT seat_no FROM tickets WHERE schedule_id=? AND status='booked'", (sid,))}
def calc_fare(fare, n):
    """Total = fare x seats + service fee x seats."""
    return round(fare * n, 2), round(SERVICE_FEE * n, 2), round((fare + SERVICE_FEE) * n, 2)
def simulate_payment(method, amount):
    """Fake gateway: always approves. Replace with a real gateway call in production."""
    return True, "SIM-" + secrets.token_hex(4).upper()
def cancellation_info(b, s):
    """Return (eligible, refund, message). >=24h: 100% fare back; 2-24h: 50%; <2h: not allowed."""
    if b["status"] != "confirmed": return False, 0.0, "This booking is already cancelled."
    hrs = (dep_dt(s) - datetime.now()).total_seconds() / 3600
    if hrs < 2: return False, 0.0, "Cancellation closes 2 hours before departure."
    pct = 1.0 if hrs >= 24 else 0.5
    return True, round(b["fare_total"] * pct, 2), f"{int(pct * 100)}% of the fare is refunded; the service fee is not."
app.jinja_env.filters["rm"] = lambda v: f"RM {float(v):,.2f}"

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"):
            flash("Please log in as administrator.", "error"); return redirect(url_for("admin"))
        return f(*a, **k)
    return w

def get_open_schedule(sid):
    s = get_db().execute("SELECT * FROM schedules WHERE id=?", (sid,)).fetchone()
    if not s or s["status"] != "active" or dep_dt(s) <= datetime.now(): return None
    return s

# ---------- customer pages ----------
@app.route("/")
def index():
    db = get_db()
    cities = [r[0] for r in db.execute("SELECT origin FROM schedules UNION SELECT destination FROM schedules ORDER BY 1")]
    q = {k: request.args.get(k, "").strip() for k in ("origin", "destination", "travel_date")}
    results = None
    if request.args:
        d = parse_date(q["travel_date"])
        if not q["origin"] or not q["destination"]: flash("Enter both origin and destination.", "error")
        elif q["origin"].lower() == q["destination"].lower(): flash("Origin and destination must differ.", "error")
        elif not d: flash("Choose a valid travel date.", "error")
        elif d < date.today(): flash("Travel date cannot be in the past.", "error")
        else:
            rows = db.execute("SELECT s.*, s.total_seats-(SELECT COUNT(*) FROM tickets t WHERE t.schedule_id=s.id AND "
                              "t.status='booked') AS available FROM schedules s WHERE lower(origin)=lower(?) AND "
                              "lower(destination)=lower(?) AND travel_date=? AND status='active' ORDER BY departure_time",
                              (q["origin"], q["destination"], d.isoformat())).fetchall()
            results = [r for r in rows if dep_dt(r) > datetime.now()]
    return render_template("index.html", cities=cities, q=q, results=results, today=date.today().isoformat())

def render_seats(s, form=None, status=200):
    form = form or {}
    names = {k[5:]: v for k, v in form.items() if k.startswith("name_")}
    return render_template("seats.html", s=s, rows=seat_rows(s["total_seats"]), taken=taken_seats(get_db(), s["id"]),
                           fee=SERVICE_FEE, max_seats=MAX_SEATS, form=form, names=names,
                           chosen=form.getlist("seats") if hasattr(form, "getlist") else []), status

@app.route("/schedule/<int:sid>")
def seats(sid):
    s = get_open_schedule(sid)
    if not s: flash("That schedule is not available for booking.", "error"); return redirect(url_for("index"))
    return render_seats(s)

@app.route("/schedule/<int:sid>/book", methods=["POST"])
def book(sid):
    s = get_open_schedule(sid)
    if not s: flash("That schedule is not available for booking.", "error"); return redirect(url_for("index"))
    f, errors = request.form, []
    chosen = list(dict.fromkeys(f.getlist("seats")))
    if not chosen: errors.append("Select at least one seat.")
    elif len(chosen) > MAX_SEATS: errors.append(f"You can book at most {MAX_SEATS} seats at a time.")
    elif any(x not in seat_labels(s["total_seats"]) for x in chosen): errors.append("Invalid seat selected.")
    for x in chosen:
        if not NAME_RE.match(f.get(f"name_{x}", "").strip()): errors.append(f"Enter a valid passenger name for seat {x}.")
    email, phone, method = f.get("email", "").strip(), f.get("phone", "").strip().replace(" ", "").replace("-", ""), f.get("payment_method", "")
    if not EMAIL_RE.match(email) or len(email) > 100: errors.append("Enter a valid email address.")
    if not PHONE_RE.match(phone): errors.append("Enter a valid Malaysian mobile number, e.g. 0123456789.")
    if method not in ("card", "fpx", "ewallet"): errors.append("Choose a payment method.")
    if errors:
        for e in errors: flash(e, "error")
        return render_seats(s, f, 400)
    fare_total, fee_total, total = calc_fare(s["fare"], len(chosen))
    ok, pay_ref = simulate_payment(method, total)
    if not ok: flash("Payment failed. Please try again.", "error"); return render_seats(s, f, 402)
    ref, db = "BK" + secrets.token_hex(4).upper(), get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        cur = db.execute("INSERT INTO bookings(reference,schedule_id,email,phone,fare_total,fee_total,total,payment_method,"
                         "payment_ref,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (ref, sid, email, phone, fare_total, fee_total, total, method, pay_ref, now_str()))
        for x in chosen:   # unique partial index rejects an already-booked seat
            db.execute("INSERT INTO tickets(booking_id,schedule_id,seat_no,passenger_name) VALUES(?,?,?,?)",
                       (cur.lastrowid, sid, x, f.get(f"name_{x}").strip()))
        db.execute("COMMIT")
    except sqlite3.IntegrityError:
        db.execute("ROLLBACK")
        flash("Sorry, one of those seats was just booked by someone else. Please pick another seat.", "error")
        return render_seats(s, None, 409)
    session["refs"] = session.get("refs", []) + [ref]
    flash(f"Payment approved (simulated). Booking {ref} confirmed.", "ok")
    return redirect(url_for("booking", ref=ref))

def load_booking(ref):
    db = get_db()
    b = db.execute("SELECT * FROM bookings WHERE reference=?", (ref,)).fetchone()
    if not b or not (ref in session.get("refs", []) or session.get("admin")): return None, None, None
    s = db.execute("SELECT * FROM schedules WHERE id=?", (b["schedule_id"],)).fetchone()
    t = db.execute("SELECT * FROM tickets WHERE booking_id=? ORDER BY seat_no", (b["id"],)).fetchall()
    return b, s, t

@app.route("/booking/<ref>")
def booking(ref):
    b, s, t = load_booking(ref)
    if not b: flash("Booking not found. Look it up with your reference and email.", "error"); return redirect(url_for("lookup"))
    return render_template("booking.html", b=b, s=s, tickets=t, cancel=cancellation_info(b, s))

@app.route("/booking/<ref>/cancel", methods=["POST"])
def cancel(ref):
    b, s, _ = load_booking(ref)
    if not b: return redirect(url_for("lookup"))
    ok, refund, msg = cancellation_info(b, s)
    if not ok: flash(msg, "error"); return redirect(url_for("booking", ref=ref))
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    db.execute("UPDATE bookings SET status='cancelled', refund_amount=?, cancelled_at=? WHERE id=? AND status='confirmed'",
               (refund, now_str(), b["id"]))
    db.execute("UPDATE tickets SET status='cancelled' WHERE booking_id=?", (b["id"],))   # frees the seats
    db.execute("COMMIT")
    flash(f"Booking cancelled. Refund of RM {refund:.2f} (simulated).", "ok")
    return redirect(url_for("booking", ref=ref))

@app.route("/lookup", methods=["GET", "POST"])
def lookup():
    if request.method == "POST":
        ref, email = request.form.get("reference", "").strip().upper(), request.form.get("email", "").strip()
        b = get_db().execute("SELECT reference FROM bookings WHERE reference=? AND lower(email)=lower(?)", (ref, email)).fetchone()
        if b:
            session["refs"] = session.get("refs", []) + [ref]
            return redirect(url_for("booking", ref=ref))
        flash("No booking matches that reference and email.", "error")
    mine = []
    if session.get("refs"):
        ph = ",".join("?" * len(session["refs"]))
        mine = get_db().execute(f"SELECT b.*, s.origin, s.destination, s.travel_date, s.departure_time FROM bookings b "
                                f"JOIN schedules s ON s.id=b.schedule_id WHERE reference IN ({ph}) ORDER BY b.id DESC",
                                session["refs"]).fetchall()
    return render_template("lookup.html", mine=mine)

# ---------- admin ----------
@app.route("/admin")
def admin():
    if not session.get("admin"): return render_template("admin.html", login=True)
    db = get_db()
    rows = db.execute("SELECT s.*, (SELECT COUNT(*) FROM tickets t WHERE t.schedule_id=s.id AND t.status='booked') AS booked "
                      "FROM schedules s WHERE travel_date>=? ORDER BY travel_date, departure_time, origin LIMIT 200",
                      (date.today().isoformat(),)).fetchall()
    edit = db.execute("SELECT * FROM schedules WHERE id=?", (request.args.get("edit", type=int),)).fetchone()
    return render_template("admin.html", login=False, rows=rows, edit=edit, today=date.today().isoformat())

@app.route("/admin/login", methods=["POST"])
def admin_login():
    if secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD): session["admin"] = True
    else: flash("Wrong password.", "error")
    return redirect(url_for("admin"))

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None); return redirect(url_for("index"))

@app.route("/admin/save", methods=["POST"])
@admin_required
def admin_save():
    f, db, errors = request.form, get_db(), []
    sid = f.get("id", type=int)
    v = {k: f.get(k, "").strip() for k in ("operator", "origin", "destination", "travel_date", "departure_time", "arrival_time", "status")}
    try: fare, seats_n = round(float(f.get("fare", "")), 2), int(f.get("total_seats", ""))
    except ValueError: fare, seats_n = 0, 0
    for k in ("operator", "origin", "destination"):
        if not 2 <= len(v[k]) <= 40: errors.append(f"{k.title()} must be 2-40 characters.")
    if v["origin"].lower() == v["destination"].lower(): errors.append("Origin and destination must differ.")
    if not parse_date(v["travel_date"]): errors.append("Invalid travel date.")
    if not (TIME_RE.match(v["departure_time"]) and TIME_RE.match(v["arrival_time"])): errors.append("Times must be HH:MM.")
    if not 1 <= fare <= 1000: errors.append("Fare must be between 1 and 1000.")
    if not (4 <= seats_n <= 60 and seats_n % 4 == 0): errors.append("Seats must be a multiple of 4 between 4 and 60.")
    if v["status"] not in ("active", "cancelled"): errors.append("Invalid status.")
    if sid and not errors:
        booked = taken_seats(db, sid)
        if booked and v["status"] == "cancelled": errors.append("Cannot cancel a schedule that has booked seats.")
        if any(seat_labels(60).index(x) >= seats_n for x in booked): errors.append("Seat count is below an already-booked seat.")
    if errors:
        for e in errors: flash(e, "error")
        return redirect(url_for("admin", edit=sid) if sid else url_for("admin"))
    vals = (v["operator"], v["origin"], v["destination"], v["travel_date"], v["departure_time"], v["arrival_time"], fare, seats_n, v["status"])
    if sid: db.execute("UPDATE schedules SET operator=?,origin=?,destination=?,travel_date=?,departure_time=?,arrival_time=?,"
                       "fare=?,total_seats=?,status=? WHERE id=?", vals + (sid,))
    else: db.execute("INSERT INTO schedules(operator,origin,destination,travel_date,departure_time,arrival_time,fare,"
                     "total_seats,status) VALUES(?,?,?,?,?,?,?,?,?)", vals)
    flash("Schedule saved.", "ok")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
