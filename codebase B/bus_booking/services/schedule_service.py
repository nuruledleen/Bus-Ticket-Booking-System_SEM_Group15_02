"""Searching, seat maps, quotes and admin schedule management."""
from datetime import datetime

from database import transaction
from repositories import schedule_repo
from services.errors import ConflictError, NotFoundError, ValidationError
from services.fare import calculate_total_fare
from services.validation import TIME_FORMAT, parse_int, validate_schedule_payload, validate_search


def get_schedule(conn, schedule_id):
    schedule = schedule_repo.get(conn, schedule_id)
    if schedule is None:
        raise NotFoundError("Schedule not found.")
    return schedule


def list_cities(conn):
    return schedule_repo.list_cities(conn)


def search_schedules(conn, args, now=None):
    criteria = validate_search(args)
    now_text = (now or datetime.now()).strftime(TIME_FORMAT)
    results = schedule_repo.search(conn, criteria["origin"], criteria["destination"], criteria["date"], now_text)
    return criteria, results


def seat_map(conn, schedule_id):
    schedule = get_schedule(conn, schedule_id)
    taken = schedule_repo.booked_seat_numbers(conn, schedule_id)
    seats = [{"number": n, "available": n not in taken} for n in range(1, schedule["total_seats"] + 1)]
    return {"schedule": schedule, "seats": seats}


def quote(conn, schedule_id, seat_count_raw, settings):
    schedule = get_schedule(conn, schedule_id)
    max_seats = settings["MAX_SEATS_PER_BOOKING"]
    seat_count = parse_int(seat_count_raw)
    if seat_count is None or not 1 <= seat_count <= max_seats:
        raise ValidationError("Invalid seat count.", {"seat_count": f"Choose between 1 and {max_seats} seats."})
    return calculate_total_fare(schedule["fare_sen"], seat_count, settings["SERVICE_FEE_SEN"])


def list_upcoming_schedules(conn, now=None):
    return schedule_repo.list_upcoming(conn, (now or datetime.now()).strftime(TIME_FORMAT))


def create_schedule(conn, payload):
    data = validate_schedule_payload(payload)
    with transaction(conn):
        schedule_id = schedule_repo.insert(conn, data)
    return schedule_repo.get(conn, schedule_id)


def update_schedule(conn, schedule_id, payload):
    data = validate_schedule_payload(payload)
    with transaction(conn):
        get_schedule(conn, schedule_id)
        highest = schedule_repo.highest_booked_seat(conn, schedule_id)
        if data["total_seats"] < highest:
            raise ConflictError(f"Seat {highest} is already booked; total seats cannot be lower than that.")
        schedule_repo.update(conn, schedule_id, data)
    return schedule_repo.get(conn, schedule_id)
