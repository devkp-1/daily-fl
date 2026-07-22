import tempfile
import unittest
from pathlib import Path
import sqlite3
from datetime import date, timedelta
import re
from unittest.mock import patch

from app import create_app
from weekly_review import (
    WeeklyReviewConfigurationError,
    WeeklyReviewResponseError,
    create_anthropic_client,
    generate_weekly_review,
    load_weekly_review_api_key,
)


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

    def test_dashboard_exposes_day_details_metadata_for_filled_cells(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})

            connection = sqlite3.connect(db_path)
            try:
                cursor = connection.execute(
                    "INSERT INTO entry (date, notes, reflection, engagement) VALUES (?, ?, ?, ?)",
                    (date.today().isoformat(), "Detailed notes", "Tied to my goal", 4),
                )
                entry_id = cursor.lastrowid
                connection.execute(
                    "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                    (entry_id, "focused"),
                )
                connection.execute(
                    "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                    (entry_id, "blocked"),
                )
            finally:
                connection.commit()
                connection.close()

            response = app.test_client().get("/")
            body = response.get_data(as_text=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn('id="day-details"', body)
            self.assertIn('id="day-details-notes"', body)
            self.assertIn('data-has-entry="1"', body)
            self.assertIn('data-notes="Detailed notes"', body)
            self.assertIn('data-reflection="Tied to my goal"', body)
            self.assertIn('data-tags="blocked, focused"', body)
            self.assertIn('addEventListener("mouseenter"', body)
            self.assertIn('addEventListener("focus"', body)

    def test_dashboard_ignores_future_entries_in_heatmap_cells(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            app = create_app({"TESTING": True, "DATABASE": str(db_path)})

            future_day = (date.today() + timedelta(days=1)).isoformat()
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    "INSERT INTO entry (date, notes, reflection, engagement) VALUES (?, ?, ?, ?)",
                    (future_day, "future notes", "future reflection", 5),
                )
            finally:
                connection.commit()
                connection.close()

            response = app.test_client().get("/")
            body = response.get_data(as_text=True)

            self.assertEqual(response.status_code, 200)
            self.assertRegex(
                body,
                re.compile(
                    rf'class="heatmap-cell intensity-0[^"]*"[\s\S]*?data-date="{future_day}"[\s\S]*?data-engagement="0"[\s\S]*?data-has-entry="0"',
                ),
            )

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
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name IN ('goal', 'entry', 'entry_tag', 'weekly_summary', 'suggestion')
                    """
                ).fetchall()
                self.assertEqual(
                    {row[0] for row in table_rows},
                    {"goal", "entry", "entry_tag", "weekly_summary", "suggestion"},
                )

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

                summary_cursor = connection.execute(
                    """
                    INSERT INTO weekly_summary (week_start, week_end, assessment, summary_text)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("2026-01-05", "2026-01-11", "on_track", "Solid consistency this week."),
                )
                weekly_summary_id = summary_cursor.lastrowid

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO weekly_summary (week_start, week_end, assessment, summary_text)
                        VALUES (?, ?, ?, ?)
                        """,
                        ("2026-01-12", "2026-01-18", "off_track", "Invalid assessment"),
                    )

                connection.execute(
                    "INSERT INTO suggestion (weekly_summary_id, text) VALUES (?, ?)",
                    (weekly_summary_id, "Reduce scope for one deliverable next week."),
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO suggestion (weekly_summary_id, text, status) VALUES (?, ?, ?)",
                        (weekly_summary_id, "Invalid status proposal", "unknown"),
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO suggestion (weekly_summary_id, text) VALUES (?, ?)",
                        (9999, "Orphan suggestion should fail"),
                    )

                connection.execute("DELETE FROM weekly_summary WHERE id = ?", (weekly_summary_id,))
                remaining_suggestions = connection.execute(
                    "SELECT COUNT(*) FROM suggestion WHERE weekly_summary_id = ?",
                    (weekly_summary_id,),
                ).fetchone()[0]
                self.assertEqual(remaining_suggestions, 0)
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

    def test_load_weekly_review_api_key_raises_clear_error_when_missing(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with patch("weekly_review.importlib.import_module", side_effect=ModuleNotFoundError()):
                with self.assertRaisesRegex(
                    WeeklyReviewConfigurationError,
                    "Weekly review requires ANTHROPIC_API_KEY",
                ):
                    load_weekly_review_api_key()

    def test_load_weekly_review_api_key_reads_environment_value(self) -> None:
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "  test-key  "}, clear=True):
            api_key = load_weekly_review_api_key()

        self.assertEqual(api_key, "test-key")

    def test_create_anthropic_client_raises_clear_error_when_package_missing(self) -> None:
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            with patch("weekly_review.importlib.import_module", side_effect=ModuleNotFoundError()):
                with self.assertRaisesRegex(
                    WeeklyReviewConfigurationError,
                    "requires the anthropic package",
                ):
                    create_anthropic_client()

    def test_create_anthropic_client_uses_key_from_environment(self) -> None:
        class FakeAnthropic:
            def __init__(self, *, api_key: str):
                self.api_key = api_key

        class FakeAnthropicModule:
            Anthropic = FakeAnthropic

        def fake_import_module(name: str):
            if name == "dotenv":
                raise ModuleNotFoundError()
            if name == "anthropic":
                return FakeAnthropicModule
            raise AssertionError(f"Unexpected module import: {name}")

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "live-key"}, clear=True):
            with patch("weekly_review.importlib.import_module", side_effect=fake_import_module):
                client = create_anthropic_client()

        self.assertEqual(client.api_key, "live-key")

    def test_generate_weekly_review_collects_context_and_returns_normalized_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            create_app({"TESTING": True, "DATABASE": str(db_path)})

            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    """
                    UPDATE goal
                    SET title = ?, description = ?, target_date = ?, status = ?
                    WHERE id = 1
                    """,
                    ("Ship launch", "Complete core milestones", "2026-12-31", "active"),
                )
                entry_cursor = connection.execute(
                    "INSERT INTO entry (date, notes, reflection, engagement) VALUES (?, ?, ?, ?)",
                    ("2026-01-10", "Shipped draft", "Strong momentum", 4),
                )
                connection.execute(
                    "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                    (entry_cursor.lastrowid, "focused"),
                )
                connection.execute(
                    """
                    INSERT INTO weekly_summary (week_start, week_end, assessment, summary_text)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("2026-01-01", "2026-01-07", "on_track", "Previous summary"),
                )
                connection.commit()
            finally:
                connection.close()

            captured_prompt: dict[str, str] = {}

            class FakeTextBlock:
                def __init__(self, text: str):
                    self.text = text

            class FakeMessages:
                def create(self, **kwargs):
                    captured_prompt["content"] = kwargs["messages"][0]["content"]
                    return type("Response", (), {"content": [FakeTextBlock(
                        '{"assessment":"ahead","summary_text":"Great follow-through.","suggestions":["Protect deep work blocks.","Trim one lower-priority deliverable."]}'
                    )]})()

            class FakeClient:
                messages = FakeMessages()

            payload = generate_weekly_review(
                database_path=str(db_path),
                client_factory=lambda: FakeClient(),
                run_day=date(2026, 1, 11),
            )

            self.assertEqual(payload["assessment"], "ahead")
            self.assertEqual(payload["week_start"], "2026-01-05")
            self.assertEqual(payload["week_end"], "2026-01-11")
            self.assertEqual(
                payload["suggestions"],
                ["Protect deep work blocks.", "Trim one lower-priority deliverable."],
            )
            self.assertIn("Ship launch", captured_prompt["content"])
            self.assertIn("Shipped draft", captured_prompt["content"])
            self.assertIn("Previous summary", captured_prompt["content"])

    def test_generate_weekly_review_rejects_malformed_model_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_app.db"
            create_app({"TESTING": True, "DATABASE": str(db_path)})

            class FakeTextBlock:
                def __init__(self, text: str):
                    self.text = text

            class FakeMessages:
                def create(self, **kwargs):
                    return type("Response", (), {"content": [FakeTextBlock(
                        '{"assessment":"off_track","summary_text":"Bad enum","suggestions":[]}'
                    )]})()

            class FakeClient:
                messages = FakeMessages()

            with self.assertRaisesRegex(
                WeeklyReviewResponseError,
                "assessment must be one of",
            ):
                generate_weekly_review(
                    database_path=str(db_path),
                    client_factory=lambda: FakeClient(),
                    run_day=date(2026, 1, 11),
                )


if __name__ == "__main__":
    unittest.main()
