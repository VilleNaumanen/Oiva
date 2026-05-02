"""Tests for the urgent items service (get_urgent_items)."""
from app.services.urgent import get_urgent_items
from .conftest import seed_meeting, seed_action, seed_digest, seed_project

TODAY    = "2099-01-01"
TOMORROW = "2099-01-02"


def test_project_deadline_in_urgent(db):
    seed_project(db, name="Big Project", deadline=TOMORROW)
    items = get_urgent_items(db, TODAY)
    assert any(i["type"] == "project" and i["title"] == "Big Project" for i in items)


def test_project_deadline_today(db):
    seed_project(db, name="Due Today", deadline=TODAY)
    items = get_urgent_items(db, TODAY)
    item = next(i for i in items if i["title"] == "Due Today")
    assert item["days_away"] == 0
    assert item["verb"] == "DEADLINE"


def test_project_no_deadline_excluded(db):
    seed_project(db, name="No Deadline")
    items = get_urgent_items(db, TODAY)
    assert not any(i["title"] == "No Deadline" for i in items)


def test_closed_project_excluded(db):
    seed_project(db, name="Closed Project", status="closed", deadline=TOMORROW)
    items = get_urgent_items(db, TODAY)
    assert not any(i["title"] == "Closed Project" for i in items)


def test_urgent_sorted_by_date(db):
    seed_meeting(db, title="Late Meeting", date="2099-03-01")
    did = seed_digest(db)
    seed_action(db, did, summary="Early Action", deadline="2099-01-15")
    seed_project(db, name="Mid Project", deadline="2099-02-01")
    items = get_urgent_items(db, TODAY)
    dates = [i["date"] for i in items]
    assert dates == sorted(dates)
