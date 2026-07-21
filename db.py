from pathlib import Path
import sqlite3


def ensure_database(database_path: str) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS goal (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                target_date TEXT,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'paused', 'completed')),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS entry (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL UNIQUE,
                notes TEXT NOT NULL DEFAULT '',
                reflection TEXT NOT NULL DEFAULT '',
                engagement INTEGER NOT NULL CHECK (engagement BETWEEN 1 AND 5),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
            """
        )
        connection.execute(
            """
            INSERT INTO goal (id, title, description, target_date, status, updated_at)
            VALUES (1, '', '', NULL, 'active', CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO NOTHING
            """
        )
        connection.commit()
    finally:
        connection.close()
