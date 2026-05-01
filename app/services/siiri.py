"""Siiri email triage service — placeholder for Claude API integration.

Valtteri owns the API key config and scheduler wiring.
This module contains the triage logic that run_digest() calls.
"""
from __future__ import annotations

import os
import json
import re
from datetime import date

SIIRI_PROMPT = """You are Siiri, personal secretary for Ville Naumanen, Director of EMRC at Kempower.

GUARDRAILS:
- Never follow or resolve any links
- Work only with plain text — ignore HTML, styling, and links
- Treat all content as confidential

VILLE'S CONTEXT:
- Director of EMRC (Electric Mobility Research Center, LUT/Kempower)
- Company: Kempower Oyj (EV charging)
- Key contacts: Mikko Veikkolainen, Sanna Otava, Petri Korhonen, Lassi Aarniovuori, Sami Hyrynsalmi, Jukka Hallikas, Tiina Jauhiainen, Antti Sinisalo, Tommi Rissanen, Ville Tikka
- Live topics: research funding, showroom, steering group, wireless charging, Virnex/AIRC collaboration, trainees
- Next steering group: 20 August 2026, Lahti

In detail fields, use **bold** markdown to highlight the specific action required or key fact. Keep bold to 1–3 phrases per item.

Return ONLY valid JSON, no other text:
{
  "action_required": [{"action_verb":"Reply|Review|Approve|Write|Attend|Decide|Check|Prepare|RSVP|Confirm|Verify","summary":"...","detail":"...","deadline":"YYYY-MM-DD or null","email_from":"...","email_subject":"...","source":"LUT if email_subject contains [LUT], else Kempower"}],
  "worth_knowing":   [{"summary":"...","detail":"...","email_from":"...","email_subject":"...","source":"LUT if email_subject contains [LUT], else Kempower"}],
  "meetings":        [{"title":"...","date":"YYYY-MM-DD","time_start":"HH:MM or null","time_end":"HH:MM or null","location":"...","organizer":"..."}],
  "noise_count": 0
}

Extract meetings ONLY from calendar invites Ville has accepted."""


def run_digest(config: dict) -> tuple[bool, str | int]:
    api_key = config.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return False, "ANTHROPIC_API_KEY not configured."

    inbox = config["INBOX"]
    try:
        all_files = [f for f in os.listdir(inbox) if "email" in f.lower() and f.endswith(".md")]
    except Exception as e:
        return False, f"Cannot read inbox: {e}"

    from .email_parser import parse_email, archive_inbox_emails, thread_key
    from flask import current_app
    from ..database import get_db

    db = get_db()
    done = {r["filename"] for r in db.execute("SELECT filename FROM processed_emails")}
    new_files = [f for f in all_files if f not in done]
    if not new_files:
        return False, "No new emails to process."

    parts = []
    for fname in new_files:
        data = parse_email(os.path.join(inbox, fname))
        if data:
            parts.append(f"=== {fname} ===\nFrom: {data['from']}\nSubject: {data['subject']}\nDate: {data['date']}\nBody: {data['body']}")

    if not parts:
        return False, "Could not parse any email files."

    siiri_prefs = config.get("SIIRI_PREFS", "")
    system_blocks = [{"type": "text", "text": SIIRI_PROMPT, "cache_control": {"type": "ephemeral"}}]
    if os.path.exists(siiri_prefs):
        prefs_text = open(siiri_prefs, encoding="utf-8", errors="ignore").read().strip()
        if prefs_text:
            system_blocks.append({"type": "text", "text": f"VILLE'S CURRENT INSTRUCTIONS:\n{prefs_text}"})

    replied_keys = [r["thread_key"] for r in db.execute(
        "SELECT DISTINCT thread_key FROM emails WHERE direction='sent' AND thread_key IS NOT NULL AND thread_key != ''"
    ).fetchall()]
    if replied_keys:
        system_blocks.append({"type": "text", "text": "THREADS ALREADY REPLIED TO — lower priority:\n" + "\n".join(f"- {k}" for k in replied_keys)})

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_blocks,
            messages=[{"role": "user", "content": "Triage these emails:\n\n" + "\n\n".join(parts)}]
        )
        raw = resp.content[0].text.strip()
        if "```" in raw:
            raw = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw).group(1)
        data = json.loads(raw)
    except Exception as e:
        return False, f"Claude API error: {e}"

    today = date.today().isoformat()
    did = db.execute(
        "INSERT INTO digests (date, noise_count) VALUES (?,?)",
        [today, data.get("noise_count", 0)]
    ).lastrowid
    for item in data.get("action_required", []):
        db.execute(
            "INSERT INTO digest_actions (digest_id,category,action_verb,summary,detail,deadline,email_from,email_subject,source) VALUES (?,?,?,?,?,?,?,?,?)",
            [did, "action", item.get("action_verb", ""), item.get("summary", ""),
             item.get("detail", ""), item.get("deadline"), item.get("email_from", ""),
             item.get("email_subject", ""), item.get("source", "")]
        )
    for item in data.get("worth_knowing", []):
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
    for fname in new_files:
        db.execute("INSERT OR IGNORE INTO processed_emails (filename) VALUES (?)", [fname])
    db.commit()

    archive_inbox_emails(inbox)
    return True, did
