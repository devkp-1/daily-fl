import tempfile
import unittest
from pathlib import Path
import sqlite3

from app import create_app


class BootstrapTests(unittest.TestCase):
    def test_root_route_and_database_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            response = client.get("/")
            body = response.get_data(as_text=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("Personal Productivity Loop", body)
            self.assertIn("Goal title:", body)
            self.assertIn("Goal description:", body)
            self.assertIn("Goal target date:", body)
            self.assertIn("Goal status: active", body)
            self.assertTrue(db_path.exists())

    def test_bootstrap_creates_default_goal_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            create_app({"TESTING": True, "DATABASE": str(db_path)})

            connection = sqlite3.connect(db_path)
            try:
                goal = connection.execute(
                    "SELECT id, title, description, target_date, status FROM goal WHERE id = 1"
                ).fetchone()
                self.assertIsNotNone(goal)
                self.assertEqual(goal[0], 1)
                self.assertEqual(goal[1], "")
                self.assertEqual(goal[2], "")
                self.assertIsNone(goal[3])
                self.assertEqual(goal[4], "active")
            finally:
                connection.close()

    def test_schema_bootstrap_creates_required_tables_and_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            create_app({"TESTING": True, "DATABASE": str(db_path)})

            connection = sqlite3.connect(db_path)
            try:
                connection.execute("PRAGMA foreign_keys = ON")

                table_rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('goal', 'entry', 'entry_tag')"
                ).fetchall()
                self.assertEqual({row[0] for row in table_rows}, {"goal", "entry", "entry_tag"})

                connection.execute(
                    "INSERT INTO entry (date, notes, reflection, engagement) VALUES (?, ?, ?, ?)",
                    ("2026-01-01", "n", "r", 3),
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO entry (date, notes, reflection, engagement) VALUES (?, ?, ?, ?)",
                        ("2026-01-01", "n2", "r2", 4),
                    )

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO entry (date, notes, reflection, engagement) VALUES (?, ?, ?, ?)",
                        ("2026-01-02", "n", "r", 6),
                    )

                entry_id = connection.execute("SELECT id FROM entry WHERE date = ?", ("2026-01-01",)).fetchone()[0]
                connection.execute(
                    "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                    (entry_id, "focused"),
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                        (entry_id, "focused"),
                    )

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                        (entry_id, "not-a-real-tag"),
                    )

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                        (9999, "blocked"),
                    )

                connection.execute("DELETE FROM entry WHERE id = ?", (entry_id,))
                remaining_tags = connection.execute(
                    "SELECT COUNT(*) FROM entry_tag WHERE entry_id = ?",
                    (entry_id,),
                ).fetchone()[0]
                self.assertEqual(remaining_tags, 0)
            finally:
                connection.close()

    def test_goal_edit_page_renders_existing_goal_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})

            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    """
                    UPDATE goal
                    SET title = ?, description = ?, target_date = ?, status = ?
                    WHERE id = 1
                    """,
                    ("Ship project", "Stay consistent", "2026-12-31", "paused"),
                )
                connection.commit()
            finally:
                connection.close()

            response = app.test_client().get("/goal/edit")
            body = response.get_data(as_text=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("<h1>Edit Goal</h1>", body)
            self.assertIn('value="Ship project"', body)
            self.assertIn("Stay consistent", body)
            self.assertIn('value="2026-12-31"', body)
            self.assertIn('<option value="paused" selected>', body)

    def test_post_goal_updates_row_and_redirects_to_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            response = client.post(
                "/goal",
                data={
                    "title": "Finish sprint",
                    "description": "Focus on core tasks",
                    "target_date": "2026-09-30",
                    "status": "completed",
                },
            )

            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers["Location"].endswith("/"))

            connection = sqlite3.connect(db_path)
            try:
                goal = connection.execute(
                    "SELECT title, description, target_date, status FROM goal WHERE id = 1"
                ).fetchone()
            finally:
                connection.close()

            self.assertEqual(goal, ("Finish sprint", "Focus on core tasks", "2026-09-30", "completed"))

            dashboard = client.get("/").get_data(as_text=True)
            self.assertIn("Goal title: Finish sprint", dashboard)
            self.assertIn("Goal status: completed", dashboard)

    def test_post_goal_rejects_invalid_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            response = client.post(
                "/goal",
                data={
                    "title": "Invalid update",
                    "description": "Should fail",
                    "target_date": "2026-09-30",
                    "status": "not-valid",
                },
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("Invalid goal status.", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
