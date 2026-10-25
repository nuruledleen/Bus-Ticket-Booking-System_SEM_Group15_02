from datetime import date, timedelta

from tests.conftest import tomorrow


def test_search_returns_schedules(client):
    res = client.get("/", query_string={"origin": "Kuala Lumpur", "destination": "Penang", "date": tomorrow()})
    assert res.status_code == 200
    assert b"Select seats" in res.data


def test_search_is_case_insensitive(client):
    res = client.get("/", query_string={"origin": "kuala lumpur", "destination": "PENANG", "date": tomorrow()})
    assert b"buses found" in res.data


def test_search_rejects_past_date(client):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    res = client.get("/", query_string={"origin": "Kuala Lumpur", "destination": "Penang", "date": yesterday})
    assert b"cannot be in the past" in res.data


def test_search_rejects_same_origin_and_destination(client):
    res = client.get("/", query_string={"origin": "Ipoh", "destination": "ipoh", "date": tomorrow()})
    assert b"must be different" in res.data
