from flask import Blueprint, render_template, request, jsonify, current_app
from ..database import get_db
from ..services.weekly import list_weekly_summaries, generate_weekly_summary

bp = Blueprint("weekly_summaries", __name__)


@bp.route("/")
def index():
    summaries = list_weekly_summaries(get_db())
    return render_template("weekly_summaries/index.html", summaries=summaries)


@bp.route("/generate", methods=["POST"])
def generate():
    body = request.get_json(force=True) or {}
    week_start = body.get("week_start") or None
    ok, result = generate_weekly_summary(current_app.config, week_start)
    if ok:
        return jsonify({"ok": True, "id": result})
    return jsonify({"ok": False, "msg": str(result)}), 400
