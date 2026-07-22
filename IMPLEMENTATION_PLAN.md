# Implementation Plan

Current state check: all `specs/base-system.md` acceptance criteria are already implemented and covered by existing behavior/tests. Remaining work is Step 2 (`specs/extension.md`).

1. [x] Add extension schema bootstrap for weekly review persistence (`db.py`).
   - Implemented `weekly_summary` and `suggestion` tables with required enums/fields, FK from `suggestion.weekly_summary_id`, and safe `CREATE TABLE IF NOT EXISTS` bootstrap behavior for existing DBs.
   - Covered by schema bootstrap tests that verify table creation plus invalid assessment/status and FK constraint failures.

2. [x] Add configuration/loading for AI review dependencies and API key handling.
   - Implemented `weekly_review.py` helper wiring with optional `.env` loading (via `python-dotenv` when installed), strict `ANTHROPIC_API_KEY` lookup, and explicit configuration errors for missing key or missing `anthropic` package.
   - Wired app startup config with `WEEKLY_REVIEW_CLIENT_FACTORY` to keep one canonical weekly-review client construction path.

3. [x] Implement weekly-review service logic (data collection + prompt + response validation).
   - Implemented `generate_weekly_review(...)` in `weekly_review.py`, including DB context collection (goal + full entry history with tags + prior weekly summaries), rolling 7-day window computation, Claude prompt construction with “propose, not decide” guardrails, strict JSON parsing, and normalization/validation of assessment + 1-3 suggestions.
   - Added tests covering normalized payload generation, week-window calculation, prompt context inclusion, and malformed model output rejection.

4. Implement `POST /weekly-review` route and transactional writes.
   - Wire dashboard button trigger to create one `weekly_summary` row plus 1-3 `suggestion` rows (`pending`) in a single transaction, then redirect to `/`.
   - Done looks like: one click produces persisted summary + suggestions for that run; partial writes do not occur on failure.

5. Extend dashboard UI for review trigger + pending suggestion indicator/list.
   - Add “Run weekly review” control and a pending badge/count near goal section; render pending suggestions with accept/reject controls that post to their routes.
   - Done looks like: when pending suggestions exist, indicator appears and suggestion actions are visible on `/`; when none exist, indicator is hidden.
   - Assumption: “expand list” requirement is satisfied with a simple native details/toggle UI (no JS framework).

6. Implement `POST /suggestion/<id>/accept` behavior.
   - For a pending suggestion, mark `accepted` and append suggestion text to goal description with a date-stamped separator.
   - Done looks like: DB shows accepted status and goal description contains appended suggestion text only after explicit accept action.
   - Assumption: accepted/rejected non-pending suggestions return 400 to prevent silent re-processing.

7. Implement `POST /suggestion/<id>/reject` behavior.
   - For a pending suggestion, mark `rejected` with no goal mutation; redirect back to dashboard.
   - Done looks like: DB status changes to rejected and goal description is unchanged.

8. Add extension-focused tests in `tests/test_bootstrap.py` (or split test module if preferred by project style).
   - Add tests for: weekly-review route persistence (Claude client mocked), 1-3 suggestion creation, dashboard pending indicator rendering, accept path updating status + goal description, reject path updating only status, and missing API key error path.
   - Done looks like: test suite passes and explicitly covers extension acceptance criteria without live API calls.

9. Update run/setup docs for extension dependencies and env setup (`running.md`).
   - Document installing added packages, creating `.env` with Claude key, and running the same app start command.
   - Done looks like: a new developer can configure key + dependencies and run weekly review from local app.

## Acceptance criteria coverage map

- `base-system.md` (all items): already satisfied by current implementation; guarded by existing tests and by keeping those tests green while implementing tasks 1-9.
- `extension.md` AC1 (real Claude call + weekly_summary row): tasks 2-4, 8, 9.
- `extension.md` AC2 (1-3 suggestions stored): tasks 3-4, 8.
- `extension.md` AC3 (pending indicator on dashboard): tasks 5, 8.
- `extension.md` AC4 (accept/reject semantics, no auto-apply): tasks 6-7, 8.
- `extension.md` AC5 (API key from `.env`, never hardcoded): tasks 2, 9.
- `extension.md` AC6 (tests for accept/reject + goal append): task 8.
