import tempfile
import unittest
from pathlib import Path
import sqlite3
from datetime import date, timedelta

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
            self.assertIn('href="/entry/new"', body)
            self.assertTrue(db_path.exists())

    def test_dashboard_renders_13x7_heatmap_with_engagement_intensity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})

            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    "INSERT INTO entry (date, notes, reflection, engagement) VALUES (?, ?, ?, ?)",
                    (date.today().isoformat(), "today note", "today reflection", 5),
                )
                connection.execute(
                    "INSERT INTO entry (date, notes, reflection, engagement) VALUES (?, ?, ?, ?)",
                    ((date.today() - timedelta(days=1)).isoformat(), "yesterday", "previous", 2),
                )
            finally:
                connection.commit()
                connection.close()

            response = app.test_client().get("/")
            body = response.get_data(as_text=True)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(body.count('class="heatmap-column"'), 13)
            self.assertEqual(body.count('class="heatmap-cell intensity-'), 91)
            self.assertIn("intensity-5", body)
            self.assertIn("intensity-2", body)
            self.assertIn(f'data-date="{date.today().isoformat()}"', body)

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

    def test_get_new_entry_page_renders_form_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})

            response = app.test_client().get("/entry/new")
            body = response.get_data(as_text=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("<h1>Log Today's Entry</h1>", body)
            self.assertIn(f"Date: {date.today().isoformat()}", body)
            self.assertIn('name="engagement"', body)
            self.assertIn('value="focused"', body)
            self.assertIn('value="breakthrough"', body)

    def test_post_entry_creates_today_entry_with_selected_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            response = client.post(
                "/entry",
                data={
                    "notes": "Made progress",
                    "reflection": "Aligned with goal",
                    "engagement": "4",
                    "tags": ["focused", "breakthrough"],
                },
            )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers["Location"].endswith("/"))

            connection = sqlite3.connect(db_path)
            try:
                entry = connection.execute(
                    "SELECT id, date, notes, reflection, engagement FROM entry"
                ).fetchone()
                self.assertIsNotNone(entry)
                self.assertEqual(entry[1], date.today().isoformat())
                self.assertEqual(entry[2], "Made progress")
                self.assertEqual(entry[3], "Aligned with goal")
                self.assertEqual(entry[4], 4)

                tags = connection.execute(
                    "SELECT tag FROM entry_tag WHERE entry_id = ? ORDER BY tag",
                    (entry[0],),
                ).fetchall()
            finally:
                connection.close()

            self.assertEqual([row[0] for row in tags], ["breakthrough", "focused"])

    def test_post_entry_allows_empty_tag_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            response = client.post(
                "/entry",
                data={
                    "notes": "No tags today",
                    "reflection": "Still showed up",
                    "engagement": "2",
                },
            )
            self.assertEqual(response.status_code, 302)

            connection = sqlite3.connect(db_path)
            try:
                entry_id = connection.execute("SELECT id FROM entry").fetchone()[0]
                tag_count = connection.execute(
                    "SELECT COUNT(*) FROM entry_tag WHERE entry_id = ?",
                    (entry_id,),
                ).fetchone()[0]
            finally:
                connection.close()

            self.assertEqual(tag_count, 0)

    def test_get_new_entry_redirects_to_edit_when_today_entry_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            first = client.post(
                "/entry",
                data={
                    "notes": "First log",
                    "reflection": "Keep momentum",
                    "engagement": "3",
                    "tags": ["focused"],
                },
            )
            self.assertEqual(first.status_code, 302)

            response = client.get("/entry/new")
            self.assertEqual(response.status_code, 302)
            self.assertTrue(
                response.headers["Location"].endswith(f"/entry/{date.today().isoformat()}/edit")
            )

    def test_post_entry_redirects_duplicate_to_edit_without_second_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            first = client.post(
                "/entry",
                data={
                    "notes": "Original entry",
                    "reflection": "Initial reflection",
                    "engagement": "4",
                    "tags": ["focused", "breakthrough"],
                },
            )
            self.assertEqual(first.status_code, 302)

            duplicate = client.post(
                "/entry",
                data={
                    "notes": "Attempted duplicate",
                    "reflection": "Should not insert",
                    "engagement": "2",
                    "tags": ["blocked"],
                },
            )
            self.assertEqual(duplicate.status_code, 302)
            self.assertTrue(
                duplicate.headers["Location"].endswith(f"/entry/{date.today().isoformat()}/edit")
            )

            connection = sqlite3.connect(db_path)
            try:
                count = connection.execute("SELECT COUNT(*) FROM entry").fetchone()[0]
                original = connection.execute(
                    "SELECT notes, reflection, engagement FROM entry WHERE date = ?",
                    (date.today().isoformat(),),
                ).fetchone()
            finally:
                connection.close()

            self.assertEqual(count, 1)
            self.assertEqual(original, ("Original entry", "Initial reflection", 4))

    def test_get_edit_entry_page_renders_existing_today_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            client.post(
                "/entry",
                data={
                    "notes": "Review day",
                    "reflection": "Stayed aligned",
                    "engagement": "5",
                    "tags": ["breakthrough", "focused"],
                },
            )

            response = client.get(f"/entry/{date.today().isoformat()}/edit")
            body = response.get_data(as_text=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("<h1>Edit Today's Entry</h1>", body)
            self.assertIn("Review day", body)
            self.assertIn("Stayed aligned", body)
            self.assertIn('value="5"', body)
            self.assertIn('value="focused" checked', body)

    def test_post_edit_entry_updates_fields_and_replaces_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})
            client = app.test_client()

            client.post(
                "/entry",
                data={
                    "notes": "Initial",
                    "reflection": "Initial reflection",
                    "engagement": "2",
                    "tags": ["focused", "distracted"],
                },
            )

            response = client.post(
                f"/entry/{date.today().isoformat()}",
                data={
                    "notes": "Updated note",
                    "reflection": "Updated reflection",
                    "engagement": "5",
                    "tags": ["breakthrough"],
                },
            )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers["Location"].endswith("/"))

            connection = sqlite3.connect(db_path)
            try:
                entry = connection.execute(
                    "SELECT id, notes, reflection, engagement FROM entry WHERE date = ?",
                    (date.today().isoformat(),),
                ).fetchone()
                tags = connection.execute(
                    "SELECT tag FROM entry_tag WHERE entry_id = ? ORDER BY tag",
                    (entry[0],),
                ).fetchall()
            finally:
                connection.close()

            self.assertEqual(entry[1:], ("Updated note", "Updated reflection", 5))
            self.assertEqual([row[0] for row in tags], ["breakthrough"])


if __name__ == "__main__":
    unittest.main()
