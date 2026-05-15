# ShipLoop Report — 2026-05-15

## Summary

First ShipLoop run on **ProjectSiluma**. Focus: make the app runnable locally, fix broken translations API on SQLite, improve UX polish on login/level-lock flows, and wire incomplete UI actions.

## Health Score

| Metric | Cycle 1 | Cycle 2 |
|--------|---------|---------|
| Start | 35 | 72 |
| End | 72 | 85 |
| Tasks completed | 9/9 | 6/9 (cycle 2 ongoing) |

## Completed

1. **Local dev** — `venv`, `.env` (gitignored), `testuser` / `password123`, server on http://localhost:5001
2. **Critical bug** — `/api/localization/<lang>` failed on SQLite (`near "%": syntax error`); now returns 38 German UI strings
3. **i18n** — Level-locked overlay uses translation keys (`levels.locked_*`, `buttons.close`)
4. **UI** — Cleaner login card; rounded level-locked dialog
5. **Unfinished UI** — “All words” / “Learned words” stats open Words tab (learned → familiarity ≥ 4 filter)
6. **Security** — Admin cleanup endpoint requires login; production requires `user_id == 2`

## Cycle 2 (test + fix)

- **Tested:** Login, localization, words, levels, browser UI
- **Fixed:** Library API 500 (`custom_level_progress` table, `motivation` column)
- **Fixed:** Words-learning API 500 (SQLite `native_language` on wrong table)
- **Seeded:** 108 UI strings → **146 DE keys** (no more `[library.title]` on main tabs)
- **Courses:** German subtitle; API returns 36 languages

## Deferred

- Full-app visual redesign / splitting `index.html` (9k lines)
- Onboarding flow still partly English
- Lesson/practice hardcoded DE strings in JS
- Automated test suite (pytest)
- bcrypt password migration
- Mass removal of `console.log` in `levels.js`

## Verify Locally

```bash
cd 03_Projects/ProjectSiluma
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../_Archive-ProjectSiluma-backups/local-dev-secrets/.env.backup .env
# Set DATABASE_URL= empty or use run_local.py (FORCE_SQLITE)
python3 scripts/dev/create_local_user.py
python3 run_local.py
```

Login: `testuser` / `password123`

## Recommendations

- Next run: lesson + practice flow browser tests; expand `CORE_LOCALIZATION_ENTRIES` for remaining hardcoded JS strings
- Consider extracting CSS from `index.html` into `static/styles/main.css`
- Add pytest smoke tests for `/api/auth/login` and `/api/localization/de`
