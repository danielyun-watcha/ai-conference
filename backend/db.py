"""SQLite state store for accepted-papers release tracking.

One row per monitored conference. The monitor flips `released` from 0 to 1
exactly once per conference and records `detected_at`; the Slack notifier only
fires on that transition.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator, Optional

from backend.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS releases (
    conference_id     TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    year              INTEGER NOT NULL,
    url               TEXT NOT NULL,
    released          INTEGER NOT NULL DEFAULT 0,
    detected_at       TEXT,
    last_checked_at   TEXT,
    last_status_code  INTEGER,
    last_error        TEXT
);
"""


@dataclass
class ReleaseRow:
    conference_id: str
    title: str
    year: int
    url: str
    released: bool
    detected_at: Optional[str]
    last_checked_at: Optional[str]
    last_status_code: Optional[int]
    last_error: Optional[str]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_release(row: sqlite3.Row) -> ReleaseRow:
    return ReleaseRow(
        conference_id=row["conference_id"],
        title=row["title"],
        year=row["year"],
        url=row["url"],
        released=bool(row["released"]),
        detected_at=row["detected_at"],
        last_checked_at=row["last_checked_at"],
        last_status_code=row["last_status_code"],
        last_error=row["last_error"],
    )


def get(conference_id: str) -> Optional[ReleaseRow]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM releases WHERE conference_id = ?",
            (conference_id,),
        ).fetchone()
    return _row_to_release(row) if row else None


def list_all() -> list[ReleaseRow]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM releases ORDER BY released DESC, year DESC, title ASC"
        ).fetchall()
    return [_row_to_release(r) for r in rows]


def upsert_check_result(
    conference_id: str,
    title: str,
    year: int,
    url: str,
    released_now: bool,
    status_code: Optional[int],
    error: Optional[str],
) -> tuple[bool, ReleaseRow]:
    """Insert or update a monitor row.

    Returns (newly_released, row). newly_released is True only on the first
    transition from not-released to released — the caller uses this to decide
    whether to fire the Slack webhook.
    """
    now = _now()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT * FROM releases WHERE conference_id = ?",
            (conference_id,),
        ).fetchone()

        was_released = bool(existing["released"]) if existing else False
        released_flag = 1 if (was_released or released_now) else 0
        detected_at: Optional[str]
        if was_released:
            detected_at = existing["detected_at"]
        elif released_now:
            detected_at = now
        else:
            detected_at = None

        conn.execute(
            """
            INSERT INTO releases (
                conference_id, title, year, url, released,
                detected_at, last_checked_at, last_status_code, last_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(conference_id) DO UPDATE SET
                title            = excluded.title,
                year             = excluded.year,
                url              = excluded.url,
                released         = excluded.released,
                detected_at      = excluded.detected_at,
                last_checked_at  = excluded.last_checked_at,
                last_status_code = excluded.last_status_code,
                last_error       = excluded.last_error
            """,
            (
                conference_id,
                title,
                year,
                url,
                released_flag,
                detected_at,
                now,
                status_code,
                error,
            ),
        )

        row = conn.execute(
            "SELECT * FROM releases WHERE conference_id = ?",
            (conference_id,),
        ).fetchone()

    newly_released = released_now and not was_released
    return newly_released, _row_to_release(row)
