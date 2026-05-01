import os
import re
import shutil
from datetime import date
from html.parser import HTMLParser


class _Stripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._buf = []

    def handle_data(self, d):
        self._buf.append(d)

    def text(self):
        return re.sub(r"\s+", " ", " ".join(self._buf)).strip()


def strip_html(s: str) -> str:
    p = _Stripper()
    try:
        p.feed(s)
    except Exception:
        pass
    return p.text()


def thread_key(subject: str) -> str:
    """Normalise a subject line to a bare thread key for reply matching."""
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


def parse_email(path: str) -> dict | None:
    try:
        raw = open(path, encoding="utf-8", errors="ignore").read()
        fm = re.search(r"\*\*From:\*\*\s*(.+)", raw)
        sm = re.search(r"\*\*Subject:\*\*\s*(.+)", raw)
        dm = re.search(r"\*\*Date:\*\*\s*(.+)", raw)
        body = raw.split("---", 1)[1] if "---" in raw else raw
        body = strip_html(body) if "<html" in body.lower() else body.strip()
        return {
            "from": fm.group(1).strip() if fm else "",
            "subject": sm.group(1).strip() if sm else "",
            "date": dm.group(1).strip() if dm else "",
            "body": body[:3000],
        }
    except Exception:
        return None


def archive_inbox_emails(inbox: str) -> None:
    from flask import current_app
    from ..database import get_db

    today = date.today().isoformat()
    archive_dir = os.path.join(inbox, "Processed", today)
    os.makedirs(archive_dir, exist_ok=True)

    db = get_db()
    try:
        files = [f for f in os.listdir(inbox) if "_email_" in f and f.endswith(".md")]
    except Exception:
        return

    for fname in files:
        data = parse_email(os.path.join(inbox, fname))
        if data:
            direction = "sent" if "sent_email" in fname.lower() else "incoming"
            tkey = thread_key(data["subject"])
            try:
                db.execute(
                    "INSERT OR IGNORE INTO emails (filename,direction,from_addr,subject,date_str,body_text,thread_key) VALUES (?,?,?,?,?,?,?)",
                    [fname, direction, data["from"], data["subject"], data["date"], data["body"], tkey]
                )
            except Exception:
                pass
        try:
            shutil.move(os.path.join(inbox, fname), os.path.join(archive_dir, fname))
        except Exception:
            pass

    db.commit()
    _mark_replied_actions(db)


def _mark_replied_actions(db) -> None:
    sent_keys = {r["thread_key"] for r in db.execute(
        "SELECT DISTINCT thread_key FROM emails WHERE direction='sent' AND thread_key IS NOT NULL AND thread_key != ''"
    ).fetchall()}
    if not sent_keys:
        return
    for action in db.execute(
        "SELECT id, email_subject FROM digest_actions WHERE replied=0 AND email_subject IS NOT NULL AND email_subject != ''"
    ).fetchall():
        if thread_key(action["email_subject"]) in sent_keys:
            db.execute("UPDATE digest_actions SET replied=1 WHERE id=?", [action["id"]])
    db.commit()
