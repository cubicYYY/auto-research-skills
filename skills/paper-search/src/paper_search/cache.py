from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

from paper_search.models import Paper

DEFAULT_TTL_SECONDS = 30 * 24 * 3600


def default_cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "paper-search" / "resolved.sqlite"


class ResolvedCache:
    """SQLite cache for resolved DOI/arXiv metadata (used by the GitHub source)."""

    def __init__(self, path: Optional[Path] = None, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.path = path or default_cache_path()
        self.ttl = ttl_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS resolved ("
            "key TEXT PRIMARY KEY, "
            "payload TEXT NOT NULL, "
            "ts INTEGER NOT NULL)"
        )
        self._conn.commit()

    def get(self, key: str) -> Optional[Paper]:
        row = self._conn.execute(
            "SELECT payload, ts FROM resolved WHERE key = ?", (key,)
        ).fetchone()
        if not row:
            return None
        payload, ts = row
        if time.time() - ts > self.ttl:
            return None
        try:
            return Paper.model_validate_json(payload)
        except Exception:
            return None

    def put(self, key: str, paper: Paper) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO resolved (key, payload, ts) VALUES (?, ?, ?)",
            (key, paper.model_dump_json(), int(time.time())),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
