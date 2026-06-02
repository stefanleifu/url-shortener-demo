from __future__ import annotations

import secrets
import sqlite3
import string
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional


BASE62_ALPHABET = string.ascii_letters + string.digits


@dataclass(frozen=True)
class Link:
    code: str
    long_url: str
    created_at: int
    expires_at: Optional[int]
    visit_count: int

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= int(time.time())


class DuplicateAliasError(ValueError):
    pass


class LinkStore:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS links (
                    code TEXT PRIMARY KEY,
                    long_url TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER,
                    visit_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_expires_at ON links(expires_at)"
            )

    def create(
        self,
        long_url: str,
        *,
        custom_alias: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Link:
        now = int(time.time())
        expires_at = now + ttl_seconds if ttl_seconds else None

        if custom_alias:
            try:
                return self._insert(custom_alias, long_url, now, expires_at)
            except sqlite3.IntegrityError as exc:
                raise DuplicateAliasError(f"Alias already exists: {custom_alias}") from exc

        for _ in range(10):
            code = self.generate_code()
            try:
                return self._insert(code, long_url, now, expires_at)
            except sqlite3.IntegrityError:
                continue

        raise RuntimeError("Unable to generate a unique short code")

    def generate_code(self, length: int = 8) -> str:
        return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))

    def _insert(
        self, code: str, long_url: str, created_at: int, expires_at: Optional[int]
    ) -> Link:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO links (code, long_url, created_at, expires_at, visit_count)
                VALUES (?, ?, ?, ?, 0)
                """,
                (code, long_url, created_at, expires_at),
            )
        return Link(code, long_url, created_at, expires_at, 0)

    def get(self, code: str) -> Optional[Link]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT code, long_url, created_at, expires_at, visit_count
                FROM links
                WHERE code = ?
                """,
                (code,),
            ).fetchone()

        if row is None:
            return None

        return Link(
            code=row["code"],
            long_url=row["long_url"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            visit_count=row["visit_count"],
        )

    def increment_visits(self, code: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE links SET visit_count = visit_count + 1 WHERE code = ?",
                (code,),
            )
