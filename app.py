from pathlib import Path
import sqlite3

from flask import Flask

from db import ensure_database


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(__file__).resolve().parent / "app.db"),
    )

    if test_config:
        app.config.update(test_config)

    ensure_database(app.config["DATABASE"])

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

    @app.get("/")
    def dashboard() -> str:
        goal = get_goal_row()
        target_date = goal["target_date"] or ""
        return (
            "Personal Productivity Loop\n"
            f"Goal title: {goal['title']}\n"
            f"Goal description: {goal['description']}\n"
            f"Goal target date: {target_date}\n"
            f"Goal status: {goal['status']}"
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
