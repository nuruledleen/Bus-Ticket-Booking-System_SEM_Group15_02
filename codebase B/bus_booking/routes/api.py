"""JSON API used by the seat-selection and booking-management pages."""
from flask import Blueprint, current_app, jsonify, request

from database import get_db
from routes.helpers import json_body
from services import booking_service, schedule_service

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/schedules/<int:schedule_id>/seats")
def seat_map(schedule_id):
    return jsonify(schedule_service.seat_map(get_db(), schedule_id))


@bp.get("/schedules/<int:schedule_id>/quote")
def quote(schedule_id):
    result = schedule_service.quote(get_db(), schedule_id, request.args.get("seat_count"), current_app.config)
    return jsonify(result)


@bp.post("/bookings")
def create_booking():
    booking = booking_service.create_booking(get_db(), json_body(), current_app.config)
    return jsonify(booking=booking), 201


@bp.get("/bookings/<reference>")
def get_booking(reference):
    return jsonify(booking=booking_service.get_booking_view(get_db(), reference, current_app.config))


@bp.post("/bookings/<reference>/cancel")
def cancel_booking(reference):
    return jsonify(booking=booking_service.cancel_booking(get_db(), reference, current_app.config))
