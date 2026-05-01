from flask import Blueprint, render_template
from ..database import get_db
from ..services.urgent import get_urgent_items
from datetime import date

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def dashboard():
    today = date.today().isoformat()
    db = get_db()

    digest = db.execute(
        "SELECT * FROM digests ORDER BY created_at DESC, id DESC LIMIT 1"
    ).fetchone()

    actions = []
    if digest:
        actions = db.execute("""
            SELECT da.*, d.date AS digest_date
            FROM digest_actions da
            JOIN digests d ON da.digest_id = d.id
            WHERE da.digest_id = ?
               OR (da.done = 0 AND da.digest_id != ?)
            ORDER BY da.category, da.done, d.date DESC, da.id
        """, [digest["id"], digest["id"]]).fetchall()

    captures = db.execute(
        "SELECT * FROM captures WHERE done = 0 ORDER BY created_at DESC LIMIT 20"
    ).fetchall()

    urgent_items = get_urgent_items(db, today)

    next_meeting = db.execute(
        "SELECT * FROM meetings WHERE date >= ? AND done = 0 ORDER BY date ASC LIMIT 1",
        [today]
    ).fetchone()

    days_away = None
    if next_meeting:
        days_away = (date.fromisoformat(next_meeting["date"]) - date.today()).days

    followups = db.execute("""
        SELECT da.id, da.note, d.date AS digest_date
        FROM digest_actions da
        JOIN digests d ON da.digest_id = d.id
        WHERE da.done = 0
          AND da.note IS NOT NULL AND da.note != ''
          AND da.note NOT LIKE 'Siiri,%'
    """).fetchall()

    active_projects = db.execute(
        "SELECT * FROM projects WHERE status = 'active' ORDER BY deadline ASC LIMIT 5"
    ).fetchall()

    return render_template(
        "dashboard/index.html",
        digest=digest,
        actions=actions,
        captures=captures,
        urgent_items=urgent_items,
        next_meeting=next_meeting,
        days_away=days_away,
        followups=followups,
        active_projects=active_projects,
        today=today,
    )
