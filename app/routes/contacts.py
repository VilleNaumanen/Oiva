from flask import Blueprint, render_template, request, jsonify
from ..database import get_db

bp = Blueprint("contacts", __name__)


@bp.route("/")
def index():
    db = get_db()
    q = request.args.get("q", "")
    if q:
        contacts = db.execute(
            "SELECT * FROM contacts WHERE name LIKE ? OR organisation LIKE ? OR email LIKE ? ORDER BY name",
            [f"%{q}%", f"%{q}%", f"%{q}%"]
        ).fetchall()
    else:
        contacts = db.execute("SELECT * FROM contacts ORDER BY name").fetchall()
    return render_template("contacts/index.html", contacts=contacts, q=q)


@bp.route("/<int:contact_id>")
def detail(contact_id):
    db = get_db()
    contact = db.execute("SELECT * FROM contacts WHERE id=?", [contact_id]).fetchone()
    if not contact:
        return "Not found", 404
    recent_actions = db.execute(
        "SELECT * FROM digest_actions WHERE email_from LIKE ? ORDER BY created_at DESC LIMIT 10",
        [f"%{contact['email']}%"] if contact["email"] else [f"%{contact['name']}%"]
    ).fetchall()
    return render_template("contacts/detail.html", contact=contact, recent_actions=recent_actions)


@bp.route("/add", methods=["POST"])
def add():
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify({"ok": False, "msg": "name required"})
    db = get_db()
    cid = db.execute(
        "INSERT INTO contacts (name,organisation,role,email,notes) VALUES (?,?,?,?,?)",
        [data["name"], data.get("organisation"), data.get("role"),
         data.get("email"), data.get("notes")]
    ).lastrowid
    db.commit()
    return jsonify({"ok": True, "id": cid})


@bp.route("/<int:contact_id>/update", methods=["POST"])
def update(contact_id):
    data = request.get_json(force=True)
    db = get_db()
    db.execute(
        "UPDATE contacts SET name=?,organisation=?,role=?,email=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
        [data.get("name"), data.get("organisation"), data.get("role"),
         data.get("email"), data.get("notes"), contact_id]
    )
    db.commit()
    return jsonify({"ok": True})
