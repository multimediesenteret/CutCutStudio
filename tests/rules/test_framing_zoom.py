"""Framing variety F1–F3 and slow zoom Z1–Z3 (spec 5.13, P4).

F: a camera that leaves program and preview gets the other framing (tight/wide) while off air,
must stand still before it can be cut to, and the candidate for the next cut is never moved.
Z: on a speaker that has stood a while, zoom in a little over a long time; stop as soon as
another shot is armed; only on cameras where the show allows it."""

from __future__ import annotations

from dataclasses import replace

from cutcut.common.ids import CameraId, RuleId
from cutcut.common.models.site import CameraLimits
from cutcut.core.intents import FrameCamera, SlowZoom, StopZoom
from cutcut.devices.cameras.base import PTZPosition, ZoomTo
from cutcut.devices.cameras.guarded import GuardedCamera, OnAir
from tests.rules.harness import Harness, started


def turns(h: Harness, n: int, ms: int = 5000) -> None:
    for i in range(n):
        h.stop_all()
        h.talk(("P1", "P2")[i % 2])
        h.run(ms)


def frames(h: Harness) -> list[FrameCamera]:
    return [i for _, i in h.intents if isinstance(i, FrameCamera)]


def with_slow_zoom(h: Harness) -> Harness:
    cams = {k: v.model_copy(update={"slow_zoom": True}) for k, v in h.show.cameras.items()}
    show = h.show.model_copy(update={"cameras": cams})
    h.engine.set_config(replace(h.engine.config, show=show))
    return h


def test_F1_the_next_framing_alternates_while_off_air() -> None:
    h = started(features={"framing_variety": True})
    turns(h, 6)
    c1 = [f.framing for f in frames(h) if f.camera is CameraId.C1]
    assert c1[:3] == ["wide", "tight", "wide"]
    assert all(d.rule is RuleId.F1 for d in h.decisions if "utsnitt" in d.reason)


def test_F1_off_means_no_reframing() -> None:
    h = started()
    turns(h, 6)
    assert frames(h) == []


def test_F2_a_reframed_camera_waits_before_it_can_be_cut_to() -> None:
    h = started(features={"framing_variety": True})
    turns(h, 2)  # P2 on air; C1 was reframed after P1 left
    h.engine.reframe_until[CameraId.C1] = h.now + 5000  # as right after a reframe
    h.stop_all()
    h.talk("P1")
    h.run(1500)
    assert any(d.blocked_by is RuleId.F2 for d in h.waits())
    assert h.program == "CU:P2"


def test_F2_a_camera_that_was_not_reframed_is_not_held() -> None:
    h = started()
    turns(h, 3)
    assert not any(d.blocked_by is RuleId.F2 for d in h.waits())


def test_F3_the_candidate_is_never_moved() -> None:
    h = started(features={"framing_variety": True})
    turns(h, 2)  # P2 on air
    h.stop_all()
    h.talk("P1")
    for _ in range(100):  # until C1 (P1) is the candidate
        h.run(30)
        if h.engine.candidate is not None and h.engine.candidate.shot == "CU:P1":
            break
    assert h.engine.candidate is not None
    before = len(frames(h))
    h.engine._reframe_pending.add(CameraId.C1)
    h.run(60)
    if h.engine.candidate is not None and h.engine.candidate.shot == "CU:P1":
        assert len(frames(h)) == before  # F3: not while it is the candidate


def test_F3_a_camera_that_is_not_the_candidate_is_reframed() -> None:
    h = started(features={"framing_variety": True})
    turns(h, 2)
    assert any(f.camera is CameraId.C1 for f in frames(h))


def test_Z1_a_speaker_who_stands_gets_a_slow_zoom() -> None:
    h = with_slow_zoom(started(features={"slow_zoom": True}))
    h.talk("P1")
    h.run(8000)
    zooms = [i for _, i in h.intents if isinstance(i, SlowZoom)]
    assert zooms
    assert zooms[0].camera is CameraId.C1
    assert zooms[0].amount <= 0.10


def test_Z1_not_before_the_speaker_has_stood_a_while() -> None:
    h = with_slow_zoom(started(features={"slow_zoom": True}))
    h.talk("P1")
    h.run(2500)
    assert not h.intents_of(SlowZoom)


def test_Z2_another_shot_armed_stops_the_zoom() -> None:
    h = with_slow_zoom(started(features={"slow_zoom": True}))
    h.talk("P1")
    h.run(8000)
    assert h.intents_of(SlowZoom)
    h.stop_all()
    h.talk("P2")
    h.run(1500)
    assert h.intents_of(StopZoom)


def test_Z2_the_zoom_runs_while_nothing_else_is_armed() -> None:
    h = with_slow_zoom(started(features={"slow_zoom": True, "bird": False}))
    h.talk("P1")
    h.run(9000)
    assert h.intents_of(SlowZoom)
    assert not h.intents_of(StopZoom)


def test_Z3_only_cameras_the_show_allows() -> None:
    h = started(features={"slow_zoom": True})  # slow_zoom is off per camera in the show
    h.talk("P1")
    h.run(10000)
    assert not h.intents_of(SlowZoom)


def guard(*, ok: bool, zoom: float = 0.4) -> GuardedCamera:
    class Driver:
        id = CameraId.C1

    g = GuardedCamera(
        Driver(),  # type: ignore[arg-type]
        CameraLimits(),
        air=lambda: OnAir(program=frozenset({CameraId.C1}), preview=frozenset()),
        slow_zoom_ok=lambda: ok,
    )
    g.st.position = PTZPosition(pan=0, tilt=0, zoom=zoom)
    return g


def test_Z3_the_guard_lets_only_small_slow_steps_through_on_air() -> None:
    g = guard(ok=True)
    assert g.blocked(ZoomTo(0.41, speed=0.02, slow=True)) is None  # I2's one exception
    assert g.blocked(ZoomTo(0.45, speed=0.02, slow=True)) == "on_program"  # too big a step
    assert g.blocked(ZoomTo(0.39, speed=0.02, slow=True)) == "on_program"  # never out on air
    assert g.blocked(ZoomTo(0.41, speed=0.3, slow=True)) == "on_program"  # too fast
    assert g.blocked(ZoomTo(0.41, speed=0.02)) == "on_program"  # not a slow-zoom step
    assert guard(ok=False).blocked(ZoomTo(0.41, speed=0.02, slow=True)) == "on_program"
