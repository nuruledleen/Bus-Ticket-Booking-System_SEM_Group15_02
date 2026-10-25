"""Unit tests for the extracted pure modules: no Flask app, no database."""
import unittest
from werkzeug.datastructures import MultiDict
from fare import calc_fare, refund_for
from seating import seat_labels
from validation import validate_booking

def form(**kw):
    d = MultiDict([("seats", s) for s in kw.pop("seats", ["1A"])])
    d.update({"name_1A": "Ann Tan", "email": "a@b.com", "phone": "0123456789", "payment_method": "card", **kw})
    return d

class FareTests(unittest.TestCase):
    def test_total(self): self.assertEqual(calc_fare(25, 2), (50.0, 2.0, 52.0))
    def test_refund_full(self): self.assertEqual(refund_for(48, 25)[:2], (True, 25.0))
    def test_refund_half(self): self.assertEqual(refund_for(10, 25)[:2], (True, 12.5))
    def test_refund_boundaries(self):
        self.assertTrue(refund_for(2, 25)[0]); self.assertFalse(refund_for(1.99, 25)[0]); self.assertEqual(refund_for(24, 25)[1], 25.0)

class ValidationTests(unittest.TestCase):
    def test_valid(self): self.assertEqual(validate_booking(form(), 40)[1], [])
    def test_bad_phone(self): self.assertTrue(validate_booking(form(phone="123"), 40)[1])
    def test_bad_email(self): self.assertTrue(validate_booking(form(email="x"), 40)[1])
    def test_bad_name(self): self.assertTrue(validate_booking(form(name_1A="R2D2"), 40)[1])
    def test_seat_not_on_bus(self): self.assertTrue(validate_booking(form(seats=["99Z"]), 40)[1])
    def test_too_many_seats(self): self.assertTrue(validate_booking(form(seats=["1A", "1B", "1C", "1D", "2A"]), 40)[1])
    def test_layout(self): self.assertEqual(seat_labels(5), ["1A", "1B", "1C", "1D", "2A"])

if __name__ == "__main__":
    unittest.main()
