from __future__ import annotations

import json
import logging
import queue
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

from cutcut.common.models.decision import Decision
from cutcut.common.models.session import Session

log = logging.getLogger(__name__)

SCHEMA_VERSION: Final = 1

# Each entry upgrades the schema from index to index + 1. Never edit an existing entry;
# append a new one (spec 12.3).
MIGRATIONS: Final[tuple[str, ...]] = (
    """
    CREATE TABLE sessions (
        session_id   TEXT PRIMARY KEY,
        username     TEXT NOT NULL,
        display_name TEXT NOT NULL,
        started_at   TEXT NOT NULL,
        ended_at     TEXT,
        data         TEXT NOT NULL
    );
    CREATE INDEX sessions_started ON sessions(started_at);
    CREATE TABLE decisions (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        ts             TEXT NOT NULL,
        mono_ms        INTEGER NOT NULL,
        correlation_id TEXT NOT NULL,
        mode           TEXT NOT NULL,
        action         TEXT NOT NULL,
        shot           TEXT NOT NULL,
        rule           TEXT NOT NULL,
        shadow         INTEGER NOT NULL,
        data           TEXT NOT NULL
    );
    CREATE INDEX decisions_ts ON decisions(ts);
    CREATE TABLE audit (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        ts     TEXT NOT NULL,
        role   TEXT NOT NULL,
        actor  TEXT NOT NULL,
        action TEXT NOT NULL,
        detail TEXT NOT NULL
    );
    CREATE INDEX audit_ts ON audit(ts);
    CREATE TABLE config_versions (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        kind     TEXT NOT NULL,
        key      TEXT NOT NULL,
        version  INTEGER NOT NULL,
        saved_at TEXT NOT NULL,
        data     TEXT NOT NULL,
        UNIQUE (kind, key, version)
    );
    CREATE TABLE alerts (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        check_id   TEXT NOT NULL,
        level      TEXT NOT NULL,
        message    TEXT NOT NULL,
        started_at TEXT NOT NULL,
        ended_at   TEXT
    );
    CREATE INDEX alerts_open ON alerts(check_id, ended_at);
    CREATE TABLE kv (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
)


@dataclass(frozen=True)
class Retention:
    """Days to keep each kind of data. Sessions: 90 days (spec 12.4, pending Q10)."""

    sessions_days: int = 90
    decisions_days: int = 30
    alerts_days: int = 90
    audit_days: int = 365


@dataclass
class StoreStats:
    written: int = 0
    dropped: int = 0
    errors: int = 0
    last_error: str | None = None


_STOP: Final = object()


class Store:
    def __init__(self, path: Path, queue_size: int = 10_000) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stats = StoreStats()
        self._lock = threading.Lock()  # guards the read connection
        self._read = self._connect()
        self._migrate(self._read)
        self._queue: queue.Queue[object] = queue.Queue(maxsize=queue_size)
        self._writer = threading.Thread(target=self._write_loop, name="store-writer", daemon=True)
        self._writer.start()

    # -- lifecycle ------------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"database {current} is newer than this CutCut understands ({SCHEMA_VERSION})"
            )
        for version in range(current, SCHEMA_VERSION):
            with conn:
                conn.executescript(MIGRATIONS[version])
                conn.execute(f"PRAGMA user_version={version + 1}")

    def close(self, timeout: float = 5.0) -> None:
        self._queue.put(_STOP)
        self._writer.join(timeout)
        with self._lock:
            self._read.close()

    def flush(self, timeout: float = 5.0) -> None:
        """Wait until all queued writes are done (used by tests and at shutdown)."""
        done = threading.Event()
        self._queue.put(done)
        done.wait(timeout)

    # -- writer ---------------------------------------------------------------------------

    def _write_loop(self) -> None:
        conn = self._connect()
        try:
            while True:
                item = self._queue.get()
                if item is _STOP:
                    return
                if isinstance(item, threading.Event):
                    item.set()
                    continue
                if not isinstance(item, tuple):
                    continue
                sql: str = item[0]
                params: tuple[Any, ...] = item[1]
                try:
                    with conn:
                        conn.execute(sql, params)
                    self.stats.written += 1
                except sqlite3.Error as exc:
                    self.stats.errors += 1
                    self.stats.last_error = str(exc)
                    log.warning("store write failed: %s", exc)
        finally:
            conn.close()

    def _enqueue(self, sql: str, params: tuple[Any, ...]) -> bool:
        try:
            self._queue.put_nowait((sql, params))
        except queue.Full:
            self.stats.dropped += 1
            return False
        return True

    # -- writes (non-blocking) -----------------------------------------------------------

    def add_decision(self, d: Decision) -> bool:
        return self._enqueue(
            "INSERT INTO decisions (ts, mono_ms, correlation_id, mode, action, shot, rule,"
            " shadow, data) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                d.ts.isoformat(),
                d.mono_ms,
                d.correlation_id,
                d.mode.value,
                d.action,
                d.shot,
                d.rule.value,
                int(d.shadow),
                d.model_dump_json(),
            ),
        )

    def upsert_session(self, s: Session, started_at: datetime, ended_at: datetime | None) -> bool:
        return self._enqueue(
            "INSERT INTO sessions (session_id, username, display_name, started_at, ended_at, data)"
            " VALUES (?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET"
            " ended_at=excluded.ended_at, data=excluded.data",
            (
                s.session_id,
                s.user.username,
                s.user.display_name,
                started_at.isoformat(),
                ended_at.isoformat() if ended_at else None,
                s.model_dump_json(),
            ),
        )

    def audit(self, ts: datetime, role: str, actor: str, action: str, **detail: Any) -> bool:
        return self._enqueue(
            "INSERT INTO audit (ts, role, actor, action, detail) VALUES (?,?,?,?,?)",
            (ts.isoformat(), role, actor, action, json.dumps(detail, ensure_ascii=False)),
        )

    def save_config_version(
        self, kind: str, key: str, version: int, saved_at: datetime, data: dict[str, Any]
    ) -> bool:
        return self._enqueue(
            "INSERT OR REPLACE INTO config_versions (kind, key, version, saved_at, data)"
            " VALUES (?,?,?,?,?)",
            (kind, key, version, saved_at.isoformat(), json.dumps(data, ensure_ascii=False)),
        )

    def open_alert(self, check_id: str, level: str, message: str, ts: datetime) -> bool:
        return self._enqueue(
            "INSERT INTO alerts (check_id, level, message, started_at) VALUES (?,?,?,?)",
            (check_id, level, message, ts.isoformat()),
        )

    def close_alert(self, check_id: str, ts: datetime) -> bool:
        return self._enqueue(
            "UPDATE alerts SET ended_at=? WHERE check_id=? AND ended_at IS NULL",
            (ts.isoformat(), check_id),
        )

    def put_kv(self, key: str, value: Any, ts: datetime) -> bool:
        return self._enqueue(
            "INSERT INTO kv (key, value, updated_at) VALUES (?,?,?) ON CONFLICT(key)"
            " DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, json.dumps(value, ensure_ascii=False, default=str), ts.isoformat()),
        )

    def purge(self, now: datetime, retention: Retention | None = None) -> bool:
        retention = retention or Retention()

        def cutoff(days: int) -> str:
            return (now - timedelta(days=days)).isoformat()

        ok = True
        for sql, days in (
            ("DELETE FROM decisions WHERE ts < ?", retention.decisions_days),
            ("DELETE FROM sessions WHERE started_at < ?", retention.sessions_days),
            (
                "DELETE FROM alerts WHERE ended_at IS NOT NULL AND ended_at < ?",
                retention.alerts_days,
            ),
            ("DELETE FROM audit WHERE ts < ?", retention.audit_days),
        ):
            ok = self._enqueue(sql, (cutoff(days),)) and ok
        return ok

    # -- reads (blocking; call via asyncio.to_thread from the event loop) -----------------

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._read.execute(sql, params))

    def get_kv(self, key: str) -> Any | None:
        rows = self._query("SELECT value FROM kv WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else None

    def decisions_since(self, since: datetime, limit: int = 1000) -> list[Decision]:
        rows = self._query(
            "SELECT data FROM decisions WHERE ts >= ? ORDER BY id LIMIT ?",
            (since.isoformat(), limit),
        )
        return [Decision.model_validate_json(r["data"]) for r in rows]

    def latest_config(self, kind: str, key: str) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT data FROM config_versions WHERE kind=? AND key=? ORDER BY version DESC LIMIT 1",
            (kind, key),
        )
        result: dict[str, Any] | None = json.loads(rows[0]["data"]) if rows else None
        return result

    def open_alerts(self) -> list[dict[str, Any]]:
        rows = self._query("SELECT * FROM alerts WHERE ended_at IS NULL ORDER BY id")
        return [dict(r) for r in rows]

    def count(self, table: str) -> int:
        if table not in {"sessions", "decisions", "audit", "config_versions", "alerts", "kv"}:
            raise ValueError(table)
        return int(self._query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"])  # noqa: S608

    def integrity_ok(self) -> bool:
        return bool(self._query("PRAGMA integrity_check")[0][0] == "ok")
