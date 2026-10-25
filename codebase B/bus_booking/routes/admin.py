"""Admin pages and API (HTTP Basic auth). Credentials come from config / env vars."""
from flask import Blueprint, jsonify, render_template

from database import get_db
from routes.helpers import admin_required, json_body
from services import schedule_service

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@admin_required
def dashboard():
    schedules = schedule_service.list_upcoming_schedules(get_db())
    return render_template("admin.html", schedules=schedules)


@bp.post("/api/schedules")
@admin_required
def create_schedule():
    return jsonify(schedule=schedule_service.create_schedule(get_db(), json_body())), 201


@bp.put("/api/schedules/<int:schedule_id>")
@admin_required
def update_schedule(schedule_id):
    return jsonify(schedule=schedule_service.update_schedule(get_db(), schedule_id, json_body()))
