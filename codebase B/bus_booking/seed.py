"""Sample data: 8 days of departures on 4 routes (both directions) plus one sample booking."""
from datetime import date, datetime, timedelta

from database import transaction
from repositories import schedule_repo
from services import booking_service
from services.validation import TIME_FORMAT

ROUTES = [  # origin, destination, travel hours, base fare in sen
    ("Kuala Lumpur", "Penang", 5, 4500),
    ("Kuala Lumpur", "Johor Bahru", 5, 3800),
    ("Kuala Lumpur", "Ipoh", 3, 2200),
    ("Kuala Lumpur", "Melaka", 2, 1600),
]
OPERATORS = [("Transnasional", "Express"), ("Billion Stars", "VIP"), ("Aeroline", "Sleeper")]
DEPARTURE_TIMES = ["08:00", "14:00", "22:00"]
DAYS = 8


def build_schedules(today):
    for day in range(DAYS):
        for origin, destination, hours, fare in ROUTES:
            for start, end in ((origin, destination), (destination, origin)):
                for i, hhmm in enumerate(DEPARTURE_TIMES):
                    operator, bus_type = OPERATORS[i]
                    departure = datetime.strptime(f"{today + timedelta(days=day)} {hhmm}", TIME_FORMAT)
                    yield {
                        "operator": operator, "bus_type": bus_type, "origin": start, "destination": end,
                        "departure_time": departure.strftime(TIME_FORMAT),
                        "arrival_time": (departure + timedelta(hours=hours)).strftime(TIME_FORMAT),
                        "fare_sen": fare + i * 500, "total_seats": 40, "status": "ACTIVE",
                    }


def seed(conn, settings, today=None):
    today = today or date.today()
    with transaction(conn):
        for data in build_schedules(today):
            schedule_repo.insert(conn, data)
    tomorrow = (today + timedelta(days=1)).isoformat()
    first = schedule_repo.search(conn, "Kuala Lumpur", "Penang", tomorrow, "2000-01-01 00:00")[0]
    booking_service.create_booking(conn, {
        "schedule_id": first["id"],
        "contact": {"email": "sample@example.com", "phone": "0123456789"},
        "passengers": [
            {"seat_number": 1, "name": "Aisyah Rahman", "age": 28, "gender": "F"},
            {"seat_number": 2, "name": "Daniel Tan", "age": 31, "gender": "M"},
        ],
    }, settings)
