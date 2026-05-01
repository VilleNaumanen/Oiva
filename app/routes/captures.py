from flask import Blueprint, request, jsonify
from ..database import get_db

bp = Blueprint("captures", __name__)


@bp.route("/add", methods=["POST"])
def add():
    text = (request.get_json(force=True) or {}).get("text", "").strip()
    if not text:
        return jsonify({"ok": False, "msg": "text required"})
    db = get_db()
    cid = db.execute(
        "INSERT INTO captures (text) VALUES (?)", [text]
    ).lastrowid
    db.commit()
    row = db.execute("SELECT * FROM captures WHERE id=?", [cid]).fetchone()
    return jsonify({"ok": True, "capture": dict(row)})


@bp.route("/<int:capture_id>/done", methods=["POST"])
def mark_done(capture_id):
    db = get_db()
    db.execute("UPDATE captures SET done=1 WHERE id=?", [capture_id])
    db.commit()
    return jsonify({"ok": True})


@bp.route("/<int:capture_id>/promote", methods=["POST"])
def promote(capture_id):
    """Promote a capture to a full digest action item."""
    db = get_db()
    capture = db.execute("SELECT * FROM captures WHERE id=?", [capture_id]).fetchone()
    if not capture:
        return jsonify({"ok": False, "msg": "capture not found"})
    from datetime import date
    digest = db.execute(
        "SELECT id FROM digests ORDER BY created_at DESC, id DESC LIMIT 1"
    ).fetchone()
    if not digest:
        did = db.execute(
            "INSERT INTO digests (date, noise_count) VALUES (?,?)",
            [date.today().isoformat(), 0]
        ).lastrowid
    else:
        did = digest["id"]
    aid = db.execute(
        "INSERT INTO digest_actions (digest_id,category,summary,action_verb) VALUES (?,?,?,?)",
        [did, "action", capture["text"], "Action"]
    ).lastrowid
    db.execute(
        "UPDATE captures SET done=1, promoted_to_action_id=? WHERE id=?",
        [aid, capture_id]
    )
    db.commit()
    return jsonify({"ok": True, "action_id": aid})
