"""BusGo MY - Flask routes only. Validation, fares, SQL and booking rules live in their own modules."""
import os, secrets
from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
import database, repository as repo
from database import get_db, close_db
from fare import SERVICE_FEE
from seating import seat_labels, seat_rows
from validation import MAX_SEATS, validate_search, validate_booking, validate_schedule
from booking_service import dep_dt, create_booking, cancel_booking, cancellation_info, SeatConflict, PaymentFailed

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["DATABASE"] = os.environ.get("BUS_DB", os.path.join(app.root_path, "busbooking.db"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
app.teardown_appcontext(close_db)
app.jinja_env.filters["rm"] = lambda v: f"RM {float(v):,.2f}"

def init_db(reset=False): database.init_db(app, reset)

@app.cli.command("init-db")
def init_db_cmd():
    """flask --app app init-db  (set RESET=1 to rebuild)"""
    init_db(reset=os.environ.get("RESET") == "1")
    print("Database ready:", app.config["DATABASE"])

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"):
            flash("Please log in as administrator.", "error"); return redirect(url_for("admin"))
        return f(*a, **k)
    return w

def get_open_schedule(sid):
    s = repo.get_schedule(get_db(), sid)
    if not s or s["status"] != "active" or dep_dt(s) <= datetime.now(): return None
    return s

# ---------- customer pages ----------
@app.route("/")
def index():
    db = get_db()
    q = {k: request.args.get(k, "").strip() for k in ("origin", "destination", "travel_date")}
    results = None
    if request.args:
        d, err = validate_search(q["origin"], q["destination"], q["travel_date"])
        if err: flash(err, "error")
        else: results = [r for r in repo.search_schedules(db, q["origin"], q["destination"], d.isoformat()) if dep_dt(r) > datetime.now()]
    return render_template("index.html", cities=repo.list_cities(db), q=q, results=results, today=date.today().isoformat())

def render_seats(s, form=None, status=200):
    form = form or {}
    names = {k[5:]: v for k, v in form.items() if k.startswith("name_")}
    return render_template("seats.html", s=s, rows=seat_rows(s["total_seats"]), taken=repo.taken_seats(get_db(), s["id"]),
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
    clean, errors = validate_booking(request.form, s["total_seats"])
    if errors:
        for e in errors: flash(e, "error")
        return render_seats(s, request.form, 400)
    try: ref = create_booking(get_db(), s, clean)
    except PaymentFailed: flash("Payment failed. Please try again.", "error"); return render_seats(s, request.form, 402)
    except SeatConflict:
        flash("Sorry, one of those seats was just booked by someone else. Please pick another seat.", "error")
        return render_seats(s, None, 409)
    session["refs"] = session.get("refs", []) + [ref]
    flash(f"Payment approved (simulated). Booking {ref} confirmed.", "ok")
    return redirect(url_for("booking", ref=ref))

def load_booking(ref):
    db = get_db()
    b = repo.get_booking(db, ref)
    if not b or not (ref in session.get("refs", []) or session.get("admin")): return None, None, None
    return b, repo.get_schedule(db, b["schedule_id"]), repo.get_tickets(db, b["id"])

@app.route("/booking/<ref>")
def booking(ref):
    b, s, t = load_booking(ref)
    if not b: flash("Booking not found. Look it up with your reference and email.", "error"); return redirect(url_for("lookup"))
    return render_template("booking.html", b=b, s=s, tickets=t, cancel=cancellation_info(b, s))

@app.route("/booking/<ref>/cancel", methods=["POST"])
def cancel(ref):
    b, s, _ = load_booking(ref)
    if not b: return redirect(url_for("lookup"))
    ok, refund, msg = cancel_booking(get_db(), b, s)
    if ok: flash(f"Booking cancelled. Refund of RM {refund:.2f} (simulated).", "ok")
    else: flash(msg, "error")
    return redirect(url_for("booking", ref=ref))

@app.route("/lookup", methods=["GET", "POST"])
def lookup():
    db = get_db()
    if request.method == "POST":
        ref, email = request.form.get("reference", "").strip().upper(), request.form.get("email", "").strip()
        if repo.find_booking(db, ref, email):
            session["refs"] = session.get("refs", []) + [ref]
            return redirect(url_for("booking", ref=ref))
        flash("No booking matches that reference and email.", "error")
    mine = repo.bookings_for_refs(db, session["refs"]) if session.get("refs") else []
    return render_template("lookup.html", mine=mine)

# ---------- admin ----------
@app.route("/admin")
def admin():
    if not session.get("admin"): return render_template("admin.html", login=True)
    db = get_db()
    return render_template("admin.html", login=False, rows=repo.admin_schedules(db, date.today().isoformat()),
                           edit=repo.get_schedule(db, request.args.get("edit", type=int)), today=date.today().isoformat())

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
    db, sid = get_db(), request.form.get("id", type=int)
    v, errors = validate_schedule(request.form)
    if sid and not errors:
        booked = repo.taken_seats(db, sid)
        if booked and v["status"] == "cancelled": errors.append("Cannot cancel a schedule that has booked seats.")
        if any(seat_labels(60).index(x) >= v["total_seats"] for x in booked): errors.append("Seat count is below an already-booked seat.")
    if errors:
        for e in errors: flash(e, "error")
        return redirect(url_for("admin", edit=sid) if sid else url_for("admin"))
    repo.save_schedule(db, v, sid)
    flash("Schedule saved.", "ok")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
