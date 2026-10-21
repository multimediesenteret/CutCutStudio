from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cutcut.common.ids import Mode, RuleId
from cutcut.common.models import Decision, Session, User
from cutcut.common.store import Retention, Store
from cutcut.common.store.store import SCHEMA_VERSION

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "cutcut.db")
    yield s
    s.close()


def decision(ts: datetime, n: int = 0) -> Decision:
    return Decision(
        ts=ts,
        mono_ms=n,
        mode=Mode.N2,
        action="cut",
        shot="CU:P2",
        rule=RuleId.T2,
        reason="test",
        correlation_id=f"d-{n}",
    )


def test_wal_mode_and_schema_version(store: Store) -> None:
    assert store._read.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert store._read.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_decisions_round_trip(store: Store) -> None:
    for i in range(5):
        assert store.add_decision(decision(NOW + timedelta(seconds=i), i))
    store.flush()
    got = store.decisions_since(NOW + timedelta(seconds=2))
    assert [d.mono_ms for d in got] == [2, 3, 4]
    assert got[0].rule is RuleId.T2


def test_session_upsert_and_kv(store: Store) -> None:
    s = Session(session_id="s1", user=User(username="kanordm", display_name="Kari Nordmann"))
    store.upsert_session(s, NOW, None)
    store.upsert_session(s, NOW, NOW + timedelta(minutes=30))
    store.put_kv("engine_state", {"mode": "N2", "program": "BIRD"}, NOW)
    store.flush()
    assert store.count("sessions") == 1
    assert store.get_kv("engine_state") == {"mode": "N2", "program": "BIRD"}
    assert store.get_kv("missing") is None


def test_alerts_open_and_close(store: Store) -> None:
    store.open_alert("H-AUD-1", "red", "Ingen lyd", NOW)
    store.flush()
    assert [a["check_id"] for a in store.open_alerts()] == ["H-AUD-1"]
    store.close_alert("H-AUD-1", NOW + timedelta(seconds=40))
    store.flush()
    assert store.open_alerts() == []


def test_config_versions_keep_latest(store: Store) -> None:
    for v in (1, 2, 3):
        store.save_config_version("show", "podcast-standard", v, NOW, {"version": v})
    store.flush()
    assert store.latest_config("show", "podcast-standard") == {"version": 3}


def test_purge_respects_retention(store: Store) -> None:
    store.add_decision(decision(NOW - timedelta(days=40)))
    store.add_decision(decision(NOW - timedelta(days=1)))
    store.audit(NOW - timedelta(days=400), "admin", "tech", "set_feature", reactions=True)
    store.audit(NOW, "operator", "tech", "cut", shot="BIRD")
    store.purge(NOW, Retention(decisions_days=30, audit_days=365))
    store.flush()
    assert store.count("decisions") == 1
    assert store.count("audit") == 1


def test_full_queue_drops_instead_of_blocking(tmp_path: Path) -> None:
    s = Store(tmp_path / "q.db", queue_size=1)
    try:
        start = time.monotonic()
        results = [s.add_decision(decision(NOW, i)) for i in range(2000)]
        assert time.monotonic() - start < 1.0  # never blocks the caller
        assert not all(results)
        assert s.stats.dropped > 0
    finally:
        s.close()


def test_newer_database_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "new.db"
    Store(path).close()
    import sqlite3

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version=99")
    conn.close()
    with pytest.raises(RuntimeError, match="newer"):
        Store(path)


@pytest.mark.skipif(not hasattr(signal, "SIGKILL"), reason="needs SIGKILL")
def test_killed_writer_leaves_consistent_database(tmp_path: Path) -> None:
    path = tmp_path / "crash.db"
    script = textwrap.dedent(
        f"""
        from datetime import datetime, UTC
        from pathlib import Path
        from cutcut.common.ids import Mode, RuleId
        from cutcut.common.models import Decision
        from cutcut.common.store import Store
        s = Store(Path({str(path)!r}))
        i = 0
        while True:
            s.add_decision(Decision(ts=datetime.now(UTC), mono_ms=i, mode=Mode.N2, action="cut",
                shot="BIRD", rule=RuleId.T8, reason="x", correlation_id=f"d-{{i}}"))
            i += 1
        """
    )
    proc = subprocess.Popen([sys.executable, "-c", script])  # noqa: S603 - our own script
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            time.sleep(0.2)
            if path.exists() and path.stat().st_size > 50_000:
                break
        os.kill(proc.pid, signal.SIGKILL)
    finally:
        proc.wait(timeout=10)
    s = Store(path)
    try:
        assert s.integrity_ok()
        assert s.count("decisions") > 0
    finally:
        s.close()
