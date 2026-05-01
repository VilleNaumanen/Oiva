"""Tests for service-layer functions — no HTTP, pure logic."""
from app.services.email_parser import thread_key
from app.services.urgent import get_urgent_items
import sqlite3


# ── thread_key ─────────────────────────────────────────────────────────────────

def test_thread_key_plain():
    assert thread_key("Project Alpha") == "project alpha"

def test_thread_key_strips_re():
    assert thread_key("Re: Project Alpha") == "project alpha"

def test_thread_key_strips_fwd():
    assert thread_key("FWD: Project Alpha") == "project alpha"

def test_thread_key_strips_lut():
    assert thread_key("[LUT] Re: Project Alpha") == "project alpha"

def test_thread_key_strips_sent_email():
    assert thread_key("sent_email Re: Project Alpha") == "project alpha"

def test_thread_key_complex_chain():
    assert thread_key("[LUT] sent_email Re: Project Alpha") == "project alpha"

def test_thread_key_empty():
    assert thread_key("") == ""

def test_thread_key_none():
    assert thread_key(None) == ""

def test_thread_key_idempotent():
    key = thread_key("Project Alpha")
    assert thread_key(key) == key

def test_thread_key_vs():
    assert thread_key("VS: Budget review") == "budget review"

def test_thread_key_sv():
    assert thread_key("SV: Budget review") == "budget review"


# ── get_urgent_items ───────────────────────────────────────────────────────────

def _make_db(tmp_path):
    """Helper: spin up a minimal test DB for service-layer tests."""
    from app import create_app
    app = create_app("testing", test_config={"DB_PATH": str(tmp_path / "svc.db")})
    with app.app_context():
        pass  # init_db() already called
    conn = sqlite3.connect(str(tmp_path / "svc.db"))
    conn.row_factory = sqlite3.Row
    return conn


def test_urgent_items_empty(tmp_path):
    conn = _make_db(tmp_path)
    assert get_urgent_items(conn, "2026-05-01") == []


def test_urgent_items_meeting_appears(tmp_path):
    conn = _make_db(tmp_path)
    conn.execute("INSERT INTO meetings (title, date, done) VALUES (?,?,?)",
                 ["Big review", "2099-06-01", 0])
    conn.commit()
    items = get_urgent_items(conn, "2026-05-01")
    assert any(i["title"] == "Big review" for i in items)


def test_urgent_items_action_with_deadline(tmp_path):
    conn = _make_db(tmp_path)
    conn.execute("INSERT INTO digests (date) VALUES (?)", ["2026-05-01"])
    did = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO digest_actions (digest_id,category,summary,deadline,done) VALUES (?,?,?,?,?)",
        [did, "action", "Deadline task", "2099-01-01", 0]
    )
    conn.commit()
    items = get_urgent_items(conn, "2026-05-01")
    assert any(i["title"] == "Deadline task" for i in items)


def test_urgent_items_limit(tmp_path):
    conn = _make_db(tmp_path)
    conn.execute("INSERT INTO digests (date) VALUES (?)", ["2026-05-01"])
    did = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for i in range(8):
        conn.execute(
            "INSERT INTO digest_actions (digest_id,category,summary,deadline,done) VALUES (?,?,?,?,?)",
            [did, "action", f"Task {i}", f"2099-{i+1:02d}-01", 0]
        )
    conn.commit()
    assert len(get_urgent_items(conn, "2026-05-01")) <= 5
