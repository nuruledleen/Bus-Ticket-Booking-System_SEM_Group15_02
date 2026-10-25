"""Run with:  python -m unittest -v test_app   (uses a throw-away database)"""
import os, tempfile, unittest, sqlite3
from datetime import date, timedelta
os.environ["BUS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["ADMIN_PASSWORD"] = "testpw"
import app as m

def valid_form(*seats, email="ann@example.com"):
    d = {"seats": list(seats), "email": email, "phone": "012-3456789", "payment_method": "card"}
    d.update({f"name_{s}": "Ann Tan" for s in seats})
    return d

class BusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m.init_db(reset=True)
    def setUp(self):
        self.c = m.app.test_client()
        db = sqlite3.connect(m.app.config["DATABASE"]); db.row_factory = sqlite3.Row
        self.day = (date.today() + timedelta(days=3)).isoformat()   # >24h away: full refund
        self.sid = db.execute("SELECT id FROM schedules WHERE origin='Kuala Lumpur' AND destination='Ipoh' AND travel_date=? "
                              "ORDER BY departure_time", (self.day,)).fetchone()["id"]
        db.close()
    def booked(self, seat):
        db = sqlite3.connect(m.app.config["DATABASE"])
        n = db.execute("SELECT COUNT(*) FROM tickets WHERE schedule_id=? AND seat_no=? AND status='booked'", (self.sid, seat)).fetchone()[0]
        db.close(); return n

    def test_search_shows_times_and_fares(self):
        r = self.c.get(f"/?origin=Kuala+Lumpur&destination=Ipoh&travel_date={self.day}")
        self.assertIn(b"09:00", r.data); self.assertIn(b"RM 25.00", r.data)
    def test_search_validation(self):
        self.assertIn(b"must differ", self.c.get(f"/?origin=Ipoh&destination=ipoh&travel_date={self.day}").data)
    def test_seat_map_shows_taken_seats(self):
        sid = m.get_db  # demo booking has 1A/1B taken on KL->Penang 08:00 tomorrow
        with m.app.app_context():
            s = m.get_db().execute("SELECT id FROM schedules WHERE origin='Kuala Lumpur' AND destination='Penang' AND "
                                   "departure_time='08:00' AND travel_date=?", ((date.today() + timedelta(days=1)).isoformat(),)).fetchone()
        self.assertIn(b"seat taken", self.c.get(f"/schedule/{s['id']}").data)
    def test_booking_fare_and_view(self):
        r = self.c.post(f"/schedule/{self.sid}/book", data=valid_form("5A", "5B"))
        self.assertEqual(r.status_code, 302)
        page = self.c.get(r.headers["Location"]).data
        self.assertIn(b"RM 52.00", page)          # 2 x (25 + 1)
    def test_duplicate_seat_rejected(self):
        self.assertEqual(self.c.post(f"/schedule/{self.sid}/book", data=valid_form("6A")).status_code, 302)
        r = m.app.test_client().post(f"/schedule/{self.sid}/book", data=valid_form("6A", email="bob@example.com"))
        self.assertEqual(r.status_code, 409); self.assertEqual(self.booked("6A"), 1)
    def test_validation_errors(self):
        bad = valid_form("7A", email="not-an-email"); bad["phone"] = "123"
        r = self.c.post(f"/schedule/{self.sid}/book", data=bad)
        self.assertEqual(r.status_code, 400); self.assertEqual(self.booked("7A"), 0)
    def test_max_seats(self):
        self.assertEqual(self.c.post(f"/schedule/{self.sid}/book", data=valid_form("8A", "8B", "8C", "8D", "9A")).status_code, 400)
    def test_cancel_refunds_and_frees_seat(self):
        loc = self.c.post(f"/schedule/{self.sid}/book", data=valid_form("10A")).headers["Location"]
        r = self.c.post(loc + "/cancel", follow_redirects=True)
        self.assertIn(b"Refund of RM 25.00", r.data); self.assertEqual(self.booked("10A"), 0)
        self.assertEqual(self.c.post(f"/schedule/{self.sid}/book", data=valid_form("10A")).status_code, 302)  # rebookable
    def test_cannot_view_others_booking(self):
        self.assertEqual(self.c.get("/booking/BKDEMO01").status_code, 302)
        self.c.post("/lookup", data={"reference": "BKDEMO01", "email": "demo@example.com"})
        self.assertEqual(self.c.get("/booking/BKDEMO01").status_code, 200)
    def test_admin_add_and_update(self):
        self.assertEqual(self.c.post("/admin/save", data={}).status_code, 302)   # not logged in
        self.c.post("/admin/login", data={"password": "testpw"})
        row = {"operator": "Test Bus", "origin": "Alor Setar", "destination": "Kuala Lumpur", "travel_date": self.day,
               "departure_time": "11:00", "arrival_time": "16:00", "fare": "40", "total_seats": "40", "status": "active"}
        self.c.post("/admin/save", data=row)
        self.assertIn(b"Alor Setar", self.c.get("/admin").data)
        with m.app.app_context():
            sid = m.get_db().execute("SELECT id FROM schedules WHERE origin='Alor Setar'").fetchone()["id"]
        self.c.post("/admin/save", data={**row, "id": sid, "fare": "55"})
        self.assertIn(b"RM 55.00", self.c.get("/admin").data)
        self.assertIn(b"Invalid", self.c.post("/admin/save", data={**row, "travel_date": "x"}, follow_redirects=True).data)

if __name__ == "__main__":
    unittest.main()
