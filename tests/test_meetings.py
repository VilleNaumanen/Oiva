"""Tests for the Meeting Management feature (F4)."""
import json
from .conftest import seed_digest, seed_action, seed_meeting


def test_add_meeting(client, db):
    payload = {"title": "Sprint Review", "date": "2099-05-15", "location": "Lappeenranta"}
    r = client.post("/meetings/add", data=json.dumps(payload), content_type="application/json")
    assert r.get_json()["ok"] is True
    row = db.execute("SELECT * FROM meetings WHERE title='Sprint Review'").fetchone()
    assert row is not None
    assert row["location"] == "Lappeenranta"


def test_add_meeting_requires_title_and_date(client):
    r = client.post("/meetings/add", data=json.dumps({"title": "No date"}),
                    content_type="application/json")
    assert r.get_json()["ok"] is False


def test_dismiss_marks_done(client, db):
    mid = seed_meeting(db, done=0)
    client.post(f"/meetings/{mid}/dismiss")
    assert db.execute("SELECT done FROM meetings WHERE id=?", [mid]).fetchone()["done"] == 1


def test_delete_removes_meeting(client, db):
    mid = seed_meeting(db)
    client.post(f"/meetings/delete/{mid}")
    assert db.execute("SELECT COUNT(*) FROM meetings WHERE id=?", [mid]).fetchone()[0] == 0


def test_urgent_items_empty(client):
    assert client.get("/meetings/urgent-items").get_json() == []


def test_urgent_items_includes_future_meeting(client, db):
    seed_meeting(db, title="Big Meeting", date="2099-06-01")
    items = client.get("/meetings/urgent-items").get_json()
    assert any(i["title"] == "Big Meeting" for i in items)


def test_urgent_items_includes_future_deadline(client, db):
    did = seed_digest(db)
    seed_action(db, did, summary="Deadline task", deadline="2099-01-01")
    items = client.get("/meetings/urgent-items").get_json()
    assert any(i["title"] == "Deadline task" for i in items)


def test_urgent_items_excludes_done_action(client, db):
    did = seed_digest(db)
    seed_action(db, did, summary="Done task", deadline="2099-01-01", done=1)
    items = client.get("/meetings/urgent-items").get_json()
    assert not any(i["title"] == "Done task" for i in items)


def test_urgent_items_excludes_dismissed_meeting(client, db):
    mid = seed_meeting(db, title="Old meeting", date="2099-06-01", done=1)
    items = client.get("/meetings/urgent-items").get_json()
    assert not any(i["title"] == "Old meeting" for i in items)


def test_urgent_items_capped_at_five(client, db):
    did = seed_digest(db)
    for i in range(8):
        seed_action(db, did, summary=f"Task {i}", deadline=f"2099-{i+1:02d}-01")
    assert len(client.get("/meetings/urgent-items").get_json()) <= 5


# ── Meetings index ─────────────────────────────────────────────────────────────

def test_meetings_index_loads(client):
    r = client.get("/meetings/")
    assert r.status_code == 200


# ── Calendar import ────────────────────────────────────────────────────────────

def test_import_calendar_empty_folder(client):
    r = client.post("/meetings/import-calendar")
    data = r.get_json()
    assert data["ok"] is True
    assert data["imported"] == 0


def test_import_calendar_creates_meeting(client, app, db, tmp_path):
    import json
    cal_dir = tmp_path / "cal_import"
    cal_dir.mkdir()
    app.config["CALENDAR"] = str(cal_dir)
    (cal_dir / "2099-05-01_meeting.json").write_text(json.dumps({
        "title": "PA Meeting", "date": "2099-05-01",
        "time_start": "10:00", "time_end": "11:00",
        "location": "Teams", "organizer": "boss@kempower.com",
        "source": "kempower",
    }))
    r = client.post("/meetings/import-calendar")
    assert r.get_json() == {"ok": True, "imported": 1}
    row = db.execute("SELECT * FROM meetings WHERE title='PA Meeting'").fetchone()
    assert row is not None
    assert row["location"] == "Teams"


def test_import_calendar_skips_duplicate(client, app, db, tmp_path):
    import json
    cal_dir = tmp_path / "cal_dup"
    cal_dir.mkdir()
    app.config["CALENDAR"] = str(cal_dir)
    payload = json.dumps({"title": "Dup Meeting", "date": "2099-06-01", "source": "kempower"})
    (cal_dir / "dup.json").write_text(payload)
    client.post("/meetings/import-calendar")
    # re-create file after archive
    (cal_dir / "dup2.json").write_text(payload)
    client.post("/meetings/import-calendar")
    count = db.execute("SELECT COUNT(*) FROM meetings WHERE title='Dup Meeting'").fetchone()[0]
    assert count == 1


# ── Snooze urgent (projects) ───────────────────────────────────────────────────

def test_snooze_urgent_noop(client, db):
    from .conftest import seed_project
    pid = seed_project(db, name="Snooze Me", deadline="2099-12-01")
    r = client.post(f"/projects/{pid}/snooze-urgent")
    assert r.get_json()["ok"] is True
    row = db.execute("SELECT * FROM projects WHERE id=?", [pid]).fetchone()
    assert row["status"] == "active"
