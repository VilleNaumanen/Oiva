"""Tests for the Quick Capture feature (F5)."""
import json
from .conftest import seed_digest, seed_capture


def test_add_capture(client, db):
    r = client.post("/captures/add", data=json.dumps({"text": "Remember to call Sanna"}),
                    content_type="application/json")
    data = r.get_json()
    assert data["ok"] is True
    assert data["capture"]["text"] == "Remember to call Sanna"
    assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 1


def test_add_empty_capture_fails(client):
    r = client.post("/captures/add", data=json.dumps({"text": "  "}),
                    content_type="application/json")
    assert r.get_json()["ok"] is False


def test_mark_capture_done(client, db):
    cid = seed_capture(db, text="Quick thought", done=0)
    client.post(f"/captures/{cid}/done")
    assert db.execute("SELECT done FROM captures WHERE id=?", [cid]).fetchone()["done"] == 1


def test_promote_creates_action(client, db):
    did = seed_digest(db)
    cid = seed_capture(db, text="Follow up with Petri")
    r = client.post(f"/captures/{cid}/promote")
    data = r.get_json()
    assert data["ok"] is True
    assert "action_id" in data
    action = db.execute("SELECT summary FROM digest_actions WHERE id=?",
                        [data["action_id"]]).fetchone()
    assert action["summary"] == "Follow up with Petri"


def test_promote_marks_capture_done(client, db):
    seed_digest(db)
    cid = seed_capture(db, text="Task to promote")
    client.post(f"/captures/{cid}/promote")
    row = db.execute("SELECT done, promoted_to_action_id FROM captures WHERE id=?",
                     [cid]).fetchone()
    assert row["done"] == 1
    assert row["promoted_to_action_id"] is not None


def test_promote_nonexistent_capture(client, db):
    r = client.post("/captures/99999/promote")
    assert r.get_json()["ok"] is False


def test_dashboard_shows_captures(client, db):
    seed_capture(db, text="Visible on dashboard")
    r = client.get("/")
    assert b"Visible on dashboard" in r.data


def test_done_captures_not_on_dashboard(client, db):
    seed_capture(db, text="Hidden capture", done=1)
    r = client.get("/")
    assert b"Hidden capture" not in r.data
