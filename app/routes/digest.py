from flask import Blueprint, request, jsonify, current_app
from ..database import get_db
from ..services.digest import persist_digest
from ..services.email_parser import archive_inbox_emails

bp = Blueprint("digest", __name__)


def _normalise(data: dict) -> dict:
    """Promote flat 'actions' list to split format when split keys are absent."""
    if not data.get("action_required") and not data.get("worth_knowing"):
        ar, wk = [], []
        for item in data.get("actions", []):
            (ar if item.get("category") == "action" else wk).append(item)
        data = {**data, "action_required": ar, "worth_knowing": wk}
    return data


@bp.route("/save", methods=["POST"])
def save():
    data = _normalise(request.get_json(force=True))
    db = get_db()
    did = persist_digest(db, data)
    archive_inbox_emails(current_app.config["INBOX"])
    return jsonify({"ok": True, "digest_id": did})


@bp.route("/run-siiri", methods=["POST"])
def run_siiri():
    from ..services import siiri as siiri_service
    ok, result = siiri_service.run_digest(current_app.config)
    if ok:
        return jsonify({"ok": True, "digest_id": result})
    return jsonify({"ok": False, "msg": str(result)})


@bp.route("/action/<int:action_id>/toggle", methods=["POST"])
def toggle(action_id):
    db = get_db()
    row = db.execute("SELECT done FROM digest_actions WHERE id=?", [action_id]).fetchone()
    if row:
        db.execute("UPDATE digest_actions SET done=? WHERE id=?",
                   [0 if row["done"] else 1, action_id])
        db.commit()
    return jsonify({"ok": True})


@bp.route("/action/<int:action_id>/note", methods=["POST"])
def save_note(action_id):
    note = request.get_json(force=True).get("note", "")
    db = get_db()
    db.execute("UPDATE digest_actions SET note=? WHERE id=?", [note, action_id])
    db.commit()
    return jsonify({"ok": True})


@bp.route("/action/<int:action_id>/reply", methods=["POST"])
def mark_replied(action_id):
    db = get_db()
    db.execute("UPDATE digest_actions SET replied=1 WHERE id=?", [action_id])
    db.commit()
    return jsonify({"ok": True})


@bp.route("/feed-siiri", methods=["POST"])
def feed_siiri():
    import os
    from datetime import date
    db = get_db()
    digest = db.execute(
        "SELECT id FROM digests ORDER BY created_at DESC, id DESC LIMIT 1"
    ).fetchone()
    if not digest:
        return jsonify({"ok": False, "msg": "No digest"})
    rows = db.execute(
        "SELECT note FROM digest_actions WHERE digest_id=? AND note LIKE 'Siiri,%'",
        [digest["id"]]
    ).fetchall()
    entries = [r["note"].strip() for r in rows if r["note"]]
    if not entries:
        return jsonify({"ok": False, "msg": "No Siiri instructions found in notes"})
    prefs = current_app.config["SIIRI_PREFS"]
    os.makedirs(os.path.dirname(prefs), exist_ok=True)
    with open(prefs, "a", encoding="utf-8") as f:
        f.write(f"\n\n## Added {date.today().isoformat()}\n")
        for entry in entries:
            f.write(f"- {entry}\n")
    return jsonify({"ok": True, "count": len(entries)})
