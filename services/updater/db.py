"""PostgreSQL database layer for conference deadlines."""

import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conferences (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER NOT NULL,
    link TEXT,
    file_name TEXT,
    era_rating TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deadlines (
    conference_id TEXT NOT NULL REFERENCES conferences(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    label TEXT,
    date TEXT NOT NULL,
    timezone TEXT DEFAULT 'AoE',
    crawled_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (conference_id, type)
);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    def __init__(self, url: str):
        self._url = url
        self._conn: Optional[psycopg2.extensions.connection] = None

    def connect(self) -> bool:
        try:
            self._conn = psycopg2.connect(self._url)
            self._conn.autocommit = True
            logger.info("DB connected")
            return True
        except Exception as e:
            logger.error("DB connection failed: %s", e)
            return False

    def init_tables(self):
        with self._cursor() as cur:
            cur.execute(_SCHEMA)
        logger.info("DB tables initialized")

    @contextmanager
    def _cursor(self):
        if not self._conn or self._conn.closed:
            self.connect()
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
        finally:
            cur.close()

    def upsert_conference(self, conf_id: str, title: str, year: int,
                          link: str = None, file_name: str = None,
                          era_rating: str = None):
        with self._cursor() as cur:
            cur.execute("""
                INSERT INTO conferences (id, title, year, link, file_name, era_rating, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    year = EXCLUDED.year,
                    link = COALESCE(EXCLUDED.link, conferences.link),
                    file_name = COALESCE(EXCLUDED.file_name, conferences.file_name),
                    era_rating = COALESCE(EXCLUDED.era_rating, conferences.era_rating),
                    updated_at = NOW()
            """, (conf_id, title, year, link, file_name, era_rating))

    def upsert_deadline(self, conference_id: str, dtype: str, label: str,
                        date: str, timezone: str = "AoE"):
        with self._cursor() as cur:
            cur.execute("""
                INSERT INTO deadlines (conference_id, type, label, date, timezone, crawled_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (conference_id, type) DO UPDATE SET
                    label = EXCLUDED.label,
                    date = EXCLUDED.date,
                    timezone = EXCLUDED.timezone,
                    crawled_at = NOW()
            """, (conference_id, dtype, label, date, timezone))

    def get_tbd_conferences(self) -> list[dict]:
        """Get conferences that still have TBD deadlines or no deadlines at all."""
        with self._cursor() as cur:
            cur.execute("""
                SELECT c.id, c.title, c.year, c.link, c.file_name, c.era_rating
                FROM conferences c
                WHERE NOT EXISTS (
                    SELECT 1 FROM deadlines d
                    WHERE d.conference_id = c.id AND d.type IN ('abstract', 'paper')
                )
                ORDER BY c.year, c.title
            """)
            return [dict(r) for r in cur.fetchall()]

    def get_all_conferences(self) -> list[dict]:
        with self._cursor() as cur:
            cur.execute("""
                SELECT c.*,
                    json_agg(
                        json_build_object(
                            'type', d.type,
                            'label', d.label,
                            'date', d.date,
                            'timezone', d.timezone,
                            'crawled_at', d.crawled_at
                        ) ORDER BY d.type
                    ) FILTER (WHERE d.type IS NOT NULL) AS deadlines
                FROM conferences c
                LEFT JOIN deadlines d ON d.conference_id = c.id
                GROUP BY c.id
                ORDER BY c.year DESC, c.title
            """)
            return [dict(r) for r in cur.fetchall()]

    def get_deadline_count(self) -> int:
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM deadlines")
            return cur.fetchone()["count"]

    def get_conference_count(self) -> int:
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM conferences")
            return cur.fetchone()["count"]

    def set_metadata(self, key: str, value: str):
        with self._cursor() as cur:
            cur.execute("""
                INSERT INTO metadata (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (key, value))

    def get_metadata(self, key: str) -> Optional[str]:
        with self._cursor() as cur:
            cur.execute("SELECT value FROM metadata WHERE key = %s", (key,))
            row = cur.fetchone()
            return row["value"] if row else None
