from functools import wraps
from hmac import compare_digest

from flask import Response, current_app, request

from services.errors import ValidationError


def json_body():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")
    return payload


def _matches(supplied, expected):
    return compare_digest((supplied or "").encode(), expected.encode())


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth, config = request.authorization, current_app.config
        if not auth or not (_matches(auth.username, config["ADMIN_USERNAME"])
                            and _matches(auth.password, config["ADMIN_PASSWORD"])):
            return Response("Admin login required.", 401, {"WWW-Authenticate": 'Basic realm="Admin"'})
        return view(*args, **kwargs)
    return wrapped
