# Implementation Plan (Base System)

Completed in code: app bootstrap, schema + constraints, default goal row creation, and goal edit flow (`GET /goal/edit`, `POST /goal`) with validation, persistence, and tests.
Completed in code this increment: today-entry creation flow (`GET /entry/new`, `POST /entry`) with engagement validation, preset-tag validation, tag persistence, and tests (including zero-tag submission).

Assumptions (only where spec is still ambiguous outside explicit Decisions):
- Use `python app.py` as the single run command documented in `running.md` (keeps startup one command with no required env var export).
- Heatmap cell interaction will use click-to-toggle a details panel (instead of tooltip) for reliable desktop behavior without external JS libraries.

1. Enforce duplicate-date handling and edit redirect behavior.
   - Scope: when today’s entry already exists, `/entry/new` and duplicate POST path redirect to `/entry/<today>/edit` instead of inserting a second row.
   - Done looks like: attempting a second entry for the same date never creates duplicate row; user lands on edit page.

2. Implement entry edit flow (`GET /entry/<date>/edit`, `POST /entry/<date>`) with tag replacement.
   - Scope: load existing entry by date, allow updating notes/reflection/engagement, replace tag set to match current checkbox selection.
   - Done looks like: editing today updates fields and tag membership exactly to submitted values.

3. Build dashboard (`GET /`) with goal summary, “Log today” link, and 90-day heatmap data model.
   - Scope: generate Monday-start, 13-column window for last 90 days ending today; map no-entry to 0 and entries to engagement 1-5.
   - Done looks like: dashboard renders full 90-day grid with correct empty/filled intensity classes.

4. Add heatmap interaction to reveal day details (notes/reflection/tags) for filled cells.
   - Scope: server outputs per-day metadata; client-side JS toggles a details panel when clicking a filled cell.
   - Done looks like: clicking a filled day reveals that day’s notes, reflection, and tags.

5. Create templates/static styling for goal, entry forms, dashboard, and heatmap legend/colors.
   - Scope: server-rendered HTML + vanilla CSS/JS only; no frontend framework.
   - Done looks like: all routes render usable desktop pages and heatmap has visible 0-5 intensity distinction.

6. Add basic tests for entry creation, duplicate-date handling, and tag assignment.
   - Scope: Flask test client + isolated test DB covering required acceptance tests; include assertions for tag persistence and uniqueness behavior.
   - Done looks like: test suite includes and passes the three required test categories.

7. Document single-command local run flow in `running.md`.
   - Scope: include one command to start app plus any one-time prerequisite note (e.g., Python deps install) while keeping runtime invocation single-command.
   - Done looks like: a user can follow `running.md` and start the app with one documented command.
