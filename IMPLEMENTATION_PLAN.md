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

4. [x] Implement `POST /weekly-review` route and transactional writes.
   - Added `POST /weekly-review` that invokes the configured review generator/client factory, inserts one `weekly_summary` row plus pending `suggestion` rows, and redirects to `/`.
   - Route now rolls back the transaction on any write failure to prevent partial persistence.
   - Added route tests for successful persistence and rollback on mid-transaction failure.

5. [x] Extend dashboard UI for review trigger + pending suggestion indicator/list.
   - Dashboard now includes a `Run weekly review` POST control and queries pending suggestions from the DB.
   - Added pending badge/count and a native `<details>` expandable list rendering each pending suggestion with accept/reject POST controls.
   - Added tests confirming indicator/list/action visibility when pending suggestions exist and hidden state when none exist.

6. [x] Implement `POST /suggestion/<id>/accept` behavior.
   - Added accept route that enforces pending-only processing, marks suggestion `accepted`, and appends the accepted suggestion into goal description with a date-stamped line.
   - Added tests for successful accept (status mutation + goal description append) and 400 on non-pending suggestions.

7. [x] Implement `POST /suggestion/<id>/reject` behavior.
   - Added reject route that enforces pending-only processing, marks suggestion `rejected`, and redirects to dashboard without mutating goal data.
   - Added tests for successful reject behavior and 400 on non-pending suggestions.

8. [x] Add extension-focused tests in `tests/test_bootstrap.py` (or split test module if preferred by project style).
   - Added tests for mocked-Claude weekly review persistence, 1-3 suggestion creation, dashboard pending indicator/list rendering, accept status+goal mutation, reject status-only mutation, rollback guarantees, and missing API key server-error path.
   - Extension behavior is now covered without live API calls.

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
