# Base System Spec — Personal Productivity Loop System

## Goal

A local web app for daily discipline logging with a GitHub-style activity
heatmap, tied to a single persistent goal statement. This is Step 1 (base
system) of the assignment. No AI is involved in this step — that comes in
Step 2 (extension).

## Stack

- Backend: Flask (Python)
- DB: SQLite (single file, `app.db`)
- Frontend: server-rendered HTML templates + vanilla JS/CSS (no framework)
- No auth — single-user, local-only app

## Data model

### `goal` table
| field        | type      | notes                                    |
|--------------|-----------|---------------------------------------------|
| id           | int, PK   | always row 1 in v1 — single active plan   |
| title        | string    | short goal/plan name                      |
| description  | text      | longer explanation of the goal            |
| target_date  | date      | when the goal should be achieved by       |
| status       | enum      | active / paused / completed               |
| updated_at   | datetime  |                                            |

### `entry` table
| field       | type          | notes                                        |
|-------------|---------------|-------------------------------------------------|
| id          | int, PK       |                                                |
| date        | date, unique  | one entry per calendar day (single active plan, so no per-goal split needed) |
| notes       | text          | free-form notes about the day                |
| reflection  | text          | how today ties to the current goal            |
| engagement  | int, 1-5      | self-rated effort/consistency for the day    |
| created_at  | datetime      |                                                |

**Future work (post-assignment):** multiple concurrent goals, with entries
linked to a specific goal via a `goal_id` foreign key and uniqueness on
`(date, goal_id)` instead of `date` alone. Deferred for now to keep the
Step 2 weekly-AI-review logic reasoning about one plan at a time.

### `entry_tag` table (many-to-many)
| field     | type    | notes                                     |
|-----------|---------|----------------------------------------------|
| entry_id  | int, FK | references `entry.id`                     |
| tag       | enum    | one of the preset tag values (see below)  |

### Preset tags
A fixed set for v1 (kept small and fixed on purpose, so future querying/
filtering stays simple — no free-form tag creation yet):

- `focused`
- `distracted`
- `blocked`
- `low-energy`
- `breakthrough`

An entry can have zero or more tags. Tags exist mainly for future
searchability/filtering (e.g. "show me all `blocked` days this month") and
as an extra signal for the Step 2 weekly AI reviewer.

## Pages / routes

1. `GET /` — Dashboard
   - Shows current goal (title, description, target date, status), with an
     "edit" link
   - Shows heatmap of last 90 days (color intensity = engagement score,
     0 = no entry that day = empty cell)
   - Link to "Log today"

2. `GET /goal/edit`, `POST /goal` — edit goal title, description,
   target_date, status

3. `GET /entry/new`, `POST /entry` — log a new entry
   - If an entry already exists for today, redirect to edit instead of
     allowing a duplicate
   - Form fields: notes, reflection, engagement (1-5), tags (multi-select
     checkboxes from the preset list)

4. `GET /entry/<date>/edit`, `POST /entry/<date>` — edit an existing entry
   (including changing tags)

## Heatmap behavior

- 90-day grid, 7 rows (days of week) x ~13 columns (weeks), similar to. GitHub or Leetcode's contribution and activity graph
- Each cell = one day. Color scale from empty (no entry) through 5 shades
  based on `engagement` 1-5
- Hovering/clicking a cell shows that day's notes, reflection, and tags
  (tooltip or simple JS toggle — no need for a fancy library)

## Explicitly out of scope for base system

- Weekly AI review — reading the week's entries, assessing ahead/on
  track/behind, and proposing plan tweaks (future work)
- The accept/reject UI for AI-suggested plan changes (also Step 2 — the
  base system only supports *manually* editing the goal via `/goal/edit`)
- Multi-user support / auth
- Tracking multiple goals at once
- Mobile-specific styling — desktop browser is fine

## Acceptance criteria (what "done" means for build stage)

- [ ] Can set/edit the goal (title, description, target date, status) and
      see it on the dashboard
- [ ] Can log a new entry for today via a form, including selecting 0+ tags
- [ ] Cannot create two entries for the same date (edits existing instead)
- [ ] Heatmap renders and visually reflects engagement scores for the last
      90 days, including empty days
- [ ] Clicking/hovering a filled day shows a preview of the day's notes, reflection,
      and tags
- [ ] App runs locally with a single documented command (see running.md)
- [ ] Basic tests exist for entry creation, duplicate-date handling, and
      tag assignment

## Decisions made at specify stage

- Engagement is tracked as **both** a 1-5 number (represented by heatmap color) and
  a set of preset tags (for future searchability + richer signal for the
  Step 2 weekly reviewer). Tags are a fixed enum in this base version, not free-form, to
  keep querying simple.
- Goal is **structured** (title, description, target_date, status) rather
  than freeform text, so the Step 2 AI reviewer has concrete fields
  (especially target_date) to reason progress against.
