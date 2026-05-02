import re
import sqlite3


def normalize_thread_key(subject: str) -> str:
    """Strip reply/forward/LUT prefixes and return a canonical lowercase key."""
    s = (subject or "").strip()
    for _ in range(20):
        prev = s
        s = re.sub(r"^\[LUT\]\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^sent_email\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^(Re|Fwd|FW|FWD|VS|VL|SV):\s*", "", s, flags=re.IGNORECASE)
        s = s.strip()
        if s == prev:
            break
    return s.lower().strip()


def get_sent_thread_keys(db: sqlite3.Connection) -> set[str]:
    """Return the set of thread keys for all outgoing emails."""
    rows = db.execute(
        "SELECT DISTINCT thread_key FROM emails"
        " WHERE direction='sent' AND thread_key IS NOT NULL AND thread_key != ''"
    ).fetchall()
    return {r["thread_key"] for r in rows}


def mark_replied_by_thread(db: sqlite3.Connection, thread_keys: set[str]) -> int:
    """Bulk-mark unreplied actions whose subject matches a sent thread key.

    Returns the number of actions updated.
    """
    if not thread_keys:
        return 0
    count = 0
    for action in db.execute(
        "SELECT id, email_subject FROM digest_actions"
        " WHERE replied=0 AND email_subject IS NOT NULL AND email_subject != ''"
    ).fetchall():
        if normalize_thread_key(action["email_subject"]) in thread_keys:
            db.execute(
                "UPDATE digest_actions SET replied=1, replied_at=CURRENT_TIMESTAMP WHERE id=?",
                [action["id"]],
            )
            count += 1
    if count:
        db.commit()
    return count


def mark_action_replied(db: sqlite3.Connection, action_id: int) -> bool:
    """Mark a single action as replied. Returns False if the id does not exist."""
    row = db.execute("SELECT id FROM digest_actions WHERE id=?", [action_id]).fetchone()
    if not row:
        return False
    db.execute(
        "UPDATE digest_actions SET replied=1, replied_at=CURRENT_TIMESTAMP WHERE id=?",
        [action_id],
    )
    db.commit()
    return True


def get_reply_history(db: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Return replied actions ordered by most recently replied, with digest date."""
    rows = db.execute(
        """SELECT da.id, da.summary, da.email_from, da.email_subject,
                  da.replied_at, d.date AS digest_date
           FROM digest_actions da
           LEFT JOIN digests d ON da.digest_id = d.id
           WHERE da.replied = 1
           ORDER BY da.replied_at DESC, da.id DESC
           LIMIT ?""",
        [limit],
    ).fetchall()
    return [dict(r) for r in rows]
