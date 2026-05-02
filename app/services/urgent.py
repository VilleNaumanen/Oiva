import sqlite3
from datetime import date


def get_urgent_items(db: sqlite3.Connection, today_str: str, limit: int = 5) -> list:
    items = []
    for m in db.execute(
        "SELECT id, title, date, location FROM meetings WHERE date >= ? AND done=0 ORDER BY date ASC LIMIT ?",
        [today_str, limit]
    ).fetchall():
        days = (date.fromisoformat(m["date"]) - date.fromisoformat(today_str)).days
        items.append({"type": "meeting", "id": m["id"], "title": m["title"],
                      "date": m["date"], "days_away": days, "verb": "MEETING", "source": None})
    for a in db.execute(
        "SELECT id, summary, deadline, action_verb, source FROM digest_actions "
        "WHERE done=0 AND deadline IS NOT NULL AND deadline >= ? ORDER BY deadline ASC LIMIT ?",
        [today_str, limit]
    ).fetchall():
        days = (date.fromisoformat(a["deadline"]) - date.fromisoformat(today_str)).days
        items.append({"type": "action", "id": a["id"], "title": a["summary"],
                      "date": a["deadline"], "days_away": days,
                      "verb": a["action_verb"] or "Action", "source": a["source"]})
    for p in db.execute(
        "SELECT id, name, deadline FROM projects "
        "WHERE status='active' AND deadline IS NOT NULL AND deadline >= ? ORDER BY deadline ASC LIMIT ?",
        [today_str, limit]
    ).fetchall():
        days = (date.fromisoformat(p["deadline"]) - date.fromisoformat(today_str)).days
        items.append({"type": "project", "id": p["id"], "title": p["name"],
                      "date": p["deadline"], "days_away": days, "verb": "DEADLINE", "source": None})
    items.sort(key=lambda x: x["date"])
    return items[:limit]
