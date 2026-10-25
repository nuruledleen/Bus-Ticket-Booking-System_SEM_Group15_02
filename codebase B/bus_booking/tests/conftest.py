from datetime import date, timedelta

import pytest

import seed
from app import create_app
from database import connect, init_db
from repositories import schedule_repo


def tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    conn = connect(app.config["DATABASE"])
    init_db(conn)
    seed.seed(conn, app.config)
    conn.close()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def conn(app):
    connection = connect(app.config["DATABASE"])
    yield connection
    connection.close()


@pytest.fixture
def schedule(conn):
    """Tomorrow's 22:00 Kuala Lumpur -> Penang bus (no pre-booked seats)."""
    return schedule_repo.search(conn, "Kuala Lumpur", "Penang", tomorrow(), "2000-01-01 00:00")[-1]


@pytest.fixture
def make_payload():
    def build(schedule_id, seats=(5,)):
        return {
            "schedule_id": schedule_id,
            "contact": {"email": "ali@example.com", "phone": "012-345 6789"},
            "passengers": [
                {"seat_number": s, "name": "Ali Ahmad", "age": 30, "gender": "M"} for s in seats
            ],
        }
    return build
