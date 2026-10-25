"""Input validation. Errors are collected as {field_key: message} and raised together."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from models import BookingRequest, Contact, Passenger
from services.errors import ValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{9,13}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'/-]{1,59}$")
BUS_TYPES = ("Express", "VIP", "Sleeper")
GENDERS = ("M", "F")
SCHEDULE_STATUSES = ("ACTIVE", "CANCELLED")
TIME_FORMAT = "%Y-%m-%d %H:%M"
GENERIC_MESSAGE = "Please correct the highlighted fields."


def raise_if_errors(errors):
    if errors:
        raise ValidationError(GENERIC_MESSAGE, errors)


def text(value):
    return value.strip() if isinstance(value, str) else ""


def parse_int(value):
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_datetime(value):
    try:
        return datetime.strptime(text(value).replace("T", " "), TIME_FORMAT)
    except ValueError:
        return None


def parse_fare_sen(value):
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0 or amount > 1000 or amount.as_tuple().exponent < -2:
        return None
    return int(amount * 100)


# ---- search ----
def validate_search(args):
    errors = {}
    origin, destination = text(args.get("origin")), text(args.get("destination"))
    travel_date = text(args.get("date"))
    if not origin:
        errors["origin"] = "Origin is required."
    if not destination:
        errors["destination"] = "Destination is required."
    if origin and destination and origin.lower() == destination.lower():
        errors["destination"] = "Destination must be different from origin."
    parsed = parse_date(travel_date)
    if parsed is None:
        errors["date"] = "Travel date must be in YYYY-MM-DD format."
    elif parsed < date.today():
        errors["date"] = "Travel date cannot be in the past."
    raise_if_errors(errors)
    return {"origin": origin, "destination": destination, "date": travel_date}


# ---- booking ----
def validate_contact(raw, errors):
    raw = raw if isinstance(raw, dict) else {}
    email = text(raw.get("email"))
    phone = re.sub(r"[\s-]", "", text(raw.get("phone")))
    if not EMAIL_RE.match(email):
        errors["contact.email"] = "Enter a valid email address."
    if not PHONE_RE.match(phone):
        errors["contact.phone"] = "Enter a valid phone number (9-13 digits)."
    return Contact(email.lower(), phone)


def validate_passenger(raw, index, total_seats, errors):
    raw = raw if isinstance(raw, dict) else {}
    key = f"passengers.{index}"
    seat, age = parse_int(raw.get("seat_number")), parse_int(raw.get("age"))
    name, gender = text(raw.get("name")), text(raw.get("gender")).upper()
    if seat is None or not 1 <= seat <= total_seats:
        errors[f"{key}.seat_number"] = f"Seat must be between 1 and {total_seats}."
    if not NAME_RE.match(name):
        errors[f"{key}.name"] = "Enter a valid name (2-60 letters)."
    if age is None or not 1 <= age <= 120:
        errors[f"{key}.age"] = "Age must be between 1 and 120."
    if gender not in GENDERS:
        errors[f"{key}.gender"] = "Select a gender."
    return Passenger(seat, name, age, gender)


def validate_booking_request(payload, schedule_id, total_seats, max_seats):
    errors = {}
    raw_passengers = payload.get("passengers")
    if not isinstance(raw_passengers, list) or not raw_passengers:
        errors["passengers"] = "Select at least one seat."
        raw_passengers = []
    elif len(raw_passengers) > max_seats:
        errors["passengers"] = f"You can book at most {max_seats} seats at a time."
    contact = validate_contact(payload.get("contact"), errors)
    passengers = tuple(
        validate_passenger(p, i, total_seats, errors) for i, p in enumerate(raw_passengers)
    )
    seats = [p.seat_number for p in passengers]
    if len(set(seats)) != len(seats):
        errors["passengers"] = "Each seat can only be selected once."
    raise_if_errors(errors)
    return BookingRequest(schedule_id, contact, passengers)


# ---- admin schedule ----
def validate_schedule_payload(payload):
    errors = {}
    operator, origin = text(payload.get("operator")), text(payload.get("origin"))
    destination, bus_type = text(payload.get("destination")), text(payload.get("bus_type"))
    status = text(payload.get("status")) or "ACTIVE"
    if not operator:
        errors["operator"] = "Operator is required."
    if bus_type not in BUS_TYPES:
        errors["bus_type"] = f"Bus type must be one of: {', '.join(BUS_TYPES)}."
    if not origin:
        errors["origin"] = "Origin is required."
    if not destination:
        errors["destination"] = "Destination is required."
    if origin and destination and origin.lower() == destination.lower():
        errors["destination"] = "Destination must be different from origin."
    departure, arrival = parse_datetime(payload.get("departure_time")), parse_datetime(payload.get("arrival_time"))
    if departure is None:
        errors["departure_time"] = "Departure must be a valid date and time."
    if arrival is None:
        errors["arrival_time"] = "Arrival must be a valid date and time."
    elif departure is not None and arrival <= departure:
        errors["arrival_time"] = "Arrival must be after departure."
    fare_sen = parse_fare_sen(payload.get("fare_rm"))
    if fare_sen is None:
        errors["fare_rm"] = "Fare must be between RM 0.01 and RM 1000.00."
    total_seats = parse_int(payload.get("total_seats"))
    if total_seats is None or not 1 <= total_seats <= 60:
        errors["total_seats"] = "Total seats must be between 1 and 60."
    if status not in SCHEDULE_STATUSES:
        errors["status"] = "Status must be ACTIVE or CANCELLED."
    raise_if_errors(errors)
    return {
        "operator": operator, "bus_type": bus_type, "origin": origin, "destination": destination,
        "departure_time": departure.strftime(TIME_FORMAT), "arrival_time": arrival.strftime(TIME_FORMAT),
        "fare_sen": fare_sen, "total_seats": total_seats, "status": status,
    }
