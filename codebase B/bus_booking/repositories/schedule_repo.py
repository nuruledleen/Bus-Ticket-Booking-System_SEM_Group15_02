"""All SQL touching the schedules table (and seat availability counts)."""
from database import fetch_all, fetch_one

_SELECT = """
SELECT s.*,
       s.total_seats - (SELECT COUNT(*) FROM booking_seats bs
                        WHERE bs.schedule_id = s.id AND bs.is_active = 1) AS seats_available
FROM schedules s
"""


def get(conn, schedule_id):
    return fetch_one(conn, _SELECT + " WHERE s.id = ?", (schedule_id,))


def search(conn, origin, destination, travel_date, now_text):
    sql = _SELECT + """
        WHERE lower(s.origin) = lower(?) AND lower(s.destination) = lower(?)
          AND date(s.departure_time) = ? AND s.status = 'ACTIVE'
          AND s.departure_time > ?
        ORDER BY s.departure_time"""
    return fetch_all(conn, sql, (origin, destination, travel_date, now_text))


def list_upcoming(conn, now_text, limit=100):
    sql = _SELECT + " WHERE s.departure_time >= ? ORDER BY s.departure_time LIMIT ?"
    return fetch_all(conn, sql, (now_text, limit))


def list_cities(conn):
    rows = fetch_all(conn, """SELECT origin AS city FROM schedules
                              UNION SELECT destination FROM schedules ORDER BY city""")
    return [row["city"] for row in rows]


def insert(conn, data):
    cur = conn.execute(
        """INSERT INTO schedules (operator, bus_type, origin, destination, departure_time,
                                  arrival_time, fare_sen, total_seats, status)
           VALUES (:operator, :bus_type, :origin, :destination, :departure_time,
                   :arrival_time, :fare_sen, :total_seats, :status)""",
        data,
    )
    return cur.lastrowid


def update(conn, schedule_id, data):
    conn.execute(
        """UPDATE schedules SET operator = :operator, bus_type = :bus_type, origin = :origin,
               destination = :destination, departure_time = :departure_time,
               arrival_time = :arrival_time, fare_sen = :fare_sen,
               total_seats = :total_seats, status = :status
           WHERE id = :id""",
        {**data, "id": schedule_id},
    )


def booked_seat_numbers(conn, schedule_id):
    rows = conn.execute(
        "SELECT seat_number FROM booking_seats WHERE schedule_id = ? AND is_active = 1",
        (schedule_id,),
    )
    return {row["seat_number"] for row in rows}


def highest_booked_seat(conn, schedule_id):
    row = fetch_one(
        conn,
        "SELECT COALESCE(MAX(seat_number), 0) AS n FROM booking_seats "
        "WHERE schedule_id = ? AND is_active = 1",
        (schedule_id,),
    )
    return row["n"]
