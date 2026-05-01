"""
Bootstrap tests — verify the app skeleton is wired correctly.
These must pass before any feature work begins.
"""
import sqlite3

EXPECTED_TABLES = {
    "digests", "digest_actions", "processed_emails", "emails",
    "meetings", "captures", "projects", "project_contacts", "project_actions",
    "contacts", "notes", "tags", "note_tags", "attachments",
    "weekly_summaries", "test_runs",
}

EXPECTED_ROUTES = {
    "/", "/digest/save", "/digest/run-siiri", "/digest/feed-siiri",
    "/digest/action/<int:action_id>/toggle",
    "/digest/action/<int:action_id>/note",
    "/digest/action/<int:action_id>/reply",
    "/meetings/add", "/meetings/<int:meeting_id>/dismiss",
    "/meetings/delete/<int:meeting_id>", "/meetings/urgent-items",
    "/captures/add", "/captures/<int:capture_id>/done",
    "/captures/<int:capture_id>/promote",
    "/projects/", "/projects/add",
    "/contacts/", "/contacts/add",
    "/admin/tests",
}


def test_app_boots(app):
    assert app is not None
    assert app.config["TESTING"] is True


def test_db_path_is_isolated(app, tmp_path):
    assert "test.db" in app.config["DB_PATH"]
    assert str(tmp_path) in app.config["DB_PATH"]


def test_all_tables_created(app):
    conn = sqlite3.connect(app.config["DB_PATH"])
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert EXPECTED_TABLES.issubset(tables), f"Missing tables: {EXPECTED_TABLES - tables}"


def test_all_routes_registered(app):
    registered = {str(r) for r in app.url_map.iter_rules()}
    missing = EXPECTED_ROUTES - registered
    assert not missing, f"Missing routes: {missing}"


def test_dashboard_returns_200(client):
    r = client.get("/")
    assert r.status_code == 200


def test_dashboard_empty_state(client):
    r = client.get("/")
    assert r.status_code == 200
