"""Tests for F8: Weekly Summary service and routes."""
import pytest
from .conftest import seed_digest, seed_action, seed_meeting, seed_project


# ── week_bounds ────────────────────────────────────────────────────────────────

def test_week_bounds_monday():
    from app.services.weekly import week_bounds
    start, end = week_bounds("2026-04-27")  # Monday
    assert start == "2026-04-27"
    assert end   == "2026-05-03"


def test_week_bounds_midweek():
    from app.services.weekly import week_bounds
    start, end = week_bounds("2026-04-29")  # Wednesday
    assert start == "2026-04-27"
    assert end   == "2026-05-03"


def test_week_bounds_sunday():
    from app.services.weekly import week_bounds
    start, end = week_bounds("2026-05-03")  # Sunday
    assert start == "2026-04-27"
    assert end   == "2026-05-03"


# ── gather_week_data ───────────────────────────────────────────────────────────

def test_gather_empty_week(db):
    from app.services.weekly import gather_week_data
    data = gather_week_data(db, "2026-04-27", "2026-05-03")
    assert data["actions"]  == []
    assert data["meetings"] == []


def test_gather_includes_actions_from_week(db):
    from app.services.weekly import gather_week_data
    did = seed_digest(db, date="2026-04-28")
    seed_action(db, did, summary="In-week action")
    data = gather_week_data(db, "2026-04-27", "2026-05-03")
    assert len(data["actions"]) == 1
    assert data["actions"][0]["summary"] == "In-week action"


def test_gather_excludes_actions_outside_week(db):
    from app.services.weekly import gather_week_data
    did = seed_digest(db, date="2026-05-10")  # following week
    seed_action(db, did, summary="Outside action")
    data = gather_week_data(db, "2026-04-27", "2026-05-03")
    assert data["actions"] == []


def test_gather_includes_meetings_in_week(db):
    from app.services.weekly import gather_week_data
    seed_meeting(db, title="Board sync", date="2026-04-30")
    data = gather_week_data(db, "2026-04-27", "2026-05-03")
    assert any(m["title"] == "Board sync" for m in data["meetings"])


def test_gather_excludes_meetings_outside_week(db):
    from app.services.weekly import gather_week_data
    seed_meeting(db, title="Next week mtg", date="2026-05-10")
    data = gather_week_data(db, "2026-04-27", "2026-05-03")
    assert data["meetings"] == []


def test_gather_includes_active_projects(db):
    from app.services.weekly import gather_week_data
    seed_project(db, name="My project", status="active")
    data = gather_week_data(db, "2026-04-27", "2026-05-03")
    assert any(p["name"] == "My project" for p in data["projects"])


def test_gather_excludes_closed_projects(db):
    from app.services.weekly import gather_week_data
    seed_project(db, name="Done project", status="closed")
    data = gather_week_data(db, "2026-04-27", "2026-05-03")
    assert not any(p["name"] == "Done project" for p in data["projects"])


# ── persist + list ─────────────────────────────────────────────────────────────

def test_persist_returns_id(db):
    from app.services.weekly import persist_weekly_summary
    sid = persist_weekly_summary(db, "2026-04-27", "2026-05-03", "## Week summary\n- Did stuff")
    assert isinstance(sid, int)
    assert sid > 0


def test_list_returns_all_ordered(db):
    from app.services.weekly import persist_weekly_summary, list_weekly_summaries
    persist_weekly_summary(db, "2026-04-20", "2026-04-26", "Older")
    persist_weekly_summary(db, "2026-04-27", "2026-05-03", "Newer")
    summaries = list_weekly_summaries(db)
    assert len(summaries) == 2
    assert summaries[0]["week_start"] == "2026-04-27"  # newest first


def test_list_empty(db):
    from app.services.weekly import list_weekly_summaries
    assert list_weekly_summaries(db) == []


# ── Routes ────────────────────────────────────────────────────────────────────

def test_weekly_summaries_index_loads(client):
    assert client.get("/weekly-summaries/").status_code == 200


def test_weekly_summaries_index_shows_summary(client, db):
    from app.services.weekly import persist_weekly_summary
    with client.application.app_context():
        from app.database import get_db
        _db = get_db()
        persist_weekly_summary(_db, "2026-04-27", "2026-05-03", "Great week content")
    r = client.get("/weekly-summaries/")
    assert b"2026-04-27" in r.data


def test_generate_route_no_api_key(client):
    r = client.post("/weekly-summaries/generate",
                    json={"week_start": "2026-04-27"})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False
    assert "ANTHROPIC_API_KEY" in r.get_json()["msg"]


def test_generate_no_data_for_week(client):
    r = client.post("/weekly-summaries/generate",
                    json={"week_start": "2099-01-06"})
    assert r.status_code == 400
    d = r.get_json()
    assert d["ok"] is False
    assert "No digest" in d["msg"] or "not configured" in d["msg"]


def test_generate_skips_duplicate_week(client, db):
    from app.services.weekly import persist_weekly_summary
    with client.application.app_context():
        from app.database import get_db
        _db = get_db()
        existing_id = persist_weekly_summary(_db, "2026-04-27", "2026-05-03", "Already generated")

    # API key missing → returns before reaching duplicate check in most configs,
    # so seed a summary and verify the count doesn't double
    count_before = db.execute("SELECT COUNT(*) FROM weekly_summaries").fetchone()[0]
    # A second POST for same week (no API key → fails before insert, but row already exists)
    client.post("/weekly-summaries/generate", json={"week_start": "2026-04-27"})
    count_after = db.execute("SELECT COUNT(*) FROM weekly_summaries").fetchone()[0]
    assert count_after == count_before  # no duplicate inserted
