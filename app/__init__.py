import os
from flask import Flask
from config import config


def create_app(config_name: str = "default", test_config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config[config_name])
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.config["UPLOADS"], exist_ok=True)

    from .database import init_db
    with app.app_context():
        init_db()

    _register_filters(app)
    _register_blueprints(app)

    return app


def _register_filters(app: Flask) -> None:
    import re
    from datetime import date
    from markupsafe import escape, Markup

    @app.template_filter("bold_md")
    def bold_md(text):
        if not text:
            return ""
        return Markup(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(escape(text))))

    @app.template_filter("fmtdate")
    def fmtdate(s):
        try:
            return date.fromisoformat(str(s)).strftime("%d %b")
        except Exception:
            return s or ""


def _register_blueprints(app: Flask) -> None:
    from .routes.dashboard import bp as dashboard_bp
    from .routes.digest import bp as digest_bp
    from .routes.meetings import bp as meetings_bp
    from .routes.captures import bp as captures_bp
    from .routes.projects import bp as projects_bp
    from .routes.contacts import bp as contacts_bp
    from .routes.notes import bp as notes_bp
    from .routes.replies import bp as replies_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(digest_bp,   url_prefix="/digest")
    app.register_blueprint(meetings_bp, url_prefix="/meetings")
    app.register_blueprint(captures_bp, url_prefix="/captures")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(contacts_bp, url_prefix="/contacts")
    app.register_blueprint(notes_bp,    url_prefix="/notes")
    app.register_blueprint(replies_bp,  url_prefix="/replies")
    app.register_blueprint(admin_bp,    url_prefix="/admin")
