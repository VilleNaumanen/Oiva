from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from ..database import get_db

bp = Blueprint("projects", __name__)


@bp.route("/")
def index():
    db = get_db()
    status = request.args.get("status", "active")
    projects = db.execute(
        "SELECT * FROM projects WHERE status=? ORDER BY deadline ASC, updated_at DESC",
        [status]
    ).fetchall()
    return render_template("projects/index.html", projects=projects, status=status)


@bp.route("/add", methods=["POST"])
def add():
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify({"ok": False, "msg": "name required"})
    db = get_db()
    pid = db.execute(
        "INSERT INTO projects (name,description,status,theme,owner,deadline,next_action) VALUES (?,?,?,?,?,?,?)",
        [data["name"], data.get("description"), data.get("status", "active"),
         data.get("theme"), data.get("owner"), data.get("deadline"), data.get("next_action")]
    ).lastrowid
    db.commit()
    return jsonify({"ok": True, "id": pid})


@bp.route("/<int:project_id>/update", methods=["POST"])
def update(project_id):
    data = request.get_json(force=True)
    db = get_db()
    db.execute(
        "UPDATE projects SET name=?,description=?,status=?,theme=?,owner=?,deadline=?,next_action=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
        [data.get("name"), data.get("description"), data.get("status"),
         data.get("theme"), data.get("owner"), data.get("deadline"),
         data.get("next_action"), project_id]
    )
    db.commit()
    return jsonify({"ok": True})


@bp.route("/<int:project_id>/close", methods=["POST"])
def close(project_id):
    db = get_db()
    db.execute("UPDATE projects SET status='closed', updated_at=CURRENT_TIMESTAMP WHERE id=?",
               [project_id])
    db.commit()
    return jsonify({"ok": True})


@bp.route("/<int:project_id>/snooze-urgent", methods=["POST"])
def snooze_urgent(project_id):
    return jsonify({"ok": True})
