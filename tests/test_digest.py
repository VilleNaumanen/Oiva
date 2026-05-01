"""Tests for the Email Digest feature (F1)."""
import json
from .conftest import seed_digest, seed_action


# ── Save endpoint ──────────────────────────────────────────────────────────────

def test_save_split_format(client, db):
    payload = {
        "action_required": [{"summary": "Review doc", "deadline": "2026-05-10",
                              "email_from": "a@b.com", "email_subject": "Sub"}],
        "worth_knowing":   [{"summary": "FYI item"}],
        "noise_count": 3,
    }
    r = client.post("/digest/save", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    assert db.execute("SELECT COUNT(*) FROM digests").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM digest_actions").fetchone()[0] == 2
    assert db.execute("SELECT noise_count FROM digests").fetchone()[0] == 3


def test_save_flat_format(client, db):
    payload = {
        "actions": [
            {"category": "action", "summary": "Flat action"},
            {"category": "info",   "summary": "Flat info"},
        ],
        "noise_count": 0,
    }
    r = client.post("/digest/save", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    rows = db.execute("SELECT category, summary FROM digest_actions ORDER BY id").fetchall()
    assert len(rows) == 2
    assert {r["category"] for r in rows} == {"action", "info"}


def test_save_split_wins_over_flat(client, db):
    payload = {
        "action_required": [{"summary": "Split action"}],
        "worth_knowing": [],
        "actions": [{"category": "action", "summary": "Should be ignored"}],
        "noise_count": 0,
    }
    client.post("/digest/save", data=json.dumps(payload), content_type="application/json")
    assert db.execute("SELECT COUNT(*) FROM digest_actions").fetchone()[0] == 1


def test_save_returns_digest_id(client):
    payload = {"action_required": [{"summary": "X"}], "worth_knowing": [], "noise_count": 0}
    data = client.post("/digest/save", data=json.dumps(payload),
                       content_type="application/json").get_json()
    assert "digest_id" in data
    assert isinstance(data["digest_id"], int)


# ── Action toggle ──────────────────────────────────────────────────────────────

def test_toggle_marks_done(client, db):
    did = seed_digest(db)
    aid = seed_action(db, did, done=0)
    client.post(f"/digest/action/{aid}/toggle")
    assert db.execute("SELECT done FROM digest_actions WHERE id=?", [aid]).fetchone()["done"] == 1


def test_toggle_marks_undone(client, db):
    did = seed_digest(db)
    aid = seed_action(db, did, done=1)
    client.post(f"/digest/action/{aid}/toggle")
    assert db.execute("SELECT done FROM digest_actions WHERE id=?", [aid]).fetchone()["done"] == 0


# ── Action note ────────────────────────────────────────────────────────────────

def test_note_saved(client, db):
    did = seed_digest(db)
    aid = seed_action(db, did)
    client.post(f"/digest/action/{aid}/note",
                data=json.dumps({"note": "Follow up Thursday"}),
                content_type="application/json")
    assert db.execute("SELECT note FROM digest_actions WHERE id=?", [aid]).fetchone()["note"] \
           == "Follow up Thursday"


def test_note_cleared(client, db):
    did = seed_digest(db)
    aid = seed_action(db, did, note="Old note")
    client.post(f"/digest/action/{aid}/note",
                data=json.dumps({"note": ""}), content_type="application/json")
    assert db.execute("SELECT note FROM digest_actions WHERE id=?", [aid]).fetchone()["note"] == ""


# ── Manual reply mark ──────────────────────────────────────────────────────────

def test_mark_replied(client, db):
    did = seed_digest(db)
    aid = seed_action(db, did, replied=0)
    r = client.post(f"/digest/action/{aid}/reply")
    assert r.get_json()["ok"] is True
    assert db.execute("SELECT replied FROM digest_actions WHERE id=?", [aid]).fetchone()["replied"] == 1


# ── Carry-over ─────────────────────────────────────────────────────────────────

def test_carryover_undone_from_older_digest(client, db):
    old_did = seed_digest(db, "2026-04-28")
    seed_action(db, old_did, summary="Old undone action", done=0)
    new_did = seed_digest(db, "2026-04-30")
    seed_action(db, new_did, summary="Current action")
    r = client.get("/")
    assert b"Old undone action" in r.data
    assert b"Current action" in r.data


def test_done_old_actions_not_carried_over(client, db):
    old_did = seed_digest(db, "2026-04-28")
    seed_action(db, old_did, summary="Completed old action", done=1)
    new_did = seed_digest(db, "2026-04-30")
    seed_action(db, new_did, summary="Current action")
    r = client.get("/")
    assert b"Completed old action" not in r.data


# ── Feed Siiri ─────────────────────────────────────────────────────────────────

def test_feed_siiri_no_digest(client):
    assert client.post("/digest/feed-siiri").get_json()["ok"] is False


def test_feed_siiri_no_siiri_notes(client, db):
    did = seed_digest(db)
    seed_action(db, did, note="Personal note")
    assert client.post("/digest/feed-siiri").get_json()["ok"] is False


def test_feed_siiri_saves_to_prefs(client, db, app, tmp_path):
    did = seed_digest(db)
    seed_action(db, did, note="Siiri, prioritize LUT emails")
    data = client.post("/digest/feed-siiri").get_json()
    assert data["ok"] is True
    assert data["count"] == 1
    prefs = tmp_path / "prefs.md"
    assert prefs.exists()
    assert "Siiri, prioritize LUT emails" in prefs.read_text(encoding="utf-8")
