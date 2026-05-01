# ADR-001: Application Structure

**Date:** 2026-05-01
**Status:** Accepted
**Author:** Harri (Senior SW Architect)

## Context

Rebuilding Oiva Notes as Oiva — a full work management tool. The previous codebase was a single 730-line `app.py` monolith. With 8 feature areas and a team of developers working in parallel, that structure is not tenable.

## Decision

Adopt a **modular Flask application** using the application factory pattern with blueprints and a service layer.

### Structure

```
oiva/
├── app/
│   ├── __init__.py        # create_app() factory
│   ├── database.py        # DB connection, schema init, indexes
│   ├── routes/            # One blueprint per feature area (HTTP only)
│   │   ├── dashboard.py
│   │   ├── digest.py
│   │   ├── meetings.py
│   │   ├── captures.py
│   │   ├── projects.py
│   │   ├── contacts.py
│   │   └── admin.py
│   ├── services/          # Business logic (no HTTP concerns)
│   │   ├── siiri.py       # Email triage + Claude API
│   │   ├── email_parser.py # Email parsing, thread keys, archiving
│   │   └── urgent.py      # Urgent items aggregation
│   ├── models/            # Structured data access (future)
│   ├── templates/         # Jinja2 templates per area
│   └── static/            # CSS, JS, images
├── config.py              # DevelopmentConfig / TestingConfig / ProductionConfig
├── run.py                 # Entry point
├── migrations/            # SQL migration scripts (Lauri)
├── tests/                 # pytest suite (Eeli)
└── docs/adr/              # Architecture decision records
```

### Key principles

1. **Routes handle HTTP only** — no business logic in route handlers. Parse request, call service, return response.
2. **Services are framework-agnostic** — services receive plain Python arguments, not Flask request objects. This makes them independently testable.
3. **DB via `get_db()`** — request-scoped connection using Flask's `g`. Tests override `DB_PATH` in config.
4. **Config classes** — `create_app(config_name)` accepts `"development"`, `"testing"`, `"production"`. No hardcoded paths.
5. **Indexes at schema init** — Lauri's indexes defined in `database.py` alongside schema, not as migrations.

## Alternatives considered

- **Single `app.py`** — rejected. Doesn't scale to team development across 8 feature areas.
- **Full ORM (SQLAlchemy)** — rejected. SQLite at this scale doesn't need ORM overhead. Direct queries with `sqlite3.Row` are readable and fast.
- **Microservices** — rejected. Overkill. Single deployable with clean internal boundaries is correct for this scale.

## Stack verdict

No stack changes. Python/Flask + SQLite + vanilla HTML/CSS/JS remains correct. The problem was structure, not technology. Noora will evaluate frontend frameworks separately (ADR-002) when the UI build begins.

## Consequences

- Each blueprint can be developed and tested independently
- `TestingConfig` lets Eeli override `DB_PATH` with a temp DB — no production data touched
- New feature areas require: one route file in `routes/`, one service in `services/`, templates in `templates/<area>/`, and registration in `create_app()`
