"""All SQL lives here. Other modules never see table or column names."""
from database import now_str

def list_cities(db):
    return [r[0] for r in db.execute("SELECT origin FROM schedules UNION SELECT destination FROM schedules ORDER BY 1")]

def search_schedules(db, origin, destination, date_iso):
    return db.execute("SELECT s.*, s.total_seats-(SELECT COUNT(*) FROM tickets t WHERE t.schedule_id=s.id AND "
                      "t.status='booked') AS available FROM schedules s WHERE lower(origin)=lower(?) AND "
                      "lower(destination)=lower(?) AND travel_date=? AND status='active' ORDER BY departure_time",
                      (origin, destination, date_iso)).fetchall()

def get_schedule(db, sid):
    return db.execute("SELECT * FROM schedules WHERE id=?", (sid,)).fetchone()

def taken_seats(db, sid):
    return {r[0] for r in db.execute("SELECT seat_no FROM tickets WHERE schedule_id=? AND status='booked'", (sid,))}

def insert_booking(db, sid, ref, c, fare_total, fee_total, total, pay_ref):
    return db.execute("INSERT INTO bookings(reference,schedule_id,email,phone,fare_total,fee_total,total,payment_method,"
                      "payment_ref,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (ref, sid, c["email"], c["phone"], fare_total, fee_total, total, c["method"], pay_ref, now_str())).lastrowid

def insert_ticket(db, booking_id, sid, seat, name):
    db.execute("INSERT INTO tickets(booking_id,schedule_id,seat_no,passenger_name) VALUES(?,?,?,?)", (booking_id, sid, seat, name))

def get_booking(db, ref):
    return db.execute("SELECT * FROM bookings WHERE reference=?", (ref,)).fetchone()

def get_tickets(db, booking_id):
    return db.execute("SELECT * FROM tickets WHERE booking_id=? ORDER BY seat_no", (booking_id,)).fetchall()

def find_booking(db, ref, email):
    return db.execute("SELECT reference FROM bookings WHERE reference=? AND lower(email)=lower(?)", (ref, email)).fetchone()

def bookings_for_refs(db, refs):
    ph = ",".join("?" * len(refs))
    return db.execute(f"SELECT b.*, s.origin, s.destination, s.travel_date, s.departure_time FROM bookings b "
                      f"JOIN schedules s ON s.id=b.schedule_id WHERE reference IN ({ph}) ORDER BY b.id DESC", refs).fetchall()

def cancel_booking_rows(db, booking_id, refund):
    db.execute("UPDATE bookings SET status='cancelled', refund_amount=?, cancelled_at=? WHERE id=? AND status='confirmed'",
               (refund, now_str(), booking_id))
    db.execute("UPDATE tickets SET status='cancelled' WHERE booking_id=?", (booking_id,))   # frees the seats

def admin_schedules(db, from_date):
    return db.execute("SELECT s.*, (SELECT COUNT(*) FROM tickets t WHERE t.schedule_id=s.id AND t.status='booked') AS booked "
                      "FROM schedules s WHERE travel_date>=? ORDER BY travel_date, departure_time, origin LIMIT 200", (from_date,)).fetchall()

_COLS = ("operator", "origin", "destination", "travel_date", "departure_time", "arrival_time", "fare", "total_seats", "status")
def save_schedule(db, v, sid=None):
    vals = tuple(v[c] for c in _COLS)
    if sid: db.execute("UPDATE schedules SET operator=?,origin=?,destination=?,travel_date=?,departure_time=?,arrival_time=?,"
                       "fare=?,total_seats=?,status=? WHERE id=?", vals + (sid,))
    else: db.execute("INSERT INTO schedules(operator,origin,destination,travel_date,departure_time,arrival_time,fare,"
                     "total_seats,status) VALUES(?,?,?,?,?,?,?,?,?)", vals)
