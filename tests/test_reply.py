"""Tests for F2: Reply tracking service and routes."""
import sqlite3
import pytest
from .conftest import seed_digest, seed_action, seed_sent_email


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_action_with_subject(conn, subject: str, replied: int = 0) -> int:
    did = seed_digest(conn)
    return seed_action(conn, did, email_subject=subject, replied=replied)


# ── normalize_thread_key ───────────────────────────────────────────────────────

def test_normalize_thread_key_strips_re():
    from app.services.reply import normalize_thread_key
    assert normalize_thread_key("Re: Project update") == "project update"


def test_normalize_thread_key_strips_fwd():
    from app.services.reply import normalize_thread_key
    assert normalize_thread_key("FWD: Project update") == "project update"
    assert normalize_thread_key("Fwd: Project update") == "project update"


def test_normalize_thread_key_strips_lut_prefix():
    from app.services.reply import normalize_thread_key
    assert normalize_thread_key("[LUT] Meeting notes") == "meeting notes"


def test_normalize_thread_key_strips_nested_prefixes():
    from app.services.reply import normalize_thread_key
    assert normalize_thread_key("Re: [LUT] Re: Weekly sync") == "weekly sync"


def test_normalize_thread_key_lowercase():
    from app.services.reply import normalize_thread_key
    assert normalize_thread_key("Action Required") == "action required"


def test_normalize_thread_key_empty():
    from app.services.reply import normalize_thread_key
    assert normalize_thread_key("") == ""
    assert normalize_thread_key(None) == ""


# ── get_sent_thread_keys ───────────────────────────────────────────────────────

def test_get_sent_thread_keys_empty(db):
    from app.services.reply import get_sent_thread_keys
    assert get_sent_thread_keys(db) == set()


def test_get_sent_thread_keys_returns_set(db):
    from app.services.reply import get_sent_thread_keys
    seed_sent_email(db, filename="s1.md", thread_key="project update")
    seed_sent_email(db, filename="s2.md", thread_key="budget review")
    keys = get_sent_thread_keys(db)
    assert keys == {"project update", "budget review"}


def test_get_sent_thread_keys_ignores_incoming(db):
    from app.services.reply import get_sent_thread_keys
    db.execute("INSERT INTO emails (filename, direction, thread_key) VALUES (?,?,?)",
               ["in.md", "incoming", "some topic"])
    db.commit()
    assert get_sent_thread_keys(db) == set()


# ── mark_replied_by_thread ────────────────────────────────────────────────────

def test_mark_replied_by_thread_updates_matching(db):
    from app.services.reply import mark_replied_by_thread
    aid = _make_action_with_subject(db, "Project update")
    updated = mark_replied_by_thread(db, {"project update"})
    assert updated == 1
    assert db.execute("SELECT replied FROM digest_actions WHERE id=?", [aid]).fetchone()[0] == 1


def test_mark_replied_by_thread_skips_already_replied(db):
    from app.services.reply import mark_replied_by_thread
    _make_action_with_subject(db, "Old topic", replied=1)
    updated = mark_replied_by_thread(db, {"old topic"})
    assert updated == 0


def test_mark_replied_by_thread_returns_count(db):
    from app.services.reply import mark_replied_by_thread
    _make_action_with_subject(db, "Topic A")
    _make_action_with_subject(db, "Topic B")
    count = mark_replied_by_thread(db, {"topic a", "topic b"})
    assert count == 2


def test_mark_replied_by_thread_empty_keys(db):
    from app.services.reply import mark_replied_by_thread
    _make_action_with_subject(db, "Anything")
    assert mark_replied_by_thread(db, set()) == 0


def test_mark_replied_by_thread_sets_replied_at(db):
    from app.services.reply import mark_replied_by_thread
    aid = _make_action_with_subject(db, "Deadline check")
    mark_replied_by_thread(db, {"deadline check"})
    row = db.execute("SELECT replied_at FROM digest_actions WHERE id=?", [aid]).fetchone()
    assert row["replied_at"] is not None


# ── mark_action_replied ───────────────────────────────────────────────────────

def test_mark_action_replied_returns_true(db):
    from app.services.reply import mark_action_replied
    aid = _make_action_with_subject(db, "Follow-up needed")
    assert mark_action_replied(db, aid) is True
    assert db.execute("SELECT replied FROM digest_actions WHERE id=?", [aid]).fetchone()[0] == 1


def test_mark_action_replied_returns_false_for_missing(db):
    from app.services.reply import mark_action_replied
    assert mark_action_replied(db, 99999) is False


def test_mark_action_replied_sets_replied_at(db):
    from app.services.reply import mark_action_replied
    aid = _make_action_with_subject(db, "Check this")
    mark_action_replied(db, aid)
    row = db.execute("SELECT replied_at FROM digest_actions WHERE id=?", [aid]).fetchone()
    assert row["replied_at"] is not None


# ── get_reply_history ─────────────────────────────────────────────────────────

def test_get_reply_history_empty(db):
    from app.services.reply import get_reply_history
    assert get_reply_history(db) == []


def test_get_reply_history_returns_replied_items(db):
    from app.services.reply import get_reply_history, mark_action_replied
    aid = _make_action_with_subject(db, "Done item")
    mark_action_replied(db, aid)
    history = get_reply_history(db)
    assert len(history) == 1
    assert history[0]["summary"] == "Test action"


def test_get_reply_history_excludes_unreplied(db):
    from app.services.reply import get_reply_history
    _make_action_with_subject(db, "Pending item")
    assert get_reply_history(db) == []


def test_get_reply_history_respects_limit(db):
    from app.services.reply import get_reply_history, mark_action_replied
    did = seed_digest(db)
    for i in range(5):
        aid = seed_action(db, did, summary=f"Action {i}", replied=1)
    history = get_reply_history(db, limit=3)
    assert len(history) == 3


# ── Route: mark_replied ───────────────────────────────────────────────────────

def test_mark_replied_route_ok(client, db):
    aid = _make_action_with_subject(db, "Need reply")
    r = client.post(f"/digest/action/{aid}/reply")
    assert r.get_json()["ok"] is True
    assert db.execute("SELECT replied FROM digest_actions WHERE id=?", [aid]).fetchone()[0] == 1


def test_mark_replied_route_404_for_missing(client):
    r = client.post("/digest/action/99999/reply")
    assert r.status_code == 404
    assert r.get_json()["ok"] is False


# ── Route: replies index ──────────────────────────────────────────────────────

def test_replies_index_loads(client):
    assert client.get("/replies/").status_code == 200


def test_replies_index_shows_replied_action(client, db):
    from app.services.reply import mark_action_replied
    did = seed_digest(db)
    aid = seed_action(db, did, summary="Confirmed deal", replied=0)
    mark_action_replied(db, aid)
    r = client.get("/replies/")
    assert b"Confirmed deal" in r.data


def test_replies_index_empty_state(client):
    r = client.get("/replies/")
    assert b"No replied actions yet" in r.data


# ── Dashboard integration ─────────────────────────────────────────────────────

def test_dashboard_shows_mark_replied_button_for_unreplied(client, db):
    did = seed_digest(db)
    seed_action(db, did, summary="Unreplied action", replied=0)
    r = client.get("/")
    assert b"Mark replied" in r.data


def test_dashboard_shows_replied_badge_for_replied(client, db):
    did = seed_digest(db)
    seed_action(db, did, summary="Already replied action", replied=1)
    r = client.get("/")
    assert b"replied-badge" in r.data
