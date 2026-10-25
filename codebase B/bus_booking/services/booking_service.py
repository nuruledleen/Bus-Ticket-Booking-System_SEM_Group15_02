"""Booking rules: create, view and cancel. Every write runs in one transaction."""
import secrets
import sqlite3
from datetime import datetime, timedelta

from database import transaction
from repositories import booking_repo
from services import schedule_service
from services.errors import ConflictError, NotFoundError, ValidationError
from services.fare import calculate_total_fare
from services.validation import GENERIC_MESSAGE, TIME_FORMAT, parse_int, validate_booking_request


def parse_time(value):
    return datetime.strptime(value, TIME_FORMAT)


def _require_bookable_schedule(conn, schedule_id, now):
    schedule = schedule_service.get_schedule(conn, schedule_id)
    if schedule["status"] != "ACTIVE":
        raise ConflictError("This schedule is no longer available.")
    if parse_time(schedule["departure_time"]) <= now:
        raise ConflictError("This bus has already departed.")
    return schedule


def _new_reference(conn):
    while True:
        reference = secrets.token_hex(4).upper()
        if not booking_repo.reference_exists(conn, reference):
            return reference


def _insert_seats_or_conflict(conn, booking_id, request):
    try:
        booking_repo.insert_seats(conn, booking_id, request.schedule_id, request.passengers)
    except sqlite3.IntegrityError as exc:  # unique index uq_active_seat
        raise ConflictError("One or more selected seats were just booked. Please choose different seats.") from exc


def cancellation_block_reason(booking, schedule, now, cutoff_hours):
    """Single source of truth for cancellation eligibility. None means cancellable."""
    if booking["status"] == "CANCELLED":
        return "This booking is already cancelled."
    if now > parse_time(schedule["departure_time"]) - timedelta(hours=cutoff_hours):
        return f"Bookings can only be cancelled up to {cutoff_hours} hours before departure."
    return None


def _load_booking_and_schedule(conn, reference):
    booking = booking_repo.get_by_reference(conn, (reference or "").strip().upper())
    if booking is None:
        raise NotFoundError("Booking not found.")
    return booking, schedule_service.get_schedule(conn, booking["schedule_id"])


def get_booking_view(conn, reference, settings, now=None):
    now = now or datetime.now()
    booking, schedule = _load_booking_and_schedule(conn, reference)
    reason = cancellation_block_reason(booking, schedule, now, settings["CANCELLATION_CUTOFF_HOURS"])
    return {
        **booking,
        "schedule": schedule,
        "seats": booking_repo.get_seats(conn, booking["id"]),
        "can_cancel": reason is None,
        "cancel_blocked_reason": reason,
    }


def create_booking(conn, payload, settings, now=None):
    now = now or datetime.now()
    schedule_id = parse_int(payload.get("schedule_id"))
    if schedule_id is None:
        raise ValidationError(GENERIC_MESSAGE, {"schedule_id": "A valid schedule is required."})
    with transaction(conn):
        schedule = _require_bookable_schedule(conn, schedule_id, now)
        request = validate_booking_request(
            payload, schedule_id, schedule["total_seats"], settings["MAX_SEATS_PER_BOOKING"]
        )
        fare = calculate_total_fare(schedule["fare_sen"], len(request.passengers), settings["SERVICE_FEE_SEN"])
        reference = _new_reference(conn)
        booking_id = booking_repo.insert_booking(conn, reference, schedule_id, request.contact, fare["total_sen"])
        _insert_seats_or_conflict(conn, booking_id, request)
    return get_booking_view(conn, reference, settings, now)


def cancel_booking(conn, reference, settings, now=None):
    now = now or datetime.now()
    with transaction(conn):
        booking, schedule = _load_booking_and_schedule(conn, reference)
        reason = cancellation_block_reason(booking, schedule, now, settings["CANCELLATION_CUTOFF_HOURS"])
        if reason:
            raise ConflictError(reason)
        booking_repo.mark_cancelled(conn, booking["id"], now.strftime("%Y-%m-%d %H:%M:%S"))
        booking_repo.release_seats(conn, booking["id"])
    return get_booking_view(conn, booking["reference"], settings, now)
