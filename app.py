from pathlib import Path
import sqlite3
from datetime import date, timedelta

from flask import Flask, redirect, render_template, request, url_for

from db import ensure_database


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(__file__).resolve().parent / "app.db"),
    )

    if test_config:
        app.config.update(test_config)

    ensure_database(app.config["DATABASE"])
    allowed_goal_statuses = {"active", "paused", "completed"}
    allowed_entry_tags = (
        "focused",
        "distracted",
        "blocked",
        "low-energy",
        "breakthrough",
    )

    def today_iso() -> str:
        return date.today().isoformat()

    def get_entry_for_date(entry_date: str) -> dict[str, str | int | list[str]] | None:
        connection = sqlite3.connect(app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        try:
            entry_row = connection.execute(
                """
                SELECT id, date, notes, reflection, engagement
                FROM entry
                WHERE date = ?
                """,
                (entry_date,),
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
            "date": str(entry_row["date"]),
            "notes": str(entry_row["notes"]),
            "reflection": str(entry_row["reflection"]),
            "engagement": int(entry_row["engagement"]),
            "tags": [str(row["tag"]) for row in tag_rows],
        }

    def get_goal_row() -> dict[str, str | None]:
        connection = sqlite3.connect(app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """
                SELECT title, description, target_date, status
                FROM goal
                WHERE id = 1
                """
            ).fetchone()
        finally:
            connection.close()

        return dict(row) if row is not None else {
            "title": "",
            "description": "",
            "target_date": None,
            "status": "active",
        }

    def update_goal_row(
        *,
        title: str,
        description: str,
        target_date: str | None,
        status: str,
    ) -> None:
        connection = sqlite3.connect(app.config["DATABASE"])
        try:
            connection.execute(
                """
                UPDATE goal
                SET title = ?, description = ?, target_date = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (title, description, target_date, status),
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
        connection = sqlite3.connect(app.config["DATABASE"])
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

    @app.get("/")
    def dashboard() -> str:
        goal = get_goal_row()
        return render_template(
            "dashboard.html",
            goal_title=goal["title"] or "",
            goal_description=goal["description"] or "",
            goal_target_date=goal["target_date"] or "",
            goal_status=goal["status"] or "active",
            heatmap_columns=get_heatmap_columns(),
        )

    @app.get("/goal/edit")
    def edit_goal() -> str:
        goal = get_goal_row()
        return render_template(
            "goal_edit.html",
            goal_title=goal["title"] or "",
            goal_description=goal["description"] or "",
            goal_target_date=goal["target_date"] or "",
            goal_status=goal["status"] or "active",
            goal_status_options=("active", "paused", "completed"),
        )

    @app.post("/goal")
    def save_goal():
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        target_date_raw = request.form.get("target_date", "").strip()
        status = request.form.get("status", "").strip()

        if status not in allowed_goal_statuses:
            return "Invalid goal status.", 400

        target_date_value: str | None = None
        if target_date_raw:
            try:
                date.fromisoformat(target_date_raw)
            except ValueError:
                return "Invalid target date; expected YYYY-MM-DD.", 400
            target_date_value = target_date_raw

        update_goal_row(
            title=title,
            description=description,
            target_date=target_date_value,
            status=status,
        )
        return redirect(url_for("dashboard"))

    @app.get("/entry/new")
    def new_entry() -> str:
        today = today_iso()
        if get_entry_for_date(today) is not None:
            return redirect(url_for("edit_entry", entry_date=today))

        return render_template(
            "entry_edit.html",
            heading="Log Today's Entry",
            action=url_for("save_entry"),
            entry_date=today,
            notes="",
            reflection="",
            engagement="",
            allowed_entry_tags=allowed_entry_tags,
            selected_tags=set(),
        )

    @app.post("/entry")
    def save_entry():
        today = today_iso()
        if get_entry_for_date(today) is not None:
            return redirect(url_for("edit_entry", entry_date=today))

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

        connection = sqlite3.connect(app.config["DATABASE"])
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.execute(
                """
                INSERT INTO entry (date, notes, reflection, engagement)
                VALUES (?, ?, ?, ?)
                """,
                (today, notes, reflection, engagement),
            )
            entry_id = cursor.lastrowid
            for tag in deduped_tags:
                connection.execute(
                    "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                    (entry_id, tag),
                )
            connection.commit()
        except sqlite3.IntegrityError:
            return redirect(url_for("edit_entry", entry_date=today))
        finally:
            connection.close()

        return redirect(url_for("dashboard"))

    @app.get("/entry/<entry_date>/edit")
    def edit_entry(entry_date: str) -> str:
        if entry_date != today_iso():
            return "Only today's entry can be edited.", 400

        entry = get_entry_for_date(entry_date)
        if entry is None:
            return redirect(url_for("new_entry"))

        return render_template(
            "entry_edit.html",
            heading="Edit Today's Entry",
            action=url_for("update_entry", entry_date=entry_date),
            entry_date=entry_date,
            notes=str(entry["notes"]),
            reflection=str(entry["reflection"]),
            engagement=str(entry["engagement"]),
            allowed_entry_tags=allowed_entry_tags,
            selected_tags=set(entry["tags"]),
        )

    @app.post("/entry/<entry_date>")
    def update_entry(entry_date: str):
        if entry_date != today_iso():
            return "Only today's entry can be edited.", 400

        entry = get_entry_for_date(entry_date)
        if entry is None:
            return redirect(url_for("new_entry"))

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

        connection = sqlite3.connect(app.config["DATABASE"])
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                UPDATE entry
                SET notes = ?, reflection = ?, engagement = ?
                WHERE id = ?
                """,
                (notes, reflection, engagement, entry["id"]),
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

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
