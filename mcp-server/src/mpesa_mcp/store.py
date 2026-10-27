"""SQLite store for sent requests (idempotency) and received callbacks (results).

One database file per server instance. The callback receiver thread and the
MCP event loop both use it, so every operation takes a lock.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Request lifecycle. Only FAILED may be re-sent under the same idempotency key:
# ACCEPTED and UNKNOWN might still complete, SUCCESS already did.
ACCEPTED, SUCCESS, FAILED, UNKNOWN = "ACCEPTED", "SUCCESS", "FAILED", "UNKNOWN"
OPEN_STATUSES = (ACCEPTED, UNKNOWN)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    key        TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    status     TEXT NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 1,
    response   TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS request_ids (
    id  TEXT PRIMARY KEY,
    key TEXT NOT NULL REFERENCES requests(key)
);
CREATE TABLE IF NOT EXISTS results (
    rowid       INTEGER PRIMARY KEY,
    corr_id     TEXT NOT NULL,
    status      TEXT NOT NULL,
    parsed      TEXT NOT NULL,
    received_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS results_corr ON results(corr_id);
"""


@dataclass
class RequestRecord:
    key: str
    kind: str
    status: str
    attempts: int
    response: dict[str, Any]
    ids: list[str]


class Store:
    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Requests
    # ------------------------------------------------------------------ #

    def get_request(self, key_or_id: str) -> RequestRecord | None:
        with self._lock:
            row = self._db.execute(
                "SELECT key, kind, status, attempts, response FROM requests WHERE key = ? "
                "UNION SELECT r.key, r.kind, r.status, r.attempts, r.response FROM requests r "
                "JOIN request_ids i ON i.key = r.key WHERE i.id = ?",
                (key_or_id, key_or_id),
            ).fetchone()
            if not row:
                return None
            ids = [r[0] for r in self._db.execute("SELECT id FROM request_ids WHERE key = ?", (row[0],))]
        return RequestRecord(row[0], row[1], row[2], row[3], json.loads(row[4] or "{}"), ids)

    def save_request(self, key: str, kind: str, status: str, response: Any, ids: list[str]) -> None:
        now = time.time()
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO requests(key, kind, status, response, created_at, updated_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET status=excluded.status, response=excluded.response, "
                "attempts=attempts+1, updated_at=excluded.updated_at",
                (key, kind, status, json.dumps(response, default=str), now, now),
            )
            for corr in filter(None, ids):
                self._db.execute("INSERT OR REPLACE INTO request_ids(id, key) VALUES (?, ?)", (str(corr), key))

    # ------------------------------------------------------------------ #
    # Results
    # ------------------------------------------------------------------ #

    def add_result(self, corr_ids: list[str], status: str, parsed: dict[str, Any]) -> None:
        """Record a callback and move any matching open request to its final status."""
        now = time.time()
        blob = json.dumps(parsed, default=str)
        with self._lock, self._db:
            for corr in {str(c) for c in corr_ids if c}:
                self._db.execute(
                    "INSERT INTO results(corr_id, status, parsed, received_at) VALUES (?,?,?,?)",
                    (corr, status, blob, now),
                )
                self._db.execute(
                    "UPDATE requests SET status = ?, updated_at = ? "
                    f"WHERE status IN ({','.join('?' * len(OPEN_STATUSES))}) "
                    "AND key IN (SELECT key FROM request_ids WHERE id = ?)",
                    (status, now, *OPEN_STATUSES, corr),
                )

    def latest_result(self, ids: list[str]) -> tuple[str, dict[str, Any]] | None:
        ids = [str(i) for i in ids if i]
        if not ids:
            return None
        with self._lock:
            row = self._db.execute(
                f"SELECT status, parsed FROM results WHERE corr_id IN ({','.join('?' * len(ids))}) "
                "ORDER BY rowid DESC LIMIT 1",
                ids,
            ).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def results_after(self, rowid: int = 0, limit: int = 50) -> list[tuple[int, str, str, dict[str, Any]]]:
        """Callbacks received after rowid, oldest first: (rowid, corr_id, status, parsed). For live logs."""
        with self._lock:
            rows = self._db.execute(
                "SELECT rowid, corr_id, status, parsed FROM results WHERE rowid > ? ORDER BY rowid LIMIT ?",
                (rowid, limit),
            ).fetchall()
        return [(r[0], r[1], r[2], json.loads(r[3])) for r in rows]
