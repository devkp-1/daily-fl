# Implementation Plan (Base System)

Completed this increment:
- Heatmap interaction is implemented: filled cells now carry per-day metadata and clicking one reveals notes, reflection, and tags in a dashboard details panel.

Remaining highest-priority items:
1. Create templates/static styling for goal, entry forms, dashboard, and heatmap legend/colors.
   - Scope: server-rendered HTML + vanilla CSS/JS only; no frontend framework.
   - Done looks like: all routes render usable desktop pages and heatmap has visible 0-5 intensity distinction with legend.

2. Document single-command local run flow in `running.md`.
   - Scope: include one command to start app plus any one-time prerequisite note (e.g., Python deps install) while keeping runtime invocation single-command.
   - Done looks like: a user can follow `running.md` and start the app with one documented command.
