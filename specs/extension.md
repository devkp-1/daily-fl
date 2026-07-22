# Extension Spec — Weekly AI Reviewer
 
## Goal
 
Step 2 of the assignment. A weekly AI pass that reads the week's daily
entries, compares them against the current goal, assesses whether user is ahead or on
track or behind, and proposes small suggested edits to the goal that the
user can accept or reject. This is the "propose, not decide" AI review
layer on top of Step 1's base system.
 
Scoped to the minimum needed to be a real, working extension for this
assignment. Daily micro-suggestions and a separate weekly-reflection entry
type are deliberately out of scope here — noted as future work.
 
## Stack additions
 
- `anthropic` Python package (Claude API)
- API key stored in `.env` (already gitignored), loaded via
  `python-dotenv` or `os.environ`
## Data model additions
 
### `weekly_summary` table
| field        | type      | notes                                          |
|--------------|-----------|--------------------------------------------------|
| id           | int, PK   |                                                  |
| week_start   | date      | Monday of the reviewed week                     |
| week_end     | date      | Sunday of the reviewed week                     |
| assessment   | enum      | ahead / on_track / behind                       |
| summary_text | text      | the AI's written synthesis for the week         |
| created_at   | datetime  |                                                  |
 
### `suggestion` table
| field         | type      | notes                                                    |
|---------------|-----------|-------------------------------------------------------------|
| id            | int, PK   |                                                              |
| weekly_summary_id | int, FK | references `weekly_summary.id`                          |
| text          | text      | the suggested goal tweak, in plain language               |
| status        | enum      | pending / accepted / rejected                              |
| created_at    | datetime  |                                                              |
 
## Context sent to the AI
 
On each weekly review run: the current goal (title, description,
target_date, status), the full history of daily entries to date (notes,
reflection, engagement, tags, dates), and all prior `weekly_summary` rows
(so the model can reason about trend, not just this week in isolation).
 
**Known limitation, not solved in v1**: sending the full entry history
every time will not scale indefinitely — cost and eventual context-window
limits will require windowing or summarizing older entries once entry
count grows large. explicitly deffered. 
 
## Trigger mechanism
 
Manual button on the dashboard: "Run weekly review." No scheduling/cron
in v1 — the user clicks it when they're ready to do their week-end check-in.
 
## Routes / behavior
 
1. `POST /weekly-review` — triggers a new review:
   - Determine week window: the 7 days ending on the day this is run
     (rolling window, not calendar-locked, since trigger is manual)
   - Send goal + full entry history + prior weekly summaries to Claude
     with a prompt instructing it to assess ahead/on-track/behind and
     propose 1-3 small, concrete suggested goal tweaks
   - Store the response as a new `weekly_summary` row, plus one `suggestion`
     row per proposed tweak (status `pending`)
   - Redirect to `/` (dashboard)
2. Dashboard (`GET /`) additions:
   - If any `suggestion` rows are `pending`, show a small indicator/icon
     near the goal section (e.g. a badge with the pending count)
   - Clicking it expands the list of pending suggestions, each with an
     accept (✓) and reject (✗) control
3. `POST /suggestion/<id>/accept` — marks the suggestion `accepted` and
   appends its text to the goal's `description` field (simple concatenation
   with a separator, e.g. a new line prefixed with the date) — this is the
   only mechanism by which a suggestion actually changes the goal. Nothing
   auto-applies.
4. `POST /suggestion/<id>/reject` — marks the suggestion `rejected`. No
   further action; it just stops showing as pending.
## AI prompt design principle
 
The reviewer proposes, it does not decide. The prompt sent to Claude must
explicitly instruct it to: assess trend based on effort/engagement and
reflection content (not fact-check truthfulness of entries), avoid a
scolding or falsely reassuring tone, and phrase suggestions as options
the user can take or leave — not directives.
 
## Explicitly out of scope for this step
 
- Daily micro-suggestions per entry (future work)
- A separate weekly-reflection journaling entry type (future work) — v1
  reasons entirely from daily entries already logged
- Scheduled/automatic review triggering (manual button only)
- Editing or deleting past weekly summaries
- Any UI for browsing summary history beyond the current pending
  suggestions (future work)
- **Deliberate week-boundary design, not implemented in v1**: a
  partial-first-week question at goal creation (does the short first
  week count as "week 0," or does the week anchor start immediately on
  the creation day?), and a user-selected weekly review day with a ±24hr
  grace window (button only counts as "on-time" within that window,
  no background scheduler). Real design, worth building later — deferred
  here because it adds meaningful build time (new goal fields, week-
  boundary branching logic, grace-window validation) relative to the time
  available for this assignment. v1 instead uses a simple rolling
  last-7-days window from whenever the button is manually clicked.
## Acceptance criteria
 
- [ ] Clicking "Run weekly review" produces a real Claude API call and
      stores a `weekly_summary` row with a real assessment + summary text
- [ ] 1-3 `suggestion` rows are created from that response
- [ ] Dashboard shows a pending-suggestion indicator when suggestions exist
- [ ] Accepting a suggestion appends its text to the goal description and
      marks it accepted; rejecting marks it rejected; neither auto-applies
      without the user's explicit action
- [ ] API key is read from `.env`, never hardcoded or committed
- [ ] Basic test exists confirming accept/reject correctly updates
      suggestion status and (for accept) goal description
 