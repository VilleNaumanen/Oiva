import os
from flask import Blueprint, request, jsonify, render_template, current_app
from werkzeug.utils import secure_filename
from ..database import get_db

bp = Blueprint("notes", __name__)

_ALLOWED = {
    "pdf", "txt", "md", "csv",
    "png", "jpg", "jpeg", "gif", "webp",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx",
}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED


def _save_tags(db, note_id: int, tags: list[str]):
    db.execute("DELETE FROM note_tags WHERE note_id=?", [note_id])
    for raw in tags:
        name = raw.strip().lower()
        if not name:
            continue
        db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", [name])
        tag_id = db.execute("SELECT id FROM tags WHERE name=?", [name]).fetchone()["id"]
        db.execute("INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?,?)", [note_id, tag_id])


def _notes_with_tags(db, tag_filter: str = ""):
    if tag_filter:
        rows = db.execute(
            """SELECT n.*, GROUP_CONCAT(t.name, ',') AS tag_names
               FROM notes n
               LEFT JOIN note_tags nt ON n.id = nt.note_id
               LEFT JOIN tags t       ON nt.tag_id = t.id
               WHERE n.id IN (
                   SELECT nt2.note_id FROM note_tags nt2
                   JOIN tags t2 ON nt2.tag_id = t2.id WHERE t2.name = ?
               )
               GROUP BY n.id ORDER BY n.created_at DESC""",
            [tag_filter]
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT n.*, GROUP_CONCAT(t.name, ',') AS tag_names
               FROM notes n
               LEFT JOIN note_tags nt ON n.id = nt.note_id
               LEFT JOIN tags t       ON nt.tag_id = t.id
               GROUP BY n.id ORDER BY n.created_at DESC"""
        ).fetchall()
    return rows


@bp.route("/")
def index():
    db = get_db()
    tag_filter = request.args.get("tag", "").strip().lower()
    notes = _notes_with_tags(db, tag_filter)

    note_ids = [r["id"] for r in notes]
    attachments: dict[int, list] = {}
    if note_ids:
        ph = ",".join("?" * len(note_ids))
        for a in db.execute(
            f"SELECT * FROM attachments WHERE note_id IN ({ph})", note_ids
        ).fetchall():
            attachments.setdefault(a["note_id"], []).append(dict(a))

    all_tags = [r["name"] for r in db.execute("SELECT name FROM tags ORDER BY name").fetchall()]
    return render_template(
        "notes/index.html",
        notes=notes,
        attachments=attachments,
        all_tags=all_tags,
        tag_filter=tag_filter,
    )


@bp.route("/add", methods=["POST"])
def add():
    data = request.get_json(force=True)
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"ok": False, "msg": "content required"})
    db = get_db()
    nid = db.execute(
        "INSERT INTO notes (title, content) VALUES (?,?)",
        [(data.get("title") or "").strip() or None, content]
    ).lastrowid
    _save_tags(db, nid, [t for t in (data.get("tags") or []) if t])
    db.commit()
    return jsonify({"ok": True, "id": nid})


@bp.route("/<int:note_id>/update", methods=["POST"])
def update(note_id):
    data = request.get_json(force=True)
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"ok": False, "msg": "content required"})
    db = get_db()
    db.execute(
        "UPDATE notes SET title=?, content=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        [(data.get("title") or "").strip() or None, content, note_id]
    )
    _save_tags(db, note_id, [t for t in (data.get("tags") or []) if t])
    db.commit()
    return jsonify({"ok": True})


@bp.route("/<int:note_id>/delete", methods=["POST"])
def delete(note_id):
    db = get_db()
    for a in db.execute("SELECT file_path FROM attachments WHERE note_id=?", [note_id]).fetchall():
        try:
            os.remove(a["file_path"])
        except OSError:
            pass
    db.execute("DELETE FROM notes WHERE id=?", [note_id])
    db.commit()
    return jsonify({"ok": True})


@bp.route("/<int:note_id>/attach", methods=["POST"])
def attach(note_id):
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "no file"})
    f = request.files["file"]
    if not f.filename or not _allowed(f.filename):
        return jsonify({"ok": False, "msg": "file type not allowed"})

    fname = secure_filename(f.filename)
    ext = fname.rsplit(".", 1)[1].lower() if "." in fname else ""
    atype = "image" if ext in {"png","jpg","jpeg","gif","webp"} else "pdf" if ext == "pdf" else "file"

    note_dir = os.path.join(current_app.config["UPLOADS"], str(note_id))
    os.makedirs(note_dir, exist_ok=True)
    fpath = os.path.join(note_dir, fname)
    f.save(fpath)

    db = get_db()
    aid = db.execute(
        "INSERT INTO attachments (note_id, filename, file_path, attachment_type) VALUES (?,?,?,?)",
        [note_id, fname, fpath, atype]
    ).lastrowid
    db.commit()
    return jsonify({"ok": True, "id": aid, "filename": fname, "type": atype})


@bp.route("/<int:note_id>/attach/<int:attach_id>/delete", methods=["POST"])
def delete_attachment(note_id, attach_id):
    db = get_db()
    a = db.execute(
        "SELECT file_path FROM attachments WHERE id=? AND note_id=?", [attach_id, note_id]
    ).fetchone()
    if a:
        try:
            os.remove(a["file_path"])
        except OSError:
            pass
        db.execute("DELETE FROM attachments WHERE id=?", [attach_id])
        db.commit()
    return jsonify({"ok": True})
