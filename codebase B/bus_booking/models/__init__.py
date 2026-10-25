"""Structured, validated input data passed from validation to services."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Contact:
    email: str
    phone: str


@dataclass(frozen=True)
class Passenger:
    seat_number: int
    name: str
    age: int
    gender: str


@dataclass(frozen=True)
class BookingRequest:
    schedule_id: int
    contact: Contact
    passengers: tuple
