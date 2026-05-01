import sqlite3
from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """Return the request-scoped DB connection, opening one if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Create all tables if they do not exist and run pending migrations."""
    from flask import current_app
    db = sqlite3.connect(current_app.config["DB_PATH"])
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    _create_schema(db)
    db.close()

    current_app.teardown_appcontext(close_db)


def _create_schema(db: sqlite3.Connection) -> None:
    db.executescript("""
        -- ── Core digest ────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS digests (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL,
            noise_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS digest_actions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            digest_id    INTEGER REFERENCES digests(id) ON DELETE CASCADE,
            category     TEXT    NOT NULL,
            summary      TEXT    NOT NULL,
            detail       TEXT,
            deadline     TEXT,
            email_from   TEXT,
            email_subject TEXT,
            action_verb  TEXT,
            source       TEXT,
            note         TEXT,
            done         INTEGER DEFAULT 0,
            replied      INTEGER DEFAULT 0,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS processed_emails (
            filename     TEXT PRIMARY KEY,
            processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Email storage ───────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS emails (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            filename   TEXT UNIQUE NOT NULL,
            direction  TEXT NOT NULL DEFAULT 'incoming',
            from_addr  TEXT,
            subject    TEXT,
            date_str   TEXT,
            body_text  TEXT,
            thread_key TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Meetings ────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS meetings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            date       TEXT NOT NULL,
            time_start TEXT,
            time_end   TEXT,
            location   TEXT,
            organizer  TEXT,
            attendees  TEXT,
            agenda     TEXT,
            source     TEXT DEFAULT 'manual',
            done       INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Quick captures ──────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS captures (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            text       TEXT NOT NULL,
            done       INTEGER DEFAULT 0,
            promoted_to_action_id INTEGER REFERENCES digest_actions(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Projects ────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT,
            status      TEXT DEFAULT 'active',
            theme       TEXT,
            owner       TEXT,
            deadline    TEXT,
            next_action TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS project_contacts (
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
            PRIMARY KEY (project_id, contact_id)
        );

        CREATE TABLE IF NOT EXISTS project_actions (
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            action_id  INTEGER REFERENCES digest_actions(id) ON DELETE CASCADE,
            PRIMARY KEY (project_id, action_id)
        );

        -- ── Contacts ────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS contacts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            organisation TEXT,
            role         TEXT,
            email        TEXT,
            notes        TEXT,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Notes (backlog — schema preserved for data migration) ───────────
        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT,
            content    TEXT NOT NULL,
            theme      TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tags (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
            tag_id  INTEGER REFERENCES tags(id)  ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS attachments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id         INTEGER REFERENCES notes(id) ON DELETE CASCADE,
            filename        TEXT NOT NULL,
            file_path       TEXT NOT NULL,
            attachment_type TEXT NOT NULL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Weekly summaries ────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS weekly_summaries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            week_end   TEXT NOT NULL,
            content    TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Test runs ───────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS test_runs (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            total   INTEGER DEFAULT 0,
            passed  INTEGER DEFAULT 0,
            failed  INTEGER DEFAULT 0,
            output  TEXT
        );
    """)

    # Indexes for high-frequency query patterns (Lauri)
    db.executescript("""
        CREATE INDEX IF NOT EXISTS idx_digest_actions_digest_id
            ON digest_actions(digest_id);
        CREATE INDEX IF NOT EXISTS idx_digest_actions_done_deadline
            ON digest_actions(done, deadline);
        CREATE INDEX IF NOT EXISTS idx_digest_actions_done
            ON digest_actions(done);
        CREATE INDEX IF NOT EXISTS idx_meetings_date_done
            ON meetings(date, done);
        CREATE INDEX IF NOT EXISTS idx_emails_thread_key
            ON emails(thread_key);
        CREATE INDEX IF NOT EXISTS idx_emails_direction
            ON emails(direction);
        CREATE INDEX IF NOT EXISTS idx_captures_done
            ON captures(done);
        CREATE INDEX IF NOT EXISTS idx_projects_status
            ON projects(status);
    """)

    db.commit()
