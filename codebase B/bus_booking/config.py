import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    DATABASE = os.environ.get("BUS_DB", str(BASE_DIR / "bus_booking.db"))
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    MAX_SEATS_PER_BOOKING = 6
    SERVICE_FEE_SEN = 100            # per seat, in sen (RM 1.00)
    CANCELLATION_CUTOFF_HOURS = 2    # cancel up to N hours before departure
