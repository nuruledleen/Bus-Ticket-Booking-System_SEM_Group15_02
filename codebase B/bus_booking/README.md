# BusBook MY (Flask + SQLite)

    python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    flask --app app init-db        # creates tables (drops existing data)
    flask --app app seed-db        # sample schedules + one sample booking
    flask --app app run --debug    # http://127.0.0.1:5000
    pytest                         # automated tests

Admin: http://127.0.0.1:5000/admin/ (default admin / admin123; override with ADMIN_USERNAME, ADMIN_PASSWORD, BUS_DB env vars).
