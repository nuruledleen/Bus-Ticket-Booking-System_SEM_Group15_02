"""Booking workflow: coordinates fare, payment, repository and transactions. No Flask objects here."""
import secrets, sqlite3
from datetime import datetime
import repository as repo
from database import transaction
from fare import calc_fare, refund_for

class SeatConflict(Exception): pass
class PaymentFailed(Exception): pass

def dep_dt(s): return datetime.strptime(f"{s['travel_date']} {s['departure_time']}", "%Y-%m-%d %H:%M")

def simulate_payment(method, amount):
    """Fake gateway: always approves. Replace with a real gateway call in production."""
    return True, "SIM-" + secrets.token_hex(4).upper()

def create_booking(db, s, clean):
    """Create a booking and its tickets atomically; return the booking reference."""
    n = len(clean["seats"])
    fare_total, fee_total, total = calc_fare(s["fare"], n)
    ok, pay_ref = simulate_payment(clean["method"], total)
    if not ok: raise PaymentFailed()
    ref = "BK" + secrets.token_hex(4).upper()
    try:
        with transaction(db):
            bid = repo.insert_booking(db, s["id"], ref, clean, fare_total, fee_total, total, pay_ref)
            for seat in clean["seats"]:   # unique partial index rejects an already-booked seat
                repo.insert_ticket(db, bid, s["id"], seat, clean["names"][seat])
    except sqlite3.IntegrityError:
        raise SeatConflict()
    return ref

def cancellation_info(b, s):
    if b["status"] != "confirmed": return False, 0.0, "This booking is already cancelled."
    return refund_for((dep_dt(s) - datetime.now()).total_seconds() / 3600, b["fare_total"])

def cancel_booking(db, b, s):
    """Return (cancelled, refund, message)."""
    ok, refund, msg = cancellation_info(b, s)
    if ok:
        with transaction(db): repo.cancel_booking_rows(db, b["id"], refund)
    return ok, refund, msg
