# Implementation Plan

All planned items for `specs/base-system.md` and `specs/extension.md` are complete.

## Remaining work

None.

## Completed extension items

1. [x] Weekly-review schema bootstrap (`weekly_summary`, `suggestion`) with constraints/FK behavior.
2. [x] Weekly-review configuration and dependency handling (`ANTHROPIC_API_KEY`, optional `.env` load, explicit config errors).
3. [x] Weekly-review service logic (context collection, rolling 7-day window, prompt, strict JSON validation, normalized payload).
4. [x] `POST /weekly-review` route with atomic summary/suggestion persistence and rollback on failure.
5. [x] Dashboard updates: manual weekly-review trigger, pending indicator/count, expandable pending suggestion list.
6. [x] `POST /suggestion/<id>/accept` route (pending-only, status transition, date-stamped goal-description append).
7. [x] `POST /suggestion/<id>/reject` route (pending-only, status transition, no goal mutation).
8. [x] Extension-focused tests for route persistence, 1-3 suggestion writes, pending UI indicator, accept/reject behavior, rollback, and missing-key error path.
9. [x] Run/setup docs updated for extension dependencies and `.env` API key configuration.
