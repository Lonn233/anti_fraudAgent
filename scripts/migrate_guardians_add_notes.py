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
        conn.execute("BEGIN")
        if not _column_exists(conn, "guardians", "monitor_note"):
            conn.execute("ALTER TABLE guardians ADD COLUMN monitor_note VARCHAR(64)")
        if not _column_exists(conn, "guardians", "ward_note"):
            conn.execute("ALTER TABLE guardians ADD COLUMN ward_note VARCHAR(64)")
        conn.execute("COMMIT")
        print("Migration complete: guardians.monitor_note/ward_note added")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
