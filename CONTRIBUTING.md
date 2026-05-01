# Contributing to Oiva

## Branching strategy

| Branch | Purpose | Who merges |
|--------|---------|------------|
| `main` | Production-ready code only. Protected — no direct pushes. | Tero (after review) |
| `develop` | Integration branch. All feature branches merge here first. | Any team member via PR |
| `feature/<name>` | One branch per feature or task. Branch from `develop`. | PR into `develop` |
| `fix/<name>` | Bug fixes. Branch from `develop` (or `main` for hotfixes). | PR into `develop` |
| `release/<version>` | Release preparation. Branch from `develop`, merges into `main`. | Tero |

## Commit message convention

Format: `<type>: <short description>`

| Type | When to use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `chore` | Tooling, config, dependencies |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `refactor` | Code change with no behaviour change |
| `style` | Formatting, whitespace |

Examples:
```
feat: add quick capture input to dashboard
fix: carry-over query returns wrong digest on same-second saves
test: add integration tests for meeting dismiss endpoint
docs: update API reference for /urgent-items
```

## Pull request rules

- Every feature PR must reference the feature spec (e.g. `Implements: F2-reply-tracking`)
- PR description must include: what changed, how to test it, screenshots for UI changes
- At least one approval required before merge to `develop`
- All tests must pass before merge
- Tero reviews and merges PRs into `main`

## Versioning

Semantic versioning: `MAJOR.MINOR.PATCH`

- `PATCH` — bug fixes, no new features
- `MINOR` — new features, backwards compatible
- `MAJOR` — breaking changes or major redesigns

Current version: `0.1.0` (pre-release)
