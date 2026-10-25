"""All SQL touching bookings and booking_seats."""
from database import fetch_all, fetch_one


def reference_exists(conn, reference):
    return conn.execute("SELECT 1 FROM bookings WHERE reference = ?", (reference,)).fetchone() is not None


def insert_booking(conn, reference, schedule_id, contact, total_fare_sen):
    cur = conn.execute(
        """INSERT INTO bookings (reference, schedule_id, contact_email, contact_phone, total_fare_sen)
           VALUES (?, ?, ?, ?, ?)""",
        (reference, schedule_id, contact.email, contact.phone, total_fare_sen),
    )
    return cur.lastrowid


def insert_seats(conn, booking_id, schedule_id, passengers):
    """Raises sqlite3.IntegrityError if any seat is already actively booked."""
    conn.executemany(
        """INSERT INTO booking_seats (booking_id, schedule_id, seat_number,
                                      passenger_name, passenger_age, passenger_gender)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [(booking_id, schedule_id, p.seat_number, p.name, p.age, p.gender) for p in passengers],
    )


def get_by_reference(conn, reference):
    return fetch_one(conn, "SELECT * FROM bookings WHERE reference = ?", (reference,))


def get_seats(conn, booking_id):
    return fetch_all(
        conn,
        """SELECT seat_number, passenger_name, passenger_age, passenger_gender
           FROM booking_seats WHERE booking_id = ? ORDER BY seat_number""",
        (booking_id,),
    )


def mark_cancelled(conn, booking_id, cancelled_at):
    conn.execute(
        "UPDATE bookings SET status = 'CANCELLED', cancelled_at = ? WHERE id = ?",
        (cancelled_at, booking_id),
    )


def release_seats(conn, booking_id):
    conn.execute("UPDATE booking_seats SET is_active = 0 WHERE booking_id = ?", (booking_id,))
