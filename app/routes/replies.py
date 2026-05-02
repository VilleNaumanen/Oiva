from flask import Blueprint, render_template
from ..database import get_db
from ..services.reply import get_reply_history

bp = Blueprint("replies", __name__)


@bp.route("/")
def index():
    replied_actions = get_reply_history(get_db(), limit=50)
    return render_template("replies/index.html", replied_actions=replied_actions)
