# Implementation Plan (Base System)

Completed in code: app bootstrap, schema + constraints, default goal row creation, and goal edit flow (`GET /goal/edit`, `POST /goal`) with validation, persistence, and tests.
Completed in code this increment: today-entry creation flow (`GET /entry/new`, `POST /entry`) with engagement validation, preset-tag validation, tag persistence, and tests (including zero-tag submission).
Completed in code this increment: duplicate-date handling now redirects to edit (`GET /entry/new` + duplicate `POST /entry`), plus entry edit flow (`GET /entry/<date>/edit`, `POST /entry/<date>`) with full field updates and tag replacement; tests cover duplicate behavior and edit updates.
Completed in code this increment: dashboard (`GET /`) now renders goal summary + “Log today” link and a Monday-start 13-column heatmap grid with 0-5 intensity classes backed by entry engagement data.

Assumptions (only where spec is still ambiguous outside explicit Decisions):
- Use `python app.py` as the single run command documented in `running.md` (keeps startup one command with no required env var export).
- Heatmap cell interaction will use click-to-toggle a details panel (instead of tooltip) for reliable desktop behavior without external JS libraries.

4. Add heatmap interaction to reveal day details (notes/reflection/tags) for filled cells.
   - Scope: server outputs per-day metadata; client-side JS toggles a details panel when clicking a filled cell.
   - Done looks like: clicking a filled day reveals that day’s notes, reflection, and tags.

5. Create templates/static styling for goal, entry forms, dashboard, and heatmap legend/colors.
   - Scope: server-rendered HTML + vanilla CSS/JS only; no frontend framework.
   - Done looks like: all routes render usable desktop pages and heatmap has visible 0-5 intensity distinction.

7. Document single-command local run flow in `running.md`.
   - Scope: include one command to start app plus any one-time prerequisite note (e.g., Python deps install) while keeping runtime invocation single-command.
   - Done looks like: a user can follow `running.md` and start the app with one documented command.
