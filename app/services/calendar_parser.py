import json
import os
from datetime import date


def _infer_source(filename: str) -> str:
    """Infer calendar source from filename prefix when JSON doesn't set it."""
    if "[LUT]" in filename:
        return "lut"
    return "calendar"


def import_calendar_files(db, config: dict) -> int:
    cal_dir = config.get("CALENDAR", "")
    if not cal_dir or not os.path.isdir(cal_dir):
        return 0

    today = date.today().isoformat()
    processed_dir = os.path.join(cal_dir, "Processed", today)
    imported = 0

    for fname in sorted(os.listdir(cal_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(cal_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        title = (data.get("title") or "").strip()
        evt_date = (data.get("date") or "").strip()
        if not title or not evt_date:
            continue

        exists = db.execute(
            "SELECT id FROM meetings WHERE title=? AND date=?", [title, evt_date]
        ).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO meetings (title, date, time_start, time_end, location, organizer, source) "
                "VALUES (?,?,?,?,?,?,?)",
                [title, evt_date,
                 data.get("time_start"), data.get("time_end"),
                 data.get("location"), data.get("organizer"),
                 data.get("source") or _infer_source(fname)]
            )
            db.commit()
            imported += 1

        os.makedirs(processed_dir, exist_ok=True)
        archive_path = os.path.join(processed_dir, fname)
        if os.path.exists(archive_path):
            os.remove(fpath)
        else:
            os.rename(fpath, archive_path)

    return imported
