import base64

from tests.conftest import tomorrow

AUTH = {"Authorization": "Basic " + base64.b64encode(b"admin:admin123").decode()}


def new_schedule_payload(**overrides):
    payload = {
        "operator": "Test Bus", "bus_type": "Express", "origin": "Kuala Lumpur", "destination": "Ipoh",
        "departure_time": f"{tomorrow()}T09:00", "arrival_time": f"{tomorrow()}T11:30",
        "fare_rm": "25.50", "total_seats": 30, "status": "ACTIVE",
    }
    return {**payload, **overrides}


def test_admin_requires_authentication(client):
    assert client.get("/admin/").status_code == 401
    assert client.post("/admin/api/schedules", json=new_schedule_payload()).status_code == 401


def test_admin_page_loads(client):
    assert client.get("/admin/", headers=AUTH).status_code == 200


def test_admin_can_add_and_update_schedule(client):
    res = client.post("/admin/api/schedules", json=new_schedule_payload(), headers=AUTH)
    assert res.status_code == 201
    schedule = res.get_json()["schedule"]
    assert schedule["fare_sen"] == 2550 and schedule["seats_available"] == 30

    res = client.put(f"/admin/api/schedules/{schedule['id']}",
                     json=new_schedule_payload(fare_rm="30.00"), headers=AUTH)
    assert res.status_code == 200 and res.get_json()["schedule"]["fare_sen"] == 3000


def test_admin_validation_errors(client):
    res = client.post("/admin/api/schedules",
                      json=new_schedule_payload(fare_rm="-1", arrival_time=f"{tomorrow()}T08:00"), headers=AUTH)
    assert res.status_code == 422
    assert {"fare_rm", "arrival_time"} <= set(res.get_json()["error"]["details"])


def test_cannot_reduce_seats_below_booked_seat(client, make_payload):
    created = client.post("/admin/api/schedules", json=new_schedule_payload(), headers=AUTH).get_json()["schedule"]
    assert client.post("/api/bookings", json=make_payload(created["id"], seats=(25,))).status_code == 201
    res = client.put(f"/admin/api/schedules/{created['id']}", json=new_schedule_payload(total_seats=20), headers=AUTH)
    assert res.status_code == 409
