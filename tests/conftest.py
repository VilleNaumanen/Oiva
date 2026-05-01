"""
Shared fixtures and seed helpers for the Oiva test suite.

Architecture (Eeli):
- `app` fixture creates a fresh Flask app with an isolated tmp DB per test.
- `client` fixture gives an HTTP test client bound to that app.
- `db` fixture gives a raw sqlite3 connection for seeding — faster than going
  through HTTP for setup, and keeps tests independent of the routes being tested.
- Seed helpers are plain functions (not fixtures) so they can be composed freely.
"""
import os
import sqlite3
import pytest
from app import create_app


# ── Core fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def app(tmp_path):
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()
    _app = create_app("testing", test_config={
        "DB_PATH":     str(tmp_path / "test.db"),
        "INBOX":       str(inbox_dir),
        "SIIRI_PREFS": str(tmp_path / "prefs.md"),
        "UPLOADS":     str(tmp_path / "uploads"),
    })
    yield _app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture
def db(app):
    """Raw connection for seeding — bypasses route layer intentionally."""
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ── Seed helpers ───────────────────────────────────────────────────────────────

def seed_digest(conn, date="2026-04-30", noise=0):
    did = conn.execute(
        "INSERT INTO digests (date, noise_count) VALUES (?,?)", [date, noise]
    ).lastrowid
    conn.commit()
    return did


def seed_action(conn, digest_id, *, category="action", summary="Test action",
                deadline=None, done=0, note=None, email_subject=None,
                action_verb=None, source=None, replied=0):
    aid = conn.execute(
        """INSERT INTO digest_actions
           (digest_id, category, summary, deadline, done, note,
            email_subject, action_verb, source, replied)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [digest_id, category, summary, deadline, done, note,
         email_subject, action_verb, source, replied]
    ).lastrowid
    conn.commit()
    return aid


def seed_meeting(conn, *, title="Test Meeting", date="2099-05-10", done=0,
                 location=None, organizer=None):
    mid = conn.execute(
        "INSERT INTO meetings (title, date, done, location, organizer) VALUES (?,?,?,?,?)",
        [title, date, done, location, organizer]
    ).lastrowid
    conn.commit()
    return mid


def seed_capture(conn, *, text="Quick thought", done=0):
    cid = conn.execute(
        "INSERT INTO captures (text, done) VALUES (?,?)", [text, done]
    ).lastrowid
    conn.commit()
    return cid


def seed_project(conn, *, name="Test Project", status="active",
                 deadline=None, next_action=None):
    pid = conn.execute(
        "INSERT INTO projects (name, status, deadline, next_action) VALUES (?,?,?,?)",
        [name, status, deadline, next_action]
    ).lastrowid
    conn.commit()
    return pid


def seed_contact(conn, *, name="Test Contact", organisation=None,
                 email=None, role=None):
    cid = conn.execute(
        "INSERT INTO contacts (name, organisation, email, role) VALUES (?,?,?,?)",
        [name, organisation, email, role]
    ).lastrowid
    conn.commit()
    return cid


def seed_sent_email(conn, *, filename="sent_test.md", thread_key="test topic"):
    conn.execute(
        "INSERT OR IGNORE INTO emails (filename, direction, thread_key) VALUES (?,?,?)",
        [filename, "sent", thread_key]
    )
    conn.commit()
