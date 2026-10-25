DROP TABLE IF EXISTS booking_seats;
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS schedules;

CREATE TABLE schedules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    operator       TEXT    NOT NULL,
    bus_type       TEXT    NOT NULL,
    origin         TEXT    NOT NULL,
    destination    TEXT    NOT NULL,
    departure_time TEXT    NOT NULL,              -- 'YYYY-MM-DD HH:MM' (local time)
    arrival_time   TEXT    NOT NULL,
    fare_sen       INTEGER NOT NULL CHECK (fare_sen > 0),
    total_seats    INTEGER NOT NULL CHECK (total_seats BETWEEN 1 AND 60),
    status         TEXT    NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CANCELLED')),
    CHECK (origin <> destination),
    CHECK (arrival_time > departure_time)
);
CREATE INDEX idx_schedules_route ON schedules (origin, destination, departure_time);

CREATE TABLE bookings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    reference      TEXT    NOT NULL UNIQUE,
    schedule_id    INTEGER NOT NULL REFERENCES schedules (id),
    contact_email  TEXT    NOT NULL,
    contact_phone  TEXT    NOT NULL,
    total_fare_sen INTEGER NOT NULL CHECK (total_fare_sen >= 0),
    status         TEXT    NOT NULL DEFAULT 'CONFIRMED' CHECK (status IN ('CONFIRMED', 'CANCELLED')),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    cancelled_at   TEXT
);

CREATE TABLE booking_seats (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id       INTEGER NOT NULL REFERENCES bookings (id),
    schedule_id      INTEGER NOT NULL REFERENCES schedules (id),
    seat_number      INTEGER NOT NULL CHECK (seat_number >= 1),
    passenger_name   TEXT    NOT NULL,
    passenger_age    INTEGER NOT NULL,
    passenger_gender TEXT    NOT NULL CHECK (passenger_gender IN ('M', 'F')),
    is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);
-- The core guarantee: one ACTIVE booking per seat per schedule.
-- Cancelled seats (is_active = 0) are excluded, so they can be re-booked.
CREATE UNIQUE INDEX uq_active_seat ON booking_seats (schedule_id, seat_number) WHERE is_active = 1;
