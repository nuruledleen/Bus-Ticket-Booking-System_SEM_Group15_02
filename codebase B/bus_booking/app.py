"""Application factory, blueprint registration and CLI commands."""
import click
from flask import Flask

import seed
from config import Config
from database import close_db, connect, init_db
from routes import admin, api, pages
from routes.errors import register_error_handlers


def format_rm(sen):
    return f"RM {sen / 100:,.2f}"


def register_cli(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Create the database tables (drops any existing data)."""
        conn = connect(app.config["DATABASE"])
        init_db(conn)
        conn.close()
        click.echo("Database initialised.")

    @app.cli.command("seed-db")
    def seed_db_command():
        """Load sample schedules and one sample booking."""
        conn = connect(app.config["DATABASE"])
        seed.seed(conn, app.config)
        conn.close()
        click.echo("Sample data loaded.")


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    app.teardown_appcontext(close_db)
    app.jinja_env.filters["rm"] = format_rm
    for blueprint in (pages.bp, api.bp, admin.bp):
        app.register_blueprint(blueprint)
    register_error_handlers(app)
    register_cli(app)
    return app


if __name__ == "__main__":
    create_app().run(debug=True)
