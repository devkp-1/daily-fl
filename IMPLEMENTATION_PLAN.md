# Implementation Plan (Base System)

Completed this increment:
- Heatmap interaction is implemented: filled cells now carry per-day metadata and clicking one reveals notes, reflection, and tags in a dashboard details panel.
- Goal and entry pages now render from dedicated templates with shared static styling, and the dashboard includes a visible 0-5 heatmap legend.

Remaining highest-priority items:
1. Document single-command local run flow in `running.md`.
   - Scope: include one command to start app plus any one-time prerequisite note (e.g., Python deps install) while keeping runtime invocation single-command.
   - Done looks like: a user can follow `running.md` and start the app with one documented command.
