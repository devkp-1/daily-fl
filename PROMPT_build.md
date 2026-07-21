# Build Mode
 
You are in BUILD mode. Implement real, working code — no stubs or
placeholders.
 
Source: structure adapted from gwincr11/ralph-wiggum-tutorial's
PROMPT_build.md format. Git commit notes (refs/notes/commits) from the original are cut
for time/complexity — see note below.
 
## Your task, in order
 
0. Before doing anything else: read `specs/base-system.md` in full, and
   read the current `IMPLEMENTATION_PLAN.md` in full.
1. Choose the single highest-priority unfinished item from
   `IMPLEMENTATION_PLAN.md`. Before writing any code for it, search the
   existing codebase to confirm it's actually not implemented yet — don't
   assume the plan is accurate; verify.
2. Implement that item completely. No stubs, no placeholders, no
   "TODO: implement later" — if you start a task, finish it in this
   iteration.
3. Run the tests relevant to the code you just touched. If functionality
   the spec requires is still missing, add it now rather than leaving it
   incomplete.
4. If you discover a bug, inconsistency, or missing piece unrelated to
   your current task, either fix it now if it's small, or add a note
   about it to `IMPLEMENTATION_PLAN.md` so it isn't lost — do not silently
   ignore it.
5. Single source of truth: don't create parallel/duplicate
   implementations or migration shims. If your change breaks an existing
   test elsewhere, fix that as part of this same increment rather than
   leaving the codebase in a broken state.
6. Once tests pass for this increment:
   - Update `IMPLEMENTATION_PLAN.md`: remove or check off the completed
     item, and add any new findings/follow-up items discovered along the
     way.
   - If you learned something operationally important about running the
     app (a command, a setup step, a gotcha) that isn't already documented,
     add a brief note to `AGENTS.md` (create it if it doesn't exist).
     Keep `AGENTS.md` strictly operational (commands, ports, run
     instructions) — status/progress notes belong in
     `IMPLEMENTATION_PLAN.md`, not here, so this file doesn't bloat.
   - `git add -A`, then commit with a message describing what changed and
     briefly why, then `git push`.
7. If `IMPLEMENTATION_PLAN.md` is getting long with many completed items,
   clean out the finished ones so it stays focused on what's left.