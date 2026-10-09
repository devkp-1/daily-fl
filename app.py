import os
import secrets
import uuid
from pathlib import Path
import sqlite3
from datetime import date, timedelta

from flask import Flask, redirect, render_template, request, session, url_for

from db import ensure_database, seed_demo_data
from weekly_review import (
    WeeklyReviewAPIError,
    WeeklyReviewConfigurationError,
    WeeklyReviewResponseError,
    create_anthropic_client,
    demo_weekly_review_generator,
    generate_weekly_review,
)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    demo_mode = os.environ.get("DEMO_MODE", "").strip().lower() in ("1", "true", "yes")

    app.config.from_mapping(
        DATABASE=str(Path(__file__).resolve().parent / "app.db"),
        WEEKLY_REVIEW_CLIENT_FACTORY=create_anthropic_client,
        WEEKLY_REVIEW_GENERATOR=demo_weekly_review_generator if demo_mode else generate_weekly_review,
        DEMO_MODE=demo_mode,
        DEMO_SESSIONS_DIR=str(Path(__file__).resolve().parent / "demo_sessions"),
        SECRET_KEY=os.environ.get("SECRET_KEY", secrets.token_hex(32)),
    )

    if test_config:
        app.config.update(test_config)

    ensure_database(app.config["DATABASE"])
    allowed_goal_statuses = {"active", "paused", "completed"}
    allowed_goal_priorities = {"low", "medium", "high"}
    allowed_entry_tags = (
        "focused",
        "distracted",
        "blocked",
        "low-energy",
        "breakthrough",
    )


    def parse_goal_id(raw: str | None) -> int | None:
        if raw is None:
            return None
        try:
            return int(raw.strip())
        except ValueError:
            return None

    def parse_goal_form(form) -> tuple[dict | None, str | None]:
        title = form.get("title", "").strip()
        if not title:
            return None, "Goal title is required."

        status = form.get("status", "").strip()
        if status not in allowed_goal_statuses:
            return None, "Invalid goal status."

        priority = form.get("priority", "").strip()
        if priority not in allowed_goal_priorities:
            return None, "Invalid goal priority."

        target_date_raw = form.get("target_date", "").strip()
        target_date_value = None
        if target_date_raw:
            try:
                date.fromisoformat(target_date_raw)
            except ValueError:
                return None, "Invalid target date; expected YYYY-MM-DD."
            target_date_value = target_date_raw

        weekly_target_hours, hours_error = parse_hours(
            form.get("weekly_target_hours", ""), "Weekly target hours", 168
        )
        if hours_error:
            return None, hours_error

        return {
            "title": title,
            "description": form.get("description", "").strip(),
            "target_date": target_date_value,
            "status": status,
            "priority": priority,
            "weekly_target_hours": weekly_target_hours,
        }, None
    


    def parse_hours(raw: str, max: float, id: str) -> tuple[float | None, str | None]:
        """Parses user input for request forms. Empty input would be valid i.e. not provided, 
            otherwise return (valid input, No error)"""
        raw = raw.strip()
        if not raw:
            return None, None
        try:
            hours = float(raw)
        except ValueError:
            return None, f"{id} must be a number."
        if not 0 <= hours <= max:
            return None, f"{id} must be a number between 0 and {max}."
        return hours, None


    def today_iso() -> str:
        return date.today().isoformat()

    def resolve_database_path() -> str:
        if not app.config["DEMO_MODE"]:
            return app.config["DATABASE"]

        if "demo_session_id" not in session:
            session["demo_session_id"] = uuid.uuid4().hex

        demo_dir = Path(app.config["DEMO_SESSIONS_DIR"])
        demo_dir.mkdir(parents=True, exist_ok=True)
        demo_db_path = demo_dir / f"{session['demo_session_id']}.db"

        if not demo_db_path.exists():
            ensure_database(str(demo_db_path))
            seed_demo_data(str(demo_db_path))

        return str(demo_db_path)

    def get_entry_for_date(entry_date: str, goal_id: int) -> dict[str, str | int | list[str]] | None:
        connection = sqlite3.connect(resolve_database_path())
        connection.row_factory = sqlite3.Row
        try:
            entry_row = connection.execute(
                """
                SELECT id, goal_id, date, notes, reflection, engagement, hours_spent
                FROM entry
                WHERE date = ? AND goal_id = ?
                """,
                (entry_date, goal_id),
            ).fetchone()
            if entry_row is None:
                return None

            tag_rows = connection.execute(
                """
                SELECT tag
                FROM entry_tag
                WHERE entry_id = ?
                ORDER BY tag
                """,
                (entry_row["id"],),
            ).fetchall()
        finally:
            connection.close()

        return {
            "id": int(entry_row["id"]),
            "goal_id": int(entry_row["goal_id"]),
            "date": str(entry_row["date"]),
            "notes": str(entry_row["notes"]),
            "reflection": str(entry_row["reflection"]),
            "engagement": int(entry_row["engagement"]),
            "hours_spent": entry_row["hours_spent"],
            "tags": [str(row["tag"]) for row in tag_rows],
        }

    def get_goal_row(goal_id: int) -> dict[str, str | None] | None:
        connection = sqlite3.connect(resolve_database_path())
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """
                SELECT id, title, description, target_date, status, priority, weekly_target_hours
                FROM goal
                WHERE id = ?
                """,
                (goal_id,),
            ).fetchone()
        finally:
            connection.close()

        return dict(row) if row is not None else None

    def insert_goal_row(
        *,
        title: str,
        description: str,
        target_date: str | None,
        status: str,
        priority: str,
        weekly_target_hours: float | None
    ) -> int:
        connection = sqlite3.connect(resolve_database_path())
        try:
            cursor = connection.execute(
                """
                INSERT INTO goal(title, description, target_date, status, priority, weekly_target_hours)
                VALUES = (?, ?, ?, ?, ?, ?)
                """,
                (title, description, target_date, status, priority, weekly_target_hours)
            )
            connection.commit()
            return int(cursor.lastrowid)
        finally:
            connection.close()


    def update_goal_row(
        goal_id: int,
        *,
        title: str,
        description: str,
        target_date: str | None,
        status: str,
        priority: str,
        weekly_target_hours: float | None
    ) -> None:
        connection = sqlite3.connect(resolve_database_path())
        try:
            connection.execute(
                """
                UPDATE goal
                SET title = ?, description = ?, target_date = ?, status = ?, priority = ?, 
                    weekly_target_hours. = ? updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, description, target_date, status, priority, weekly_target_hours, goal_id)
            )
            connection.commit()
        finally:
            connection.close()

    def get_heatmap_columns() -> list[list[dict[str, str | int | bool | list[str]]]]:
        today = date.today()
        last_90_start = today - timedelta(days=89)

        # 13 columns x 7 rows, Monday-start, anchored to the week containing today.
        current_week_monday = today - timedelta(days=today.weekday())
        grid_start = current_week_monday - timedelta(weeks=12)
        connection = sqlite3.connect(resolve_database_path())
        connection.row_factory = sqlite3.Row
        try:
            entry_rows = connection.execute(
                """
                SELECT id, date, notes, reflection, engagement
                FROM entry
                WHERE date BETWEEN ? AND ?
                """,
                (last_90_start.isoformat(), today.isoformat()),
            ).fetchall()
            tag_rows = connection.execute(
                """
                SELECT e.date, et.tag
                FROM entry_tag et
                JOIN entry e ON e.id = et.entry_id
                WHERE e.date BETWEEN ? AND ?
                ORDER BY et.tag
                """,
                (last_90_start.isoformat(), today.isoformat()),
            ).fetchall()
        finally:
            connection.close()

        entry_by_date: dict[str, dict[str, str | int | list[str]]] = {
            str(row["date"]): {
                "engagement": int(row["engagement"]),
                "notes": str(row["notes"]),
                "reflection": str(row["reflection"]),
                "tags": [],
            }
            for row in entry_rows
        }
        for row in tag_rows:
            day = str(row["date"])
            if day in entry_by_date:
                entry_by_date[day]["tags"].append(str(row["tag"]))

        columns: list[list[dict[str, str | int | bool | list[str]]]] = []
        for week_offset in range(13):
            week_start = grid_start + timedelta(weeks=week_offset)
            week_days: list[dict[str, str | int | bool | list[str]]] = []
            for day_offset in range(7):
                day_value = week_start + timedelta(days=day_offset)
                day_iso = day_value.isoformat()
                in_last_90 = last_90_start <= day_value <= today
                day_entry = entry_by_date.get(day_iso)
                engagement = int(day_entry["engagement"]) if day_entry is not None and in_last_90 else 0
                week_days.append(
                    {
                        "date": day_iso,
                        "engagement": engagement,
                        "in_last_90": in_last_90,
                        "is_today": day_value == today,
                        "notes": str(day_entry["notes"]) if day_entry is not None else "",
                        "reflection": str(day_entry["reflection"]) if day_entry is not None else "",
                        "tags": list(day_entry["tags"]) if day_entry is not None else [],
                        "has_entry": day_entry is not None and in_last_90,
                    }
                )
            columns.append(week_days)

        return columns

    def get_pending_suggestions() -> list[dict[str, str | int]]:
        connection = sqlite3.connect(resolve_database_path())
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT id, text, created_at
                FROM suggestion
                WHERE status = 'pending'
                ORDER BY created_at, id
                """
            ).fetchall()
        finally:
            connection.close()

        return [
            {
                "id": int(row["id"]),
                "text": str(row["text"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def get_accepted_suggestions() -> list[dict[str, str | int]]:
        connection = sqlite3.connect(resolve_database_path())
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT id, text, created_at
                FROM suggestion
                WHERE status = 'accepted'
                ORDER BY created_at, id
                """
            ).fetchall()
        finally:
            connection.close()

        return [
            {
                "id": int(row["id"]),
                "text": str(row["text"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def get_all_goals() -> list[dict[str, str | int | None]]:
        connection = sqlite3.connect(resolve_database_path())
        connection.row_factory = sqlite3.Row
        #standard sort is lexical, "ORDER BY" assigns number to priority value
        try:
            rows = connection.execute(
                """
                SELECT id, title, description, target_date, status, priority, weekly_target_hours
                FROM goal
                ORDER BY
                    CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    id
                """
            ).fetchall()
        finally:
            connection.close()

        return [dict(row) for row in rows]

    @app.get("/")
    def dashboard() -> str:
        goals = get_all_goals()
        goal = goals[0]
        pending_suggestions = get_pending_suggestions()
        accepted_suggestions = get_accepted_suggestions()
        return render_template(
            "dashboard.html",
            goal_title=goal["title"] or "",
            goal_description=goal["description"] or "",
            goal_target_date=goal["target_date"] or "",
            goal_status=goal["status"] or "active",
            heatmap_columns=get_heatmap_columns(),
            pending_suggestions=pending_suggestions,
            pending_suggestion_count=len(pending_suggestions),
            accepted_suggestions=accepted_suggestions,
            demo_mode=app.config["DEMO_MODE"],
        )

    @app.get("/preview")
    def preview_home():
        import random
        mock_goals = [
            {"name": "Practice 150 LeetCode Problems", "date": "Target: Oct 1"},
            {"name": "Write 500 words daily", "date": "Target: Dec 31"},
        ]
        mock_streaks = [
            {"name": "LeetCode", "day": 34, "total": 150, "forecast": [random.randint(0, 5) for _ in range(14)]},
            {"name": "Writing", "day": 78, "total": 200, "forecast": [random.randint(0, 5) for _ in range(14)]},
        ]
        mock_heatmap = [[random.randint(0, 5) for _ in range(7)] for _ in range(26)]  # ~6 months
        return render_template(
            "home_preview.html",
            today_display=date.today().strftime("%B %d"),
            mock_goals=mock_goals,
            mock_streaks=mock_streaks,
            mock_heatmap=mock_heatmap,
        )

    @app.get("/goal/new")
    def new_goal() -> str:
        return render_template(
            "goal_edit.html",
            heading = "New Goal",
            action=url_for("create_goal"),
            goal_title="",
            goal_description="",
            goal_target_date="",
            goal_status="active",
            goal_priorty="medium",
            goal_weekly_target_hours="",
            goal_status_options=("active", "paused", "completed"),
            goal_priority_options=allowed_goal_priorities
        )

    @app.post("/goal")
    def create_goal():
        values, error = parse_goal_form(request.form)
        if error:
            return error, 400
        insert_goal_row(**values)
        return redirect(url_for("dashboard"))

    @app.get("/goal/<int:goal_id>/edit")
    def edit_goal(goal_id: int) -> str:
        goal = get_goal_row(goal_id)
        if goal is None:
            return "Goal not Found", 404
        return render_template(
                    "goal_edit.html",
                    heading = "Edit Goal",
                    action=url_for("update_goal", goal_id = goal_id),
                    goal_title=goal["title"] or "",
                    goal_description=goal["description"] or "",
                    goal_target_date=goal["target_date"] or "",
                    goal_status=goal["status"],
                    goal_priorty=goal["priority"],
                    goal_weekly_target_hours="" if goal["weekly_target_hours"] is None else goal["weekly_target_hours"],
                    goal_status_options=("active", "paused", "completed"),
                    goal_priority_options=allowed_goal_priorities
                )

    @app.post("/goal/<int:goal_id>")
    def update_goal(goal_id: int):
        if get_goal_row(goal_id) is None:
            return "Goal not found.", 404
        values, error = parse_goal_form(request.form)
        if error:
            return error, 400
        update_goal_row(goal_id, **values)
        return redirect(url_for("dashboard"))

    @app.get("/entry/new")
    def new_entry() -> str:
        goal_id = parse_goal_id(request.args.get("goal_id"))
        if goal_id is None:
            return "A valid goal is requried.", 400
        goal = get_goal_row(goal_id)
        if goal is None:
            return "Goal not found.", 404

        #If there is an existing entry for this particular goal today, then just edit it. Otherwise proceed
        today = today_iso()
        if get_entry_for_date(today, goal_id) is not None:
            return redirect(url_for("edit_entry", entry_date=today, goal_id=goal_id))
    
        return render_template(
            "entry_edit.html",
            heading="Log Today's Entry",
            action=url_for("save_entry"),
            entry_date=today,
            goal_id=goal_id,
            goal_title=goal["title"],
            notes="",
            reflection="",
            engagement="",
            hours_spent="",
            allowed_entry_tags=allowed_entry_tags,
            selected_tags=set(),
        )

    @app.get("/entry/<entry_date>/edit")
    def edit_entry(entry_date: str) -> str:
        goal_id = parse_goal_id(request.args.get("goal_id"))

        if goal_id is None:
            return "Valid goal required.", 400
        goal = get_goal_row("goal_id")
        if goal is None:
            return "Goal not found.", 404

        if entry_date != today_iso():
            return "Only today's entry can be edited.", 400

        entry = get_entry_for_date(entry_date, goal_id)
        if entry is None:
            return redirect(url_for("new_entry", goal_id=goal_id))
        
        return render_template(
            "entry_edit.html",
            heading="Edit Today's Entry",
            action=url_for("update_entry", entry_date=entry_date),
            entry_date=entry_date,
            goal_id=goal_id,
            goal_title=goal["title"],
            notes=str(entry["notes"]),
            reflection=str(entry["reflection"]),
            engagement=str(entry["engagement"]),
            hours_spent="" if entry["hours_spent"] is None else entry["hours_spent"],
            allowed_entry_tags=allowed_entry_tags,
            selected_tags=set(entry["tags"]),
        )

    @app.post("/entry")
    def save_entry():
        goal_id = parse_goal_id(request.form.get("goal_id", "").strip())
        if goal_id is None:
            return "A valid goal is required.", 400

        if get_goal_row(goal_id) is None:
                return "Goal is not found", 404
        
        today = today_iso()
        if get_entry_for_date(today, goal_id) is not None:
            return redirect(url_for("edit_entry", entry_date=today, goal_id = goal_id))

        hours_spent, hours_error = parse_hours(request.form.get("hours_spent", ""), 24, "Hours spent")
        if hours_error:
                return "Hours spent must be a number.", 400
            
        notes = request.form.get("notes", "").strip()
        reflection = request.form.get("reflection", "").strip()
        engagement_raw = request.form.get("engagement", "").strip()
        submitted_tags = request.form.getlist("tags")

        try:
            engagement = int(engagement_raw)
        except ValueError:
            return "Engagement must be an integer between 1 and 5.", 400

        if not 1 <= engagement <= 5:
            return "Engagement must be an integer between 1 and 5.", 400

        deduped_tags: list[str] = []
        for tag in submitted_tags:
            if tag not in allowed_entry_tags:
                return "Invalid entry tag.", 400
            if tag not in deduped_tags:
                deduped_tags.append(tag)

        connection = sqlite3.connect(resolve_database_path())
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.execute(
                """
                INSERT INTO entry (goal_id, date, notes, reflection, engagement, hours_spent)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (goal_id, today, notes, reflection, engagement, hours_spent),
            )
            entry_id = cursor.lastrowid
            for tag in deduped_tags:
                connection.execute(
                    "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                    (entry_id, tag),
                )
            connection.commit()
        except sqlite3.IntegrityError:
            return redirect(url_for("edit_entry", entry_date=today, goal_id= goal_id))
        finally:
            connection.close()

        return redirect(url_for("dashboard"))

    @app.post("/entry/<entry_date>")
    def update_entry(entry_date: str):
        goal_id = parse_goal_id(request.forms.get("goal_id"))
        if goal_id is None:
            return "A valid goal is required", 400
        if get_goal_row(request.forms.get("goal_id")):
            return "Goal not found.", 404
        
        if entry_date != today_iso():
            return "Only today's entry can be edited.", 400

        entry = get_entry_for_date(entry_date)
        if entry is None:
            return redirect(url_for("new_entry"), goal_id = goal_id)

        notes = request.form.get("notes", "").strip()
        reflection = request.form.get("reflection", "").strip()
        engagement_raw = request.form.get("engagement", "").strip()
        submitted_tags = request.form.getlist("tags")

        hours_spent, house_error = parse_hours(request.forms.get("hours_spent", ""), 24, "Hours spent")
        if house_error:
            return house_error, 400

        try:
            engagement = int(engagement_raw)
        except ValueError:
            return "Engagement must be an integer between 1 and 5.", 400

        if not 1 <= engagement <= 5:
            return "Engagement must be an integer between 1 and 5.", 400

        deduped_tags: list[str] = []
        for tag in submitted_tags:
            if tag not in allowed_entry_tags:
                return "Invalid entry tag.", 400
            if tag not in deduped_tags:
                deduped_tags.append(tag)

        connection = sqlite3.connect(resolve_database_path())
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                UPDATE entry
                SET notes = ?, reflection = ?, engagement = ?, hours_spent = ?
                WHERE id = ?
                """,
                (notes, reflection, engagement, hours_spent, entry["id"]),
            )
            connection.execute("DELETE FROM entry_tag WHERE entry_id = ?", (entry["id"],))
            for tag in deduped_tags:
                connection.execute(
                    "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                    (entry["id"], tag),
                )
            connection.commit()
        finally:
            connection.close()

        return redirect(url_for("dashboard"))

    @app.post("/weekly-review")
    def run_weekly_review():
        review_generator = app.config["WEEKLY_REVIEW_GENERATOR"]
        review_client_factory = app.config["WEEKLY_REVIEW_CLIENT_FACTORY"]
        try:
            review_payload = review_generator(
                database_path=resolve_database_path(),
                client_factory=review_client_factory,
            )
        except (WeeklyReviewConfigurationError, WeeklyReviewResponseError) as exc:
            return str(exc), 500
        except WeeklyReviewAPIError as exc:
            return str(exc), 502

        connection = sqlite3.connect(resolve_database_path())
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            summary_cursor = connection.execute(
                """
                INSERT INTO weekly_summary (week_start, week_end, assessment, summary_text)
                VALUES (?, ?, ?, ?)
                """,
                (
                    review_payload["week_start"],
                    review_payload["week_end"],
                    review_payload["assessment"],
                    review_payload["summary_text"],
                ),
            )
            weekly_summary_id = summary_cursor.lastrowid
            for suggestion_text in review_payload["suggestions"]:
                connection.execute(
                    """
                    INSERT INTO suggestion (weekly_summary_id, text, status)
                    VALUES (?, ?, 'pending')
                    """,
                    (weekly_summary_id, suggestion_text),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return redirect(url_for("dashboard"))

    @app.post("/suggestion/<int:suggestion_id>/accept")
    def accept_suggestion(suggestion_id: int):
        connection = sqlite3.connect(resolve_database_path())
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            suggestion_row = connection.execute(
                """
                SELECT id, status
                FROM suggestion
                WHERE id = ?
                """,
                (suggestion_id,),
            ).fetchone()
            if suggestion_row is None:
                return "Suggestion not found.", 404
            if suggestion_row["status"] != "pending":
                return "Suggestion is not pending.", 400

            connection.execute(
                "UPDATE suggestion SET status = 'accepted' WHERE id = ?",
                (suggestion_id,),
            )
            connection.commit()
        finally:
            connection.close()

        return redirect(url_for("dashboard"))

    @app.post("/suggestion/<int:suggestion_id>/reject")
    def reject_suggestion(suggestion_id: int):
        connection = sqlite3.connect(resolve_database_path())
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            suggestion_row = connection.execute(
                """
                SELECT id, status
                FROM suggestion
                WHERE id = ?
                """,
                (suggestion_id,),
            ).fetchone()
            if suggestion_row is None:
                return "Suggestion not found.", 404
            if suggestion_row["status"] != "pending":
                return "Suggestion is not pending.", 400

            connection.execute(
                "UPDATE suggestion SET status = 'rejected' WHERE id = ?",
                (suggestion_id,),
            )
            connection.commit()
        finally:
            connection.close()

        return redirect(url_for("dashboard"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run()