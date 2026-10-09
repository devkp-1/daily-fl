from pathlib import Path
import sqlite3


CURRENT_SCHEMA_VERSION = 2


def _get_schema_version(connection: sqlite3.Connection) -> int:
    return connection.execute("PRAGMA user_version").fetchone()[0]


def _set_schema_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute(f"PRAGMA user_version = {version}")


def _create_fresh_schema(connection: sqlite3.Connection) -> None:
    """Used only for brand-new databases - creates the current (v2) schema directly."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS goal (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            target_date TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'paused', 'completed')),
            priority TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high')),
            weekly_target_hours REAL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS entry (
            id INTEGER PRIMARY KEY,
            goal_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            reflection TEXT NOT NULL DEFAULT '',
            engagement INTEGER NOT NULL CHECK (engagement BETWEEN 1 AND 5),
            hours_spent REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (date, goal_id),
            FOREIGN KEY (goal_id) REFERENCES goal (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS entry_tag (
            entry_id INTEGER NOT NULL,
            tag TEXT NOT NULL CHECK (
                tag IN (
                    'focused',
                    'distracted',
                    'blocked',
                    'low-energy',
                    'breakthrough'
                )
            ),
            UNIQUE (entry_id, tag),
            FOREIGN KEY (entry_id) REFERENCES entry (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS weekly_summary (
            id INTEGER PRIMARY KEY,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            assessment TEXT NOT NULL CHECK (assessment IN ('ahead', 'on_track', 'behind')),
            summary_text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS suggestion (
            id INTEGER PRIMARY KEY,
            weekly_summary_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            suggestion_type TEXT NOT NULL DEFAULT 'goal_note'
                CHECK (suggestion_type IN ('goal_note', 'weekly_target_hours')),
            target_goal_id INTEGER,
            proposed_weekly_target_hours REAL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'accepted', 'rejected')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (weekly_summary_id) REFERENCES weekly_summary (id) ON DELETE CASCADE,
            FOREIGN KEY (target_goal_id) REFERENCES goal (id) ON DELETE SET NULL
        );
        """
    )
    connection.execute(
        """
        INSERT INTO goal (id, title, description, target_date, status, priority, weekly_target_hours, updated_at)
        VALUES (1, '', '', NULL, 'active', 'medium', NULL, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO NOTHING
        """
    )
    _set_schema_version(connection, CURRENT_SCHEMA_VERSION)


def _migrate_v0_to_v2(connection: sqlite3.Connection) -> None:
    """
    Rebuilds `goal` and `entry` for existing (pre-multi-goal) databases.
    SQLite's ALTER TABLE can't add CHECK constraints or change UNIQUE
    constraints in place, so this uses the standard SQLite table-rebuild
    pattern: create the new shape, copy data across, drop the old table,
    rename the new one into place. Existing data (goal id=1 and its
    entries) is preserved; new columns default to NULL for pre-existing
    rows rather than fabricating values.
    """
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN")

        # --- Rebuild `goal` first, since `entry` will reference it ---
        connection.execute(
            """
            CREATE TABLE goal_new (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                target_date TEXT,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'paused', 'completed')),
                priority TEXT NOT NULL DEFAULT 'medium'
                    CHECK (priority IN ('low', 'medium', 'high')),
                weekly_target_hours REAL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO goal_new (id, title, description, target_date, status, priority, weekly_target_hours, updated_at)
            SELECT id, title, description, target_date, status, 'medium', NULL, updated_at
            FROM goal
            """
        )
        connection.execute("DROP TABLE goal")
        connection.execute("ALTER TABLE goal_new RENAME TO goal")

        # --- Rebuild `entry`: add goal_id (backfilled to 1) and hours_spent,
        #     change uniqueness from (date) alone to (date, goal_id) ---
        connection.execute(
            """
            CREATE TABLE entry_new (
                id INTEGER PRIMARY KEY,
                goal_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                reflection TEXT NOT NULL DEFAULT '',
                engagement INTEGER NOT NULL CHECK (engagement BETWEEN 1 AND 5),
                hours_spent REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (date, goal_id),
                FOREIGN KEY (goal_id) REFERENCES goal (id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            INSERT INTO entry_new (id, goal_id, date, notes, reflection, engagement, hours_spent, created_at)
            SELECT id, 1, date, notes, reflection, engagement, NULL, created_at
            FROM entry
            """
        )
        connection.execute("DROP TABLE entry")
        connection.execute("ALTER TABLE entry_new RENAME TO entry")

        # --- Extend `suggestion` with the new suggestion-type columns ---
        # entry_tag's FK to entry(id) survives the rename since SQLite
        # resolves FKs by table name, not by a fixed internal reference.
        existing_suggestion_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(suggestion)").fetchall()
        }
        if "suggestion_type" not in existing_suggestion_columns:
            connection.execute(
                "ALTER TABLE suggestion ADD COLUMN suggestion_type TEXT NOT NULL DEFAULT 'goal_note'"
            )
        if "target_goal_id" not in existing_suggestion_columns:
            connection.execute("ALTER TABLE suggestion ADD COLUMN target_goal_id INTEGER")
        if "proposed_weekly_target_hours" not in existing_suggestion_columns:
            connection.execute("ALTER TABLE suggestion ADD COLUMN proposed_weekly_target_hours REAL")

        _set_schema_version(connection, CURRENT_SCHEMA_VERSION)
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def ensure_database(database_path: str) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    try:
        current_version = _get_schema_version(connection)

        if current_version == 0:
            table_count = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'goal'"
            ).fetchone()[0]
            if table_count == 0:
                # Genuinely new database - create the current schema directly.
                _create_fresh_schema(connection)
            else:
                # Pre-existing database from before schema versioning existed.
                _migrate_v0_to_v2(connection)
        elif current_version < CURRENT_SCHEMA_VERSION:
            # Placeholder for future migrations (v2 -> v3, etc.) as the
            # schema continues to evolve.
            raise RuntimeError(
                f"No migration path defined from schema version {current_version} "
                f"to {CURRENT_SCHEMA_VERSION}."
            )

        connection.commit()
    finally:
        connection.close()


def seed_demo_data(database_path: str) -> None:
    from datetime import date, timedelta

    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            UPDATE goal SET title = ?, description = ?, target_date = ?, status = ?, priority = ?, weekly_target_hours = ?
            WHERE id = 1
            """,
            (
                "Try the demo: pick a goal you actually care about",
                "This is sample data so you can see how daily logging and the "
                "heatmap work. Create your own goal any time to replace this.",
                (date.today() + timedelta(days=60)).isoformat(),
                "active",
                "high",
                5.0,
            ),
        )
        sample_entries = [
            (date.today() - timedelta(days=2), "Explored the demo", "Curious how the AI review works", 4, 1.5, ["focused"]),
            (date.today() - timedelta(days=1), "Logged a real day", "Trying to stay consistent", 3, 1.0, ["breakthrough"]),
        ]
        for entry_date, notes, reflection, engagement, hours_spent, tags in sample_entries:
            cursor = connection.execute(
                """
                INSERT INTO entry (goal_id, date, notes, reflection, engagement, hours_spent)
                VALUES (1, ?, ?, ?, ?, ?)
                """,
                (entry_date.isoformat(), notes, reflection, engagement, hours_spent),
            )
            for tag in tags:
                connection.execute(
                    "INSERT INTO entry_tag (entry_id, tag) VALUES (?, ?)",
                    (cursor.lastrowid, tag),
                )
        connection.commit()
    finally:
        connection.close()