# Implementation Plan (Base System)

Current state check: repository currently contains no Flask app code (`app.py`), no `templates/`, and no `tests/`, so all acceptance-criteria functionality remains to be implemented.

Assumptions (only where spec is still ambiguous outside explicit Decisions):
- Use `python app.py` as the single run command documented in `running.md` (keeps startup one command with no required env var export).
- Heatmap cell interaction will use click-to-toggle a details panel (instead of tooltip) for reliable desktop behavior without external JS libraries.

1. Initialize Flask app skeleton and SQLite connection/bootstrap.
   - Scope: create app entrypoint, DB helper, and startup wiring so app creates/opens `app.db` in repo root.
   - Done looks like: starting the app serves a basic response and creates `app.db` on first run.

2. Implement schema creation for `goal`, `entry`, and `entry_tag` with required constraints.
   - Scope: include `entry.date` UNIQUE, `entry.engagement` constrained to 1-5, `entry_tag` UNIQUE (`entry_id`, `tag`), FK cascade delete, and allowed preset tags.
   - Done looks like: schema init creates all 3 tables with constraints matching spec/review decisions.

3. Add first-run default goal creation (single-row goal behavior).
   - Scope: ensure goal row `id=1` auto-exists with empty/default values and is updated in place thereafter.
   - Done looks like: first dashboard load shows goal fields (even before manual edit) without setup flow.

4. Build goal edit flow (`GET /goal/edit`, `POST /goal`) and persistence.
   - Scope: form for title/description/target_date/status (`active|paused|completed`), POST validation, update row 1, redirect back to dashboard.
   - Done looks like: editing goal persists and dashboard reflects changed values.

5. Implement entry creation flow for today (`GET /entry/new`, `POST /entry`) with tag assignment.
   - Scope: render form fields (notes, reflection, engagement, preset tag checkboxes), accept 0+ tags, save entry + tags for server-local “today”.
   - Done looks like: submitting today’s entry stores entry and selected tags; empty tag selection also succeeds.

6. Enforce duplicate-date handling and edit redirect behavior.
   - Scope: when today’s entry already exists, `/entry/new` and duplicate POST path redirect to `/entry/<today>/edit` instead of inserting a second row.
   - Done looks like: attempting a second entry for the same date never creates duplicate row; user lands on edit page.

7. Implement entry edit flow (`GET /entry/<date>/edit`, `POST /entry/<date>`) with tag replacement.
   - Scope: load existing entry by date, allow updating notes/reflection/engagement, replace tag set to match current checkbox selection.
   - Done looks like: editing today updates fields and tag membership exactly to submitted values.

8. Build dashboard (`GET /`) with goal summary, “Log today” link, and 90-day heatmap data model.
   - Scope: generate Monday-start, 13-column window for last 90 days ending today; map no-entry to 0 and entries to engagement 1-5.
   - Done looks like: dashboard renders full 90-day grid with correct empty/filled intensity classes.

9. Add heatmap interaction to reveal day details (notes/reflection/tags) for filled cells.
   - Scope: server outputs per-day metadata; client-side JS toggles a details panel when clicking a filled cell.
   - Done looks like: clicking a filled day reveals that day’s notes, reflection, and tags.

10. Create templates/static styling for goal, entry forms, dashboard, and heatmap legend/colors.
    - Scope: server-rendered HTML + vanilla CSS/JS only; no frontend framework.
    - Done looks like: all routes render usable desktop pages and heatmap has visible 0-5 intensity distinction.

11. Add basic tests for entry creation, duplicate-date handling, and tag assignment.
    - Scope: Flask test client + isolated test DB covering required acceptance tests; include assertions for tag persistence and uniqueness behavior.
    - Done looks like: test suite includes and passes the three required test categories.

12. Document single-command local run flow in `running.md`.
    - Scope: include one command to start app plus any one-time prerequisite note (e.g., Python deps install) while keeping runtime invocation single-command.
    - Done looks like: a user can follow `running.md` and start the app with one documented command.