"""Properties that must hold for any conversation (I2, I3, S1, S3, H2) and engine speed."""

from __future__ import annotations

import itertools
import statistics
import time

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cutcut.common.ids import CameraId, RuleId
from cutcut.core.engine import StepResult
from cutcut.core.inputs import Inputs
from tests.rules.harness import WARMUP_MS, Harness

Segment = tuple[int | None, int, float, bool, int | None]
segment = st.tuples(
    st.one_of(st.none(), st.integers(0, 3)),  # who talks (None = silence)
    st.integers(100, 5000),  # how long
    st.floats(4, 20),  # dominance
    st.booleans(),  # falling pitch at the end
    st.one_of(st.none(), st.integers(1, 4)),  # camera that starts moving
)
conversation = st.lists(segment, min_size=3, max_size=25)
EXEMPT_H2 = {RuleId.H4, RuleId.MANUAL, RuleId.S4}


def play(participants: int, segments: list[Segment], preset: str = "standard") -> Harness:
    h = Harness(participants=participants, preset=preset)
    h.run(WARMUP_MS)
    pids = [p.id.value for p in h.show.participants]
    for who, ms, dom, falling, moving in segments:
        for pid in pids:
            h.stop(pid, pitch_falling=falling)
        if who is not None and who < len(pids):
            h.talk(pids[who], dominance_db=dom)
        h.moving = {CameraId(f"C{moving}")} if moving else set()
        h.run(ms)
    return h


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.integers(1, 4), conversation, st.sampled_from(["rolig", "standard", "energisk"]))
def test_invariants_hold_for_any_conversation(
    participants: int, segments: list[Segment], preset: str
) -> None:
    h = play(participants, segments, preset)
    times = h.cut_times()
    # S3: never more than one cut per second
    assert all(b - a >= 1000 for a, b in itertools.pairwise(times)), times
    # S1: never cut to a camera that is moving
    assert h.violations == []
    # H2: no automatic return to the previous shot within H2 (except H4 returns, overrides)
    cuts = h.cuts()
    for prev, cur, nxt in zip(cuts, cuts[1:], cuts[2:], strict=False):
        if nxt.shot == prev.shot and nxt.rule not in EXEMPT_H2:
            assert nxt.mono_ms - cur.mono_ms >= h.rules.H2_no_return_s * 1000 - 30, (prev, cur, nxt)


@settings(max_examples=20, deadline=None)
@given(st.integers(1, 4), conversation)
def test_engine_is_deterministic(participants: int, segments: list[Segment]) -> None:
    """I3: the same input always gives the same decisions."""
    a = play(participants, segments)
    b = play(participants, segments)
    assert [d.model_dump() for d in a.decisions] == [d.model_dump() for d in b.decisions]
    assert a.intents == b.intents


def test_step_is_fast_enough() -> None:
    """Budget: well under the 30 ms tick and the 150 ms cut deadline (10.4)."""
    h = Harness(participants=4)
    durations: list[float] = []
    original = h.engine.step

    def timed(inp: Inputs) -> StepResult:
        t0 = time.perf_counter()
        result = original(inp)
        durations.append(time.perf_counter() - t0)
        return result

    h.engine.step = timed  # type: ignore[method-assign]
    for i in range(60):
        h.stop_all()
        h.talk(("P1", "P2", "P3", "P4")[i % 4])
        if i % 7 == 0:
            h.talk("P2")
        h.run(1000)
    durations.sort()
    assert statistics.mean(durations) < 0.002
    assert durations[int(len(durations) * 0.999)] < 0.010
