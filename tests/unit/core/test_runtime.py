from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest

from cutcut.common.clock import FakeClock, SystemClock
from cutcut.common.config import effective_rules, example_site_dir, load_rule_presets, load_site
from cutcut.common.ids import BIRD, RuleId, SourceId
from cutcut.common.store import Store
from cutcut.core.engine import Engine
from cutcut.core.inputs import EngineConfig, SetAuto, SetLock
from cutcut.core.intents import SetPreview, Take
from cutcut.core.runtime import TICK_MS, CoreRuntime, RecordingExecutor


def engine(now_ms: int = 0) -> Engine:
    site = load_site(example_site_dir())
    show = site.shows["samtale"]
    return Engine(
        EngineConfig.from_show(show, effective_rules(show, load_rule_presets())), now_ms=now_ms
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "cutcut.db")
    yield s
    s.close()


def speech(mic: str, talking: bool) -> dict[str, object]:
    other = "M1" if mic == "M2" else "M2"
    frame_on = {"vad": 0.9, "dominance_db": 12, "pause_ms": 0}
    frame_off = {"vad": 0.05, "dominance_db": 0, "pause_ms": 5000}
    return {"mics": {mic: frame_on if talking else frame_off, other: frame_off}}


def run_for(rt: CoreRuntime, clock: FakeClock, ms: int, payload: dict[str, object]) -> None:
    for _ in range(ms // TICK_MS):
        clock.advance(TICK_MS)
        rt.feed_bus("audio.frame", payload)
        rt.tick()


def test_runtime_feeds_bus_messages_and_executes_intents(store: Store) -> None:
    clock = FakeClock()
    ex = RecordingExecutor()
    seen: list[str] = []
    rt = CoreRuntime(engine(), clock, ex, store, on_decision=lambda d: seen.append(d.rule.value))
    run_for(rt, clock, 3000, speech("M2", False))
    run_for(rt, clock, 1500, speech("M2", True))
    assert rt.engine.program == "CU:P2"
    assert SetPreview(SourceId.C2) in ex.intents
    assert Take("cut") in ex.intents
    assert "T2" in seen
    store.flush()
    assert store.count("decisions") == rt.stats.decisions > 0


def test_missing_audio_triggers_S4_through_the_runtime() -> None:
    clock = FakeClock()
    rt = CoreRuntime(engine(), clock, RecordingExecutor())
    for _ in range(100):  # 3 s with no audio frames at all
        clock.advance(TICK_MS)
        rt.tick()
    assert rt.engine.paused
    assert rt.engine.program == BIRD
    assert rt.engine.s4_paused


def test_invalid_bus_payload_is_counted_not_raised() -> None:
    rt = CoreRuntime(engine(), FakeClock(), RecordingExecutor())
    rt.feed_bus("audio.frame", {"mics": {"M9": {"vad": 2}}})
    rt.feed_bus("atem.state", {"program": "nope"})
    assert rt.stats.invalid_messages == 2


def test_executor_crash_does_not_stop_ticking() -> None:
    class Broken:
        def submit(self, intent: object) -> None:
            raise RuntimeError("device bug")

    clock = FakeClock()
    rt = CoreRuntime(engine(), clock, Broken())
    run_for(rt, clock, 2000, speech("M2", True))  # would submit intents → raises inside
    assert rt.stats.ticks > 0


def test_settings_survive_a_restart_and_engine_waits_before_cutting(store: Store) -> None:
    clock = FakeClock()
    rt = CoreRuntime(engine(), clock, RecordingExecutor(), store)
    rt.command(SetAuto(on=False))
    rt.command(SetLock(on=True))
    run_for(rt, clock, 1200, speech("M2", False))
    store.flush()

    # "core" restarts: new engine, new monotonic clock origin, same database
    clock2 = FakeClock()
    rt2 = CoreRuntime(engine(), clock2, RecordingExecutor(), store)
    assert rt2.engine.auto is False
    assert rt2.engine.lock is True
    rt2.command(SetAuto(on=True))
    rt2.command(SetLock(on=False))
    run_for(rt2, clock2, 4000, speech("M2", True))
    assert rt2.engine.program == BIRD  # 5 s calm after restart (manual_quiet_s)
    run_for(rt2, clock2, 2000, speech("M2", True))
    assert rt2.engine.program == "CU:P2"


async def test_run_loop_ticks_in_real_time_and_stops() -> None:
    rt = CoreRuntime(engine(), SystemClock(), RecordingExecutor())
    task = asyncio.create_task(rt.run())
    await asyncio.sleep(0.35)
    rt.stop()
    await asyncio.wait_for(task, timeout=1)
    assert 8 <= rt.stats.ticks <= 14  # ~30 ms ticks
    assert rt.stats.max_step_ms < 10


def test_s4_rule_is_logged_with_rule_id(caplog: pytest.LogCaptureFixture) -> None:
    clock = FakeClock()
    rt = CoreRuntime(engine(), clock, RecordingExecutor())
    with caplog.at_level("INFO"):
        for _ in range(80):
            clock.advance(TICK_MS)
            rt.tick()
    assert any(getattr(r, "rule", None) == RuleId.S4.value for r in caplog.records)
