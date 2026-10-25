"""All input validation. Each function returns cleaned data plus a list of error messages."""
import re
from datetime import date, datetime
from seating import seat_labels

MAX_SEATS = 4
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'/@-]{1,59}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^(\+?60|0)1\d{8,9}$")   # Malaysian mobile
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

def parse_date(v):
    try: return datetime.strptime(v or "", "%Y-%m-%d").date()
    except ValueError: return None

def validate_search(origin, destination, date_str):
    """Return (date, error_message); one of them is None."""
    d = parse_date(date_str)
    if not origin or not destination: return None, "Enter both origin and destination."
    if origin.lower() == destination.lower(): return None, "Origin and destination must differ."
    if not d: return None, "Choose a valid travel date."
    if d < date.today(): return None, "Travel date cannot be in the past."
    return d, None

def validate_booking(f, total_seats):
    """Return (clean, errors) for the booking form."""
    errors = []
    seats = list(dict.fromkeys(f.getlist("seats")))
    if not seats: errors.append("Select at least one seat.")
    elif len(seats) > MAX_SEATS: errors.append(f"You can book at most {MAX_SEATS} seats at a time.")
    elif any(x not in seat_labels(total_seats) for x in seats): errors.append("Invalid seat selected.")
    names = {x: f.get(f"name_{x}", "").strip() for x in seats}
    errors += [f"Enter a valid passenger name for seat {x}." for x, n in names.items() if not NAME_RE.match(n)]
    email = f.get("email", "").strip()
    phone = f.get("phone", "").strip().replace(" ", "").replace("-", "")
    method = f.get("payment_method", "")
    if not EMAIL_RE.match(email) or len(email) > 100: errors.append("Enter a valid email address.")
    if not PHONE_RE.match(phone): errors.append("Enter a valid Malaysian mobile number, e.g. 0123456789.")
    if method not in ("card", "fpx", "ewallet"): errors.append("Choose a payment method.")
    return {"seats": seats, "names": names, "email": email, "phone": phone, "method": method}, errors

def validate_schedule(f):
    """Return (values, errors) for the admin schedule form."""
    errors = []
    v = {k: f.get(k, "").strip() for k in ("operator", "origin", "destination", "travel_date", "departure_time", "arrival_time", "status")}
    try: v["fare"], v["total_seats"] = round(float(f.get("fare", "")), 2), int(f.get("total_seats", ""))
    except ValueError: v["fare"], v["total_seats"] = 0, 0
    for k in ("operator", "origin", "destination"):
        if not 2 <= len(v[k]) <= 40: errors.append(f"{k.title()} must be 2-40 characters.")
    if v["origin"].lower() == v["destination"].lower(): errors.append("Origin and destination must differ.")
    if not parse_date(v["travel_date"]): errors.append("Invalid travel date.")
    if not (TIME_RE.match(v["departure_time"]) and TIME_RE.match(v["arrival_time"])): errors.append("Times must be HH:MM.")
    if not 1 <= v["fare"] <= 1000: errors.append("Fare must be between 1 and 1000.")
    if not (4 <= v["total_seats"] <= 60 and v["total_seats"] % 4 == 0): errors.append("Seats must be a multiple of 4 between 4 and 60.")
    if v["status"] not in ("active", "cancelled"): errors.append("Invalid status.")
    return v, errors
