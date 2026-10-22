"""`cutcut hwtest akseptanse`: the 10.4 numbers from a session's decisions and the
feilsøkingsmodus recording."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cutcut.hwtest.acceptance import analyze, load_decisions, load_presses
from tests.unit.api.test_api import Rig

T0 = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)


def cut(ms: int, shot: str, rule: str = "T2", **measures: float) -> dict[str, Any]:
    ts = (T0 + timedelta(milliseconds=ms)).isoformat()
    return {
        "ts": ts,
        "mono_ms": ms,
        "action": "cut",
        "shot": shot,
        "rule": rule,
        "shadow": False,
        "measures": measures,
    }


def steps(decisions: list[dict[str, Any]], presses: list[dict[str, Any]]) -> dict[str, Any]:
    r = analyze(decisions, presses, T0, T0 + timedelta(minutes=10))
    return {s.id: s for s in r.steps}


def test_good_cuts_pass() -> None:
    d = [cut(i * 6000, f"CU:P{1 + i % 2}", cut_point=1, preview_ms=600) for i in range(20)]
    p = [{"label": "take cut", "ms": 40 + i} for i in range(20)]
    s = steps(d, p)
    assert all(x.result == "ok" for x in s.values()), {k: v.summary for k, v in s.items()}
    assert "20 kutt" in s["A1"].summary


def test_slow_cuts_K3_and_short_previews_fail() -> None:
    d = [cut(i * 6000, f"CU:P{1 + i % 2}", cut_point=3, preview_ms=100) for i in range(10)]
    p = [{"label": "take cut", "ms": 400.0} for _ in range(10)]
    s = steps(d, p)
    assert s["A1"].result == "feil"
    assert s["A2"].result == "feil"
    assert s["A3"].result == "feil"


def test_a_quick_cut_back_is_found_but_not_a_manual_one() -> None:
    d = [cut(0, "CU:P1"), cut(5000, "CU:P2"), cut(7000, "CU:P1")]
    assert steps(d, [])["A4"].result == "feil"
    d = [cut(0, "CU:P1"), cut(5000, "CU:P2", rule="MANUAL"), cut(7000, "CU:P1")]
    s = steps(d, [])
    assert s["A4"].result == "ok"
    assert "1 overstyringer" in s["A5"].summary


def test_without_the_recording_A1_asks_for_feilsokingsmodus() -> None:
    s = steps([cut(0, "CU:P1", cut_point=1, preview_ms=500)], [])
    assert s["A1"].result == "hoppet over"
    assert "feilsøkingsmodus" in s["A1"].summary


def test_reads_a_real_session_from_the_database_and_the_recording(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    try:
        studio = rig.sim.studio
        studio.debug.folder = tmp_path / "debug"
        studio.debug._use_thread = False
        start = studio.deps.clock.now()
        rig.client.put("/api/debug", json={"hours": 1})
        rig.client.post("/api/sim/card", json={"card": "04A1B2C3"})
        rig.client.put("/api/session/show", json={"guests": 1, "video": True})
        rig.client.post("/api/recording", json={"action": "start"})
        rig.client.post("/api/sim/conversation", json={"on": True})
        rig.run(90_000)
        studio.debug.event("press", {"label": "take cut", "ms": 35.0})
        rig.client.put("/api/debug", json={"hours": 0})
        rig.store.flush()
        end = studio.deps.clock.now()
        decisions = load_decisions(tmp_path / "cutcut.db", start, end)
        presses = load_presses(tmp_path / "debug", start, end)
        assert [d for d in decisions if d["action"] == "cut"]
        assert presses
        assert presses[0]["ms"] == 35.0
        report = analyze(decisions, presses, start, end)
        assert {s.id for s in report.steps} == {"A1", "A2", "A3", "A4", "A5"}
    finally:
        rig.store.close()
        logging.getLogger().setLevel(logging.INFO)
