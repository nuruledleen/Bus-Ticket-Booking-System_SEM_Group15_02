import sqlite3

import pytest
from datetime import datetime, timedelta

from repositories import schedule_repo
from services.fare import calculate_total_fare
from services.validation import TIME_FORMAT


def book(client, payload):
    return client.post("/api/bookings", json=payload)


def seat_available(client, schedule_id, number):
    seats = client.get(f"/api/schedules/{schedule_id}/seats").get_json()["seats"]
    return next(s for s in seats if s["number"] == number)["available"]


def test_create_booking_calculates_total(client, app, schedule, make_payload):
    res = book(client, make_payload(schedule["id"], seats=(5, 6)))
    assert res.status_code == 201
    booking = res.get_json()["booking"]
    expected = calculate_total_fare(schedule["fare_sen"], 2, app.config["SERVICE_FEE_SEN"])["total_sen"]
    assert booking["total_fare_sen"] == expected
    assert booking["status"] == "CONFIRMED" and len(booking["seats"]) == 2
    assert booking["contact_phone"] == "0123456789"  # normalised
    assert client.get(f"/api/bookings/{booking['reference']}").status_code == 200


def test_duplicate_seat_is_rejected_atomically(client, schedule, make_payload):
    assert book(client, make_payload(schedule["id"], seats=(5,))).status_code == 201
    res = book(client, make_payload(schedule["id"], seats=(6, 5)))
    assert res.status_code == 409 and res.get_json()["error"]["code"] == "conflict"
    assert seat_available(client, schedule["id"], 6)  # rolled back, seat 6 not taken


def test_database_constraint_blocks_duplicate_active_seat(client, conn, schedule, make_payload):
    booking = book(client, make_payload(schedule["id"])).get_json()["booking"]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO booking_seats (booking_id, schedule_id, seat_number, passenger_name, "
            "passenger_age, passenger_gender) VALUES (?, ?, 5, 'X Y', 20, 'F')",
            (booking["id"], schedule["id"]),
        )


def test_invalid_passenger_details_return_field_errors(client, schedule, make_payload):
    payload = make_payload(schedule["id"])
    payload["passengers"][0].update(name="1", age=500, gender="Z", seat_number=99)
    payload["contact"] = {"email": "nope", "phone": "abc"}
    res = book(client, payload)
    assert res.status_code == 422
    details = res.get_json()["error"]["details"]
    for key in ("passengers.0.name", "passengers.0.age", "passengers.0.gender",
                "passengers.0.seat_number", "contact.email", "contact.phone"):
        assert key in details


def test_too_many_seats_rejected(client, schedule, make_payload):
    res = book(client, make_payload(schedule["id"], seats=range(10, 17)))
    assert res.status_code == 422


def test_cancel_frees_seat_and_allows_rebooking(client, schedule, make_payload):
    booking = book(client, make_payload(schedule["id"])).get_json()["booking"]
    res = client.post(f"/api/bookings/{booking['reference']}/cancel")
    assert res.status_code == 200 and res.get_json()["booking"]["status"] == "CANCELLED"
    assert seat_available(client, schedule["id"], 5)
    assert book(client, make_payload(schedule["id"])).status_code == 201
    assert client.post(f"/api/bookings/{booking['reference']}/cancel").status_code == 409


def test_cancel_blocked_close_to_departure(client, app, conn, make_payload):
    departure = datetime.now() + timedelta(hours=1)
    schedule_id = schedule_repo.insert(conn, {
        "operator": "Soon Bus", "bus_type": "Express", "origin": "Ipoh", "destination": "Melaka",
        "departure_time": departure.strftime(TIME_FORMAT),
        "arrival_time": (departure + timedelta(hours=3)).strftime(TIME_FORMAT),
        "fare_sen": 2000, "total_seats": 10, "status": "ACTIVE",
    })
    booking = book(client, make_payload(schedule_id, seats=(1,))).get_json()["booking"]
    assert booking["can_cancel"] is False
    res = client.post(f"/api/bookings/{booking['reference']}/cancel")
    assert res.status_code == 409 and "hours before departure" in res.get_json()["error"]["message"]


def test_unknown_booking_is_404(client):
    res = client.get("/api/bookings/NOSUCHREF")
    assert res.status_code == 404 and res.get_json()["error"]["code"] == "not_found"
