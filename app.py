from pathlib import Path
import sqlite3
from datetime import date
from html import escape

from flask import Flask, redirect, request, url_for

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

    @app.get("/")
    def dashboard() -> str:
        goal = get_goal_row()
        target_date = goal["target_date"] or ""
        return (
            "<h1>Personal Productivity Loop</h1>"
            f"<p>Goal title: {escape(goal['title'] or '')}</p>"
            f"<p>Goal description: {escape(goal['description'] or '')}</p>"
            f"<p>Goal target date: {escape(target_date)}</p>"
            f"<p>Goal status: {escape(goal['status'] or 'active')}</p>"
            f'<p><a href="{url_for("edit_goal")}">Edit goal</a></p>'
        )

    @app.get("/goal/edit")
    def edit_goal() -> str:
        goal = get_goal_row()
        target_date = goal["target_date"] or ""
        status = goal["status"] or "active"

        options = "".join(
            (
                f'<option value="{candidate}"{" selected" if status == candidate else ""}>'
                f"{candidate.capitalize()}</option>"
            )
            for candidate in ("active", "paused", "completed")
        )

        return (
            "<h1>Edit Goal</h1>"
            '<form method="post" action="/goal">'
            '<label for="title">Title</label><br>'
            f'<input id="title" name="title" type="text" value="{escape(goal["title"] or "")}"><br>'
            '<label for="description">Description</label><br>'
            f'<textarea id="description" name="description">{escape(goal["description"] or "")}</textarea><br>'
            '<label for="target_date">Target date</label><br>'
            f'<input id="target_date" name="target_date" type="date" value="{escape(target_date)}"><br>'
            '<label for="status">Status</label><br>'
            f'<select id="status" name="status">{options}</select><br><br>'
            '<button type="submit">Save goal</button>'
            "</form>"
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

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
