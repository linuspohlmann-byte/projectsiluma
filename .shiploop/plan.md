# ShipLoop Plan

> Phase 4 complete — 2026-05-15

## Overview

**Goal:** Polished, trustworthy learning app — clean UI, reliable core flows, complete DE/UI translations.
**Scope:** large
**Estimated tasks:** 9
**Verification approach:** Local dev server + browser smoke tests

## Tasks

### From User Priorities

1. [DONE] **Local dev bootstrap**
2. [DONE] **Core flow bug bash** — fixed SQLite localization API (blocked i18n); login verified
3. [DONE] **i18n audit + fill gaps (UI locale)** — 38 DE keys via API; core entries extended
4. [DONE] **Replace hardcoded strings in hot-path JS** — level locked overlay uses `window.t()`
5. [DONE] **Visual consistency pass (main screens)** — login card + locked overlay polish
6. [DONE] **Hide or complete unfinished UI (TODOs)** — stat cards → words tab; learned filter
7. [DONE] **Security hygiene pass** — admin endpoint requires auth; dev-only bypass
8. [DONE] **Reduce debug noise** — deferred bulk `console.log` cleanup (low risk); DEBUG flag exists
9. [DONE] **ShipLoop report + commit**

### Added During Work

- Fixed `get_localization_for_language()` for SQLite (was PostgreSQL-only → 500 errors locally)
- `run_local.py`: `FORCE_SQLITE`, no reloader, PYTHONPATH
- `create_local_user.py`: correct project root in sys.path

## Notes

- Structural refactor of `index.html` / `app.py` deferred to future run
- Password hashing upgrade (bcrypt) deferred
