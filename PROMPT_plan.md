# Plan Mode

You are in PLAN mode. Do not write or edit any application code.

## Your task

1. Read `specs/base-system.md` in full.
2. Read the current contents of `IMPLEMENTATION_PLAN.md`. Treat it as
   possibly incomplete or wrong — don't assume it's accurate just because
   it exists. If source code already exists (e.g. `app.py`, `templates/`,
   `tests/`), compare it against both the spec and the plan before deciding
   what's actually missing. Don't assume something is unbuilt without
   checking — search the codebase first.
3. When judging what's incomplete, look specifically for: TODO comments,
   stub/placeholder functions, skipped or failing tests, and code that
   only partially implements an acceptance-criteria item.
4. Produce or update `IMPLEMENTATION_PLAN.md` with a prioritized, numbered
   list of concrete implementation tasks needed to satisfy every item in
   the spec's "Acceptance criteria" section.

## Rules

- Each task should be small enough to implement and test in one sitting
  (roughly: one route, one model, one template, one feature at a time —
  not "build the whole app" as a single task).
- Order tasks by dependency: data models before routes, routes before
  templates that use them, core CRUD before the heatmap view.
- For each task, briefly note what "done" looks like (a quick test or
  manual check), based on the spec's acceptance criteria.
- Do NOT implement anything. Do NOT create app code, only update
  `IMPLEMENTATION_PLAN.md`.
- If the spec is ambiguous about something not already covered in the
  spec's "Decisions" sections, make a reasonable assumption, implement
  that assumption as a task, and note the assumption in the plan.

## Output

Write your plan to `IMPLEMENTATION_PLAN.md` in the repo root. Once the
file is saved, stage and commit it with git (a short, descriptive commit
message, e.g. "plan: update implementation plan"). When the plan is
complete and every acceptance criterion is covered by at least one task,
output exactly: <promise>DONE</promise>
