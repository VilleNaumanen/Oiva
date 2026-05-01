from flask import Blueprint, request, jsonify, current_app
from ..database import get_db
from ..services import siiri as siiri_service
from ..services.email_parser import archive_inbox_emails

bp = Blueprint("digest", __name__)


@bp.route("/save", methods=["POST"])
def save():
    data = request.get_json(force=True)
    from datetime import date

    action_required = data.get("action_required", [])
    worth_knowing = data.get("worth_knowing", [])
    if not action_required and not worth_knowing:
        for item in data.get("actions", []):
            (action_required if item.get("category") == "action" else worth_knowing).append(item)

    db = get_db()
    did = db.execute(
        "INSERT INTO digests (date, noise_count) VALUES (?,?)",
        [date.today().isoformat(), data.get("noise_count", 0)]
    ).lastrowid
    for item in action_required:
        db.execute(
            "INSERT INTO digest_actions (digest_id,category,action_verb,summary,detail,deadline,email_from,email_subject,source) VALUES (?,?,?,?,?,?,?,?,?)",
            [did, "action", item.get("action_verb", ""), item.get("summary", ""),
             item.get("detail", ""), item.get("deadline"), item.get("email_from", ""),
             item.get("email_subject", ""), item.get("source", "")]
        )
    for item in worth_knowing:
        db.execute(
            "INSERT INTO digest_actions (digest_id,category,summary,detail,email_from,email_subject,source) VALUES (?,?,?,?,?,?,?)",
            [did, "info", item.get("summary", ""), item.get("detail", ""),
             item.get("email_from", ""), item.get("email_subject", ""), item.get("source", "")]
        )
    for m in data.get("meetings", []):
        if m.get("title") and m.get("date"):
            db.execute(
                "INSERT INTO meetings (title,date,time_start,time_end,location,organizer,source) VALUES (?,?,?,?,?,?,?)",
                [m["title"], m["date"], m.get("time_start"), m.get("time_end"),
                 m.get("location"), m.get("organizer"), "siiri"]
            )
    db.commit()
    archive_inbox_emails(current_app.config["INBOX"])
    return jsonify({"ok": True, "digest_id": did})


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
    from datetime import date
    import os
    prefs = current_app.config["SIIRI_PREFS"]
    os.makedirs(os.path.dirname(prefs), exist_ok=True)
    with open(prefs, "a", encoding="utf-8") as f:
        f.write(f"\n\n## Added {date.today().isoformat()}\n")
        for entry in entries:
            f.write(f"- {entry}\n")
    return jsonify({"ok": True, "count": len(entries)})
