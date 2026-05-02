from flask import Blueprint, request, jsonify, render_template, current_app
from ..database import get_db
from ..services.urgent import get_urgent_items
from datetime import date, timedelta

bp = Blueprint("meetings", __name__)


@bp.route("/")
def index():
    db = get_db()
    today = date.today().isoformat()
    two_weeks_ago = (date.today() - timedelta(days=14)).isoformat()
    upcoming = db.execute(
        "SELECT * FROM meetings WHERE date >= ? AND done=0 ORDER BY date ASC",
        [today]
    ).fetchall()
    past = db.execute(
        "SELECT * FROM meetings WHERE date >= ? AND date < ? ORDER BY date DESC LIMIT 20",
        [two_weeks_ago, today]
    ).fetchall()
    return render_template("meetings/index.html", upcoming=upcoming, past=past, today=today)


@bp.route("/add", methods=["POST"])
def add():
    data = request.get_json(force=True)
    if not data.get("title") or not data.get("date"):
        return jsonify({"ok": False, "msg": "title and date required"})
    db = get_db()
    mid = db.execute(
        "INSERT INTO meetings (title,date,time_start,time_end,location,organizer,attendees,agenda,source) VALUES (?,?,?,?,?,?,?,?,?)",
        [data["title"], data["date"], data.get("time_start"), data.get("time_end"),
         data.get("location"), data.get("organizer"), data.get("attendees"),
         data.get("agenda"), data.get("source", "manual")]
    ).lastrowid
    db.commit()
    return jsonify({"ok": True, "id": mid})


@bp.route("/<int:meeting_id>/dismiss", methods=["POST"])
def dismiss(meeting_id):
    db = get_db()
    db.execute("UPDATE meetings SET done=1 WHERE id=?", [meeting_id])
    db.commit()
    return jsonify({"ok": True})


@bp.route("/delete/<int:meeting_id>", methods=["POST"])
def delete(meeting_id):
    db = get_db()
    db.execute("DELETE FROM meetings WHERE id=?", [meeting_id])
    db.commit()
    return jsonify({"ok": True})


@bp.route("/urgent-items")
def urgent_items():
    db = get_db()
    items = get_urgent_items(db, date.today().isoformat())
    return jsonify(items)


@bp.route("/import-calendar", methods=["POST"])
def import_calendar():
    from ..services.calendar_parser import import_calendar_files
    db = get_db()
    n = import_calendar_files(db, current_app.config)
    return jsonify({"ok": True, "imported": n})
