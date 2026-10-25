from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from services.errors import AppError


def _respond(status, code, message, details=None):
    if "/api/" in request.path:
        return jsonify(error={"code": code, "message": message, "details": details or {}}), status
    return render_template("error.html", status=status, message=message), status


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(err):
        return _respond(err.status, err.code, err.message, err.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return _respond(err.code, err.name.lower().replace(" ", "_"), err.description)
