"""Weekly Summary service — generates and persists AI-written week reviews."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

WEEKLY_SUMMARY_PROMPT = """You are Siiri, personal secretary for Ville Naumanen, Director of EMRC at Kempower.

Generate a concise weekly summary in plain markdown. Write factual bullet points — no editorialising, no greetings, no filler.

Structure your output with these sections (omit any section that has no items):

## Actions completed / replied
## Still open — pending actions
## Meetings
## Projects
## Key information

Rules:
- Each bullet is one crisp line
- Use **bold** only for deadlines and critical names
- No markdown headers beyond ##
- If a section is empty, omit it entirely
- End with a one-line "Week in one sentence" summary
"""


def week_bounds(anchor: str) -> tuple[str, str]:
    """Return (monday_iso, sunday_iso) for the week containing anchor date."""
    d = date.fromisoformat(anchor)
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def _last_complete_week() -> tuple[str, str]:
    """Return bounds of the most recently completed Mon–Sun week."""
    today = date.today()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday.isoformat(), last_sunday.isoformat()


def gather_week_data(db: sqlite3.Connection, week_start: str, week_end: str) -> dict:
    """Collect all relevant records for the given week."""
    actions = db.execute(
        """SELECT da.category, da.summary, da.detail, da.deadline,
                  da.action_verb, da.email_from, da.source, da.done, da.replied
           FROM digest_actions da
           JOIN digests d ON da.digest_id = d.id
           WHERE d.date BETWEEN ? AND ?
           ORDER BY da.category, da.done, da.replied""",
        [week_start, week_end],
    ).fetchall()

    meetings = db.execute(
        "SELECT title, date, time_start, location, organizer FROM meetings"
        " WHERE date BETWEEN ? AND ? ORDER BY date, time_start",
        [week_start, week_end],
    ).fetchall()

    projects = db.execute(
        "SELECT name, deadline, next_action FROM projects"
        " WHERE status='active' ORDER BY deadline ASC NULLS LAST LIMIT 15",
    ).fetchall()

    notes = db.execute(
        "SELECT title, content FROM notes ORDER BY created_at DESC LIMIT 10"
    ).fetchall()

    return {
        "actions":  [dict(r) for r in actions],
        "meetings": [dict(r) for r in meetings],
        "projects": [dict(r) for r in projects],
        "notes":    [dict(r) for r in notes],
    }


def build_summary_input(data: dict, week_start: str, week_end: str) -> str:
    """Format gathered week data as structured text for Claude."""
    lines = [f"WEEK: {week_start} to {week_end}\n"]

    if data["actions"]:
        lines.append("EMAIL ACTIONS THIS WEEK:")
        for a in data["actions"]:
            verb = f"[{a['action_verb']}] " if a["action_verb"] else ""
            status = "DONE" if a["done"] else ("REPLIED" if a["replied"] else "OPEN")
            src = f" ({a['source']})" if a["source"] else ""
            lines.append(f"  [{status}] {verb}{a['summary']}{src}")
            if a["detail"]:
                lines.append(f"    → {a['detail'][:200]}")
            if a["deadline"]:
                lines.append(f"    deadline: {a['deadline']}")

    if data["meetings"]:
        lines.append("\nMEETINGS THIS WEEK:")
        for m in data["meetings"]:
            time = f" {m['time_start']}" if m["time_start"] else ""
            loc = f" @ {m['location']}" if m["location"] else ""
            lines.append(f"  {m['date']}{time}: {m['title']}{loc}")

    if data["projects"]:
        lines.append("\nACTIVE PROJECTS:")
        for p in data["projects"]:
            due = f" (due {p['deadline']})" if p["deadline"] else ""
            nxt = f" → {p['next_action']}" if p["next_action"] else ""
            lines.append(f"  {p['name']}{due}{nxt}")

    if data["notes"]:
        lines.append("\nRECENT NOTES:")
        for n in data["notes"]:
            title = f"{n['title']}: " if n["title"] else ""
            lines.append(f"  {title}{n['content'][:200]}")

    return "\n".join(lines)


def persist_weekly_summary(db: sqlite3.Connection, week_start: str, week_end: str, content: str) -> int:
    """Insert a weekly summary record and return its id."""
    row_id = db.execute(
        "INSERT INTO weekly_summaries (week_start, week_end, content) VALUES (?,?,?)",
        [week_start, week_end, content],
    ).lastrowid
    db.commit()
    return row_id


def list_weekly_summaries(db: sqlite3.Connection) -> list[dict]:
    """Return all weekly summaries ordered newest first."""
    rows = db.execute(
        "SELECT id, week_start, week_end, content, created_at"
        " FROM weekly_summaries ORDER BY week_start DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def generate_weekly_summary(config: dict, week_start: str | None = None) -> tuple[bool, str | int]:
    """Orchestrate data gathering, Claude API call, and persistence.

    Returns (True, id) on success or (False, error_message) on failure.
    """
    api_key = config.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return False, "ANTHROPIC_API_KEY not configured."

    from flask import current_app
    from ..database import get_db

    db = get_db()

    if week_start:
        w_start, w_end = week_bounds(week_start)
    else:
        w_start, w_end = _last_complete_week()

    existing = db.execute(
        "SELECT id FROM weekly_summaries WHERE week_start=?", [w_start]
    ).fetchone()
    if existing:
        return True, existing["id"]

    data = gather_week_data(db, w_start, w_end)
    if not data["actions"] and not data["meetings"]:
        return False, f"No digest actions or meetings found for {w_start} – {w_end}."

    user_text = build_summary_input(data, w_start, w_end)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=[{"type": "text", "text": WEEKLY_SUMMARY_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_text}],
        )
        content = resp.content[0].text.strip()
    except Exception as e:
        return False, f"Claude API error: {e}"

    summary_id = persist_weekly_summary(db, w_start, w_end, content)
    return True, summary_id
