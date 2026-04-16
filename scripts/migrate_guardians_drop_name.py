from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config.settings import settings


def _sqlite_path_from_url(url: str) -> Path:
    if not url.startswith("sqlite:///"):
        raise RuntimeError("This migration script only supports sqlite:/// URLs")
    return Path(url.replace("sqlite:///", "", 1)).resolve()


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def main() -> None:
    db_path = _sqlite_path_from_url(settings.database_url)
    if not db_path.exists():
        raise RuntimeError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        has_name = _column_exists(conn, "guardians", "name")
        if not has_name:
            print("guardians.name already removed, skip.")
            return

        conn.execute("BEGIN")
        conn.execute(
            """
            CREATE TABLE guardians_new (
                id INTEGER NOT NULL PRIMARY KEY,
                monitor_id INTEGER NOT NULL,
                ward_id INTEGER NOT NULL,
                relationship VARCHAR(64),
                created_at DATETIME NOT NULL,
                CONSTRAINT uq_guardian_monitor_ward UNIQUE (monitor_id, ward_id),
                FOREIGN KEY(monitor_id) REFERENCES users (id),
                FOREIGN KEY(ward_id) REFERENCES users (id)
            )
            """
        )
        invalid_count = conn.execute(
            "SELECT COUNT(*) FROM guardians WHERE monitor_id IS NULL OR ward_id IS NULL"
        ).fetchone()[0]

        conn.execute(
            """
            INSERT INTO guardians_new (id, monitor_id, ward_id, relationship, created_at)
            SELECT id, monitor_id, ward_id, relationship, created_at
            FROM guardians
            WHERE monitor_id IS NOT NULL AND ward_id IS NOT NULL
            """
        )
        conn.execute("DROP TABLE guardians")
        conn.execute("ALTER TABLE guardians_new RENAME TO guardians")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_guardians_id ON guardians (id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_guardians_monitor_id ON guardians (monitor_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_guardians_ward_id ON guardians (ward_id)")
        conn.execute("COMMIT")
        print("Migration complete: guardians.name removed")
        if invalid_count:
            print(f"Warning: dropped {invalid_count} invalid guardian rows (NULL monitor_id/ward_id)")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
