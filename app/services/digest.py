"""Shared digest persistence logic used by both the HTTP save route and the in-app Siiri triage."""
from datetime import date


def persist_digest(db, data: dict) -> int:
    """Insert a digest + its actions and meetings. Returns the new digest ID."""
    today = date.today().isoformat()
    did = db.execute(
        "INSERT INTO digests (date, noise_count) VALUES (?,?)",
        [today, data.get("noise_count", 0)]
    ).lastrowid

    for item in data.get("action_required", []):
        db.execute(
            "INSERT INTO digest_actions "
            "(digest_id,category,action_verb,summary,detail,deadline,email_from,email_subject,source) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [did, "action",
             item.get("action_verb", ""), item.get("summary", ""),
             item.get("detail", ""),      item.get("deadline"),
             item.get("email_from", ""),  item.get("email_subject", ""),
             item.get("source", "")]
        )

    for item in data.get("worth_knowing", []):
        db.execute(
            "INSERT INTO digest_actions "
            "(digest_id,category,summary,detail,email_from,email_subject,source) "
            "VALUES (?,?,?,?,?,?,?)",
            [did, "info",
             item.get("summary", ""),    item.get("detail", ""),
             item.get("email_from", ""), item.get("email_subject", ""),
             item.get("source", "")]
        )

    for m in data.get("meetings", []):
        if m.get("title") and m.get("date"):
            db.execute(
                "INSERT INTO meetings (title,date,time_start,time_end,location,organizer,source) "
                "VALUES (?,?,?,?,?,?,?)",
                [m["title"], m["date"],
                 m.get("time_start"), m.get("time_end"),
                 m.get("location"),   m.get("organizer"), "siiri"]
            )

    db.commit()
    return did
