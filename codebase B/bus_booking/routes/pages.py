"""HTML pages. Thin: parse the request, call a service, render a template."""
from datetime import date, datetime

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from database import get_db
from services import booking_service, schedule_service
from services.errors import ValidationError

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    conn = get_db()
    context = {
        "cities": schedule_service.list_cities(conn),
        "form": {key: request.args.get(key, "") for key in ("origin", "destination", "date")},
        "today": date.today().isoformat(),
        "results": None,
        "errors": {},
    }
    if request.args:
        try:
            _, context["results"] = schedule_service.search_schedules(conn, request.args, datetime.now())
        except ValidationError as err:
            context["errors"] = err.details
    return render_template("index.html", **context)


@bp.get("/schedules/<int:schedule_id>/seats")
def seats(schedule_id):
    schedule = schedule_service.get_schedule(get_db(), schedule_id)
    return render_template("seats.html", s=schedule, max_seats=current_app.config["MAX_SEATS_PER_BOOKING"])


@bp.get("/bookings")
def lookup():
    reference = request.args.get("reference", "").strip()
    if reference:
        return redirect(url_for("pages.booking_detail", reference=reference.upper()))
    return render_template("lookup.html")


@bp.get("/bookings/<reference>")
def booking_detail(reference):
    booking = booking_service.get_booking_view(get_db(), reference, current_app.config)
    return render_template("booking.html", b=booking)
