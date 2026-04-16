from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config.settings import settings


def _sqlite_path_from_url(url: str) -> Path:
    if not url.startswith("sqlite:///"):
        raise RuntimeError("This migration script only supports sqlite:/// URLs")
    return Path(url.replace("sqlite:///", "", 1)).resolve()


def _has_table(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def main() -> None:
    db_path = _sqlite_path_from_url(settings.database_url)
    if not db_path.exists():
        raise RuntimeError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        if not _has_table(conn, "guardian_link_requests"):
            print("guardian_link_requests table not found, skip.")
            return

        conn.execute("BEGIN")
        conn.execute(
            """
            CREATE TABLE guardian_link_requests_new (
                id INTEGER NOT NULL PRIMARY KEY,
                requester_id INTEGER NOT NULL,
                monitor_id INTEGER NOT NULL,
                ward_id INTEGER NOT NULL,
                name VARCHAR(64) NOT NULL,
                relationship VARCHAR(64),
                status VARCHAR(16) NOT NULL,
                created_at DATETIME NOT NULL,
                processed_at DATETIME,
                FOREIGN KEY(requester_id) REFERENCES users (id),
                FOREIGN KEY(monitor_id) REFERENCES users (id),
                FOREIGN KEY(ward_id) REFERENCES users (id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO guardian_link_requests_new
            (id, requester_id, monitor_id, ward_id, name, relationship, status, created_at, processed_at)
            SELECT id, requester_id, monitor_id, ward_id, name, relationship, status, created_at, processed_at
            FROM guardian_link_requests
            """
        )
        conn.execute("DROP TABLE guardian_link_requests")
        conn.execute("ALTER TABLE guardian_link_requests_new RENAME TO guardian_link_requests")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_guardian_link_requests_id ON guardian_link_requests (id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_guardian_link_requests_requester_id ON guardian_link_requests (requester_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_guardian_link_requests_monitor_id ON guardian_link_requests (monitor_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_guardian_link_requests_ward_id ON guardian_link_requests (ward_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_guardian_link_requests_status ON guardian_link_requests (status)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_guardian_link_requests_created_at ON guardian_link_requests (created_at)")
        conn.execute("COMMIT")
        print("Migration complete: dropped pair-status unique constraint on guardian_link_requests")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
