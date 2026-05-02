"""Tests for the Notes feature (F4) and Siiri workspace context."""
import io
import json
import pytest
from .conftest import seed_project, seed_meeting


# ── Helpers ────────────────────────────────────────────────────────────────────

def seed_note(conn, *, title=None, content="Test note", tags=None):
    nid = conn.execute(
        "INSERT INTO notes (title, content) VALUES (?,?)", [title, content]
    ).lastrowid
    conn.commit()
    if tags:
        for name in tags:
            conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", [name])
            tid = conn.execute("SELECT id FROM tags WHERE name=?", [name]).fetchone()["id"]
            conn.execute("INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?,?)", [nid, tid])
        conn.commit()
    return nid


# ── Index ──────────────────────────────────────────────────────────────────────

def test_notes_index_loads(client):
    assert client.get("/notes/").status_code == 200


def test_notes_index_shows_note(client, db):
    seed_note(db, content="My important note")
    r = client.get("/notes/")
    assert b"My important note" in r.data


def test_notes_index_tag_filter(client, db):
    seed_note(db, content="Tagged note",   tags=["project"])
    seed_note(db, content="Untagged note")
    r = client.get("/notes/?tag=project")
    assert b"Tagged note"   in r.data
    assert b"Untagged note" not in r.data


# ── Add ────────────────────────────────────────────────────────────────────────

def test_add_note(client, db):
    r = client.post("/notes/add", data=json.dumps({"content": "Hello world"}),
                    content_type="application/json")
    assert r.get_json()["ok"] is True
    assert db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 1


def test_add_note_with_title_and_tags(client, db):
    r = client.post("/notes/add", data=json.dumps({
        "title": "My note", "content": "Body", "tags": ["work", "urgent"]
    }), content_type="application/json")
    data = r.get_json()
    assert data["ok"] is True
    tags = [row[0] for row in db.execute(
        "SELECT t.name FROM tags t JOIN note_tags nt ON t.id=nt.tag_id WHERE nt.note_id=?",
        [data["id"]]
    ).fetchall()]
    assert set(tags) == {"work", "urgent"}


def test_add_note_requires_content(client):
    r = client.post("/notes/add", data=json.dumps({"title": "No body"}),
                    content_type="application/json")
    assert r.get_json()["ok"] is False


# ── Update ─────────────────────────────────────────────────────────────────────

def test_update_note(client, db):
    nid = seed_note(db, content="Old content")
    r = client.post(f"/notes/{nid}/update",
                    data=json.dumps({"content": "New content", "tags": ["updated"]}),
                    content_type="application/json")
    assert r.get_json()["ok"] is True
    row = db.execute("SELECT content FROM notes WHERE id=?", [nid]).fetchone()
    assert row["content"] == "New content"


def test_update_note_replaces_tags(client, db):
    nid = seed_note(db, content="Note", tags=["old"])
    client.post(f"/notes/{nid}/update",
                data=json.dumps({"content": "Note", "tags": ["new"]}),
                content_type="application/json")
    tags = [r[0] for r in db.execute(
        "SELECT t.name FROM tags t JOIN note_tags nt ON t.id=nt.tag_id WHERE nt.note_id=?", [nid]
    ).fetchall()]
    assert tags == ["new"]


# ── Delete ─────────────────────────────────────────────────────────────────────

def test_delete_note(client, db):
    nid = seed_note(db, content="To delete")
    r = client.post(f"/notes/{nid}/delete")
    assert r.get_json()["ok"] is True
    assert db.execute("SELECT COUNT(*) FROM notes WHERE id=?", [nid]).fetchone()[0] == 0


# ── File attachments ───────────────────────────────────────────────────────────

def test_attach_file(client, db):
    nid = seed_note(db)
    data = {"file": (io.BytesIO(b"hello pdf"), "doc.pdf")}
    r = client.post(f"/notes/{nid}/attach", data=data, content_type="multipart/form-data")
    resp = r.get_json()
    assert resp["ok"] is True
    assert resp["filename"] == "doc.pdf"
    assert db.execute("SELECT COUNT(*) FROM attachments WHERE note_id=?", [nid]).fetchone()[0] == 1


def test_attach_disallows_exe(client, db):
    nid = seed_note(db)
    data = {"file": (io.BytesIO(b"evil"), "virus.exe")}
    r = client.post(f"/notes/{nid}/attach", data=data, content_type="multipart/form-data")
    assert r.get_json()["ok"] is False


def test_delete_attachment(client, db):
    nid = seed_note(db)
    data = {"file": (io.BytesIO(b"data"), "report.pdf")}
    resp = client.post(f"/notes/{nid}/attach", data=data, content_type="multipart/form-data").get_json()
    aid  = resp["id"]
    r    = client.post(f"/notes/{nid}/attach/{aid}/delete")
    assert r.get_json()["ok"] is True
    assert db.execute("SELECT COUNT(*) FROM attachments WHERE id=?", [aid]).fetchone()[0] == 0


# ── Siiri workspace context ────────────────────────────────────────────────────

def test_workspace_context_empty(db):
    from app.services.siiri import _workspace_context
    assert _workspace_context(db, "2099-01-01") is None


def test_workspace_context_includes_note(db):
    from app.services.siiri import _workspace_context
    seed_note(db, title="Key thing", content="Remember the deadline")
    ctx = _workspace_context(db, "2099-01-01")
    assert ctx is not None
    assert "Remember the deadline" in ctx


def test_workspace_context_includes_meeting(db):
    from app.services.siiri import _workspace_context
    seed_meeting(db, title="Board meeting", date="2099-02-01")
    ctx = _workspace_context(db, "2099-01-01")
    assert "Board meeting" in ctx


def test_workspace_context_includes_project(db):
    from app.services.siiri import _workspace_context
    seed_project(db, name="Showroom build", deadline="2099-03-01")
    ctx = _workspace_context(db, "2099-01-01")
    assert "Showroom build" in ctx


def test_workspace_context_excludes_past_meeting(db):
    from app.services.siiri import _workspace_context
    seed_meeting(db, title="Old meeting", date="2000-01-01")
    ctx = _workspace_context(db, "2099-01-01")
    assert ctx is None or "Old meeting" not in ctx
