"""CA-1: GuardedCamera – the on-air guard (I2, PV2), limits, queue and circuit breaker."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cutcut.common.ids import CameraId, SourceId
from cutcut.common.models.site import CameraLimits
from cutcut.core.inputs import AtemReadback
from cutcut.devices.cameras.base import (
    AutoTracking,
    CameraCommand,
    Exposure,
    MoveTo,
    Nudge,
    PTZPosition,
    RecallPreset,
    StorePreset,
    WhiteBalance,
    ZoomTo,
)
from cutcut.devices.cameras.guarded import OPEN_S, GuardedCamera, OnAir, on_air
from cutcut.sim.fake_camera import FakeCamera

CAMS = [CameraId.C1, CameraId.C2, CameraId.C3, CameraId.C4]


@dataclass
class Atem:
    rb: AtemReadback | None = field(
        default_factory=lambda: AtemReadback(program=SourceId.C1, preview=SourceId.C5)
    )

    def air(self) -> OnAir | None:
        return on_air(self.rb, CAMS)


class Clock:
    t = 100.0

    def __call__(self) -> float:
        return self.t


def rig(cam: CameraId = CameraId.C2, **kw: object) -> tuple[GuardedCamera, FakeCamera, Atem]:
    fake = FakeCamera(cam)
    atem = Atem()
    g = GuardedCamera(fake, CameraLimits(), atem.air, **kw)  # type: ignore[arg-type]
    return g, fake, atem


def drain(g: GuardedCamera) -> None:
    async def go() -> None:
        while await g.step():
            pass

    asyncio.run(go())


def test_PV2_a_camera_on_preview_is_not_moved() -> None:
    g, fake, atem = rig()
    atem.rb = AtemReadback(program=SourceId.C1, preview=SourceId.C2)
    assert g.submit(RecallPreset(3)) == "on_preview"
    assert g.submit(WhiteBalance(kelvin=4000)) == "on_preview"
    drain(g)
    assert fake.moved == []
    assert g.st.last_refused == "white_balance: på preview (PV2)"


def test_PV2_can_be_turned_off_but_program_is_always_guarded() -> None:
    g, _fake, atem = rig(guard_preview=False)
    atem.rb = AtemReadback(program=SourceId.C1, preview=SourceId.C2)
    assert g.submit(RecallPreset(3)) == "queued"
    atem.rb = AtemReadback(program=SourceId.C2, preview=SourceId.C1)
    assert g.submit(RecallPreset(4)) == "on_program"


def test_I2_on_program_nothing_that_moves_or_colours_gets_through() -> None:
    g, fake, atem = rig()
    atem.rb = AtemReadback(program=SourceId.C2, preview=SourceId.C1)
    cmds: list[CameraCommand] = [
        RecallPreset(1),
        Nudge(pan=0.2),
        MoveTo(10, 0),
        ZoomTo(0.5),
        WhiteBalance(kelvin=5000),
        Exposure(gain_db=6),
        AutoTracking(on=True),
    ]
    for cmd in cmds:
        assert g.submit(cmd) == "on_program", cmd
    # what does not change the picture is still allowed
    assert g.submit(StorePreset(7)) == "queued"
    assert g.submit(AutoTracking(on=False)) == "queued"  # AT6: off is always safe
    drain(g)
    assert fake.moved == []
    assert fake.received == ["store 7", "tracking False"]


def test_I2_the_atem_cut_after_the_command_was_queued() -> None:
    g, fake, atem = rig()
    assert g.submit(RecallPreset(2)) == "queued"
    atem.rb = AtemReadback(program=SourceId.C2, preview=SourceId.C1)  # cut before it was sent
    drain(g)
    assert fake.moved == []
    assert g.st.refused == 1


def test_I2_no_atem_no_movement() -> None:
    g, _fake, atem = rig()
    atem.rb = None
    assert g.submit(Nudge(tilt=0.1)) == "no_atem"
    assert g.submit(StorePreset(1)) == "queued"


def test_I2_a_layout_on_air_holds_every_camera() -> None:
    g, _fake, atem = rig()
    atem.rb = AtemReadback(program=SourceId.SUPERSOURCE, preview=SourceId.C1, program_layout="X")
    assert g.submit(RecallPreset(1)) == "on_program"


def test_I2_property_random_commands_and_cuts_never_move_a_camera_on_air() -> None:
    """Plan CA-1: random commands while the ATEM cuts at random; none reaches a camera
    while it is on program or preview."""
    sources = st.sampled_from([SourceId.C1, SourceId.C2, SourceId.C5, SourceId.SUPERSOURCE])
    cmds = st.one_of(
        st.builds(RecallPreset, st.integers(-5, 300), st.floats(-1, 2)),
        st.builds(StorePreset, st.integers(0, 255)),
        st.builds(Nudge, st.floats(-3, 3), st.floats(-3, 3), st.floats(-3, 3)),
        st.builds(MoveTo, st.floats(-400, 400), st.floats(-200, 200), st.floats(0, 2)),
        st.builds(ZoomTo, st.floats(-1, 2), st.floats(0, 2)),
        st.builds(WhiteBalance, st.integers(2000, 10000)),
        st.builds(AutoTracking, st.booleans()),
    )
    ops = st.lists(
        st.one_of(
            st.tuples(st.just("submit"), cmds),
            st.tuples(st.just("cut"), st.tuples(sources, sources)),
            st.tuples(st.just("atem_lost"), st.none()),
            st.tuples(st.just("step"), st.none()),
        ),
        max_size=60,
    )

    @settings(max_examples=300, deadline=None)
    @given(ops)
    def check(script: list[tuple[str, Any]]) -> None:
        g, fake, atem = rig()

        async def go() -> None:
            for op, arg in script:
                if op == "submit":
                    g.submit(arg)
                elif op == "cut":
                    pgm, pvw = arg
                    atem.rb = AtemReadback(program=pgm, preview=pvw)
                elif op == "atem_lost":
                    atem.rb = None
                else:
                    before = len(fake.moved)
                    await g.step()
                    if len(fake.moved) > before:
                        air = atem.air()
                        assert air is not None
                        assert CameraId.C2 not in air.program | air.preview

        asyncio.run(go())

    check()


def test_limits_clamp_and_log(caplog: pytest.LogCaptureFixture) -> None:
    g, fake, _ = rig()
    g.limits = CameraLimits(pan=(-30, 30), tilt=(-10, 20), zoom=(0, 0.6), max_speed=0.4)
    assert g.submit(MoveTo(pan=90, tilt=-50, speed=1.0)) == "queued"
    assert g.submit(ZoomTo(zoom=0.9)) == "queued"
    assert g.submit(RecallPreset(1, speed=0.9)) == "queued"
    assert g.submit(RecallPreset(1, speed=0.2)) == "queued"  # within: not clamped
    drain(g)
    assert fake.received[:2] == ["move 30 -10 0.4", "position"]
    assert "zoom 0.6 0.3" in fake.received
    assert "recall 1 0.4" in fake.received
    assert "recall 1 0.2" in fake.received
    assert g.st.clamped == 3
    assert "klemt til grensene" in caplog.text


def test_a_nudge_stops_at_the_limit() -> None:
    g, fake, _ = rig()
    g.limits = CameraLimits(pan=(-30, 30))
    g.st.position = PTZPosition(pan=30, tilt=0, zoom=0.2)
    g.submit(Nudge(pan=0.5, tilt=0.2))
    g.submit(Nudge(pan=-0.5))  # back in: fine
    drain(g)
    assert fake.received[0] == "nudge 0 0.2 0"
    assert "nudge -0.5 0 0" in fake.received


def test_bad_preset_numbers_are_refused() -> None:
    g, _, _ = rig()
    assert g.submit(RecallPreset(256)) == "invalid"
    assert g.submit(StorePreset(-1)) == "invalid"


def test_circuit_breaker_after_three_failures() -> None:
    clock = Clock()
    g, fake, _ = rig(clock=clock)
    fake.down = True
    for n in range(3):
        g.submit(RecallPreset(n))
        drain(g)
    assert g.st.ok is False
    assert g.st.last_error == "recall_preset: svarer ikke"
    assert g.submit(RecallPreset(1)) == "breaker_open"
    clock.t += OPEN_S
    fake.down = False
    assert g.submit(RecallPreset(1)) == "queued"
    drain(g)
    assert g.st.ok is True


def test_a_slow_camera_times_out_and_never_blocks() -> None:
    g, fake, _ = rig(timeout_s=0.05)
    fake.delay_s = 0.5
    g.submit(RecallPreset(1))
    drain(g)
    assert g.st.failed == 1
    assert g.st.last_error == "recall_preset: svarte ikke innen 50 ms"


def test_a_lagging_queue_keeps_the_newest() -> None:
    g, fake, _ = rig()
    for n in range(20):
        g.submit(RecallPreset(n))
    assert g.st.queue == 8
    assert g.st.dropped == 12
    drain(g)
    assert fake.received[0] == "recall 12 0.5"


def test_run_sends_in_the_background() -> None:
    g, fake, _ = rig()

    async def go() -> None:
        task = asyncio.create_task(g.run())
        await asyncio.sleep(0)
        g.submit(RecallPreset(5))
        for _ in range(20):
            await asyncio.sleep(0.001)
            if fake.received:
                break
        task.cancel()

    asyncio.run(go())
    assert fake.received[0] == "recall 5 0.5"


def test_limits_in_devices_yaml_are_checked() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match=r"lowest 10\.0 is above highest -10\.0"):
        CameraLimits(pan=(10, -10))
    with pytest.raises(ValidationError, match="within 0–1"):
        CameraLimits(zoom=(0, 2))
