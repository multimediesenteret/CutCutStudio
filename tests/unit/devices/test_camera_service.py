"""CA-6: the camera service in core – S1 from the position read-back, H-CAM-MOVE, H-CAM-*,
AI-tracking off at start (AT6) and new addresses from the technician window."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from cutcut.common.config import example_site_dir, load_site
from cutcut.common.ids import CameraId, SourceId
from cutcut.common.models.site import CameraDevice, Devices
from cutcut.core.inputs import AtemReadback
from cutcut.devices.cameras.base import AutoTracking, CameraDriver, MoveTo
from cutcut.devices.cameras.guarded import OnAir, on_air
from cutcut.devices.cameras.service import SETTLE_S, CameraService
from cutcut.health import FuncCheck
from cutcut.health import checks as hc
from cutcut.health.model import CheckResult
from cutcut.sim.fake_camera import FakeCamera
from tests.unit.api.test_api import Rig

DEVICES: Devices = load_site(example_site_dir()).devices
C2 = CameraId.C2


class Clock:
    t = 1000.0

    def __call__(self) -> float:
        return self.t


def service(clock: Clock | None = None) -> tuple[CameraService, dict[CameraId, FakeCamera]]:
    fakes: dict[CameraId, FakeCamera] = {}

    def make(cam: CameraId, dev: CameraDevice) -> CameraDriver | None:
        if dev.ip is None:
            return None
        fakes[cam] = FakeCamera(cam)
        return fakes[cam]

    rb = AtemReadback(program=SourceId.C1, preview=SourceId.C5)

    def air() -> OnAir | None:
        return on_air(rb, list(DEVICES.cameras))

    svc = CameraService.from_devices(DEVICES, air, make=make, clock=clock or Clock())
    return svc, fakes


def now() -> datetime:
    return datetime(2026, 10, 21, 9, 0, tzinfo=UTC)


def drain(svc: CameraService) -> None:
    async def go() -> None:
        for g in svc.guards.values():
            while await g.step():
                pass

    asyncio.run(go())


def test_only_steerable_cameras_get_a_guard() -> None:
    svc, _fakes = service()
    assert set(svc.guards) == {CameraId.C1, CameraId.C2, CameraId.C3, CameraId.C4}
    assert CameraId.C5 not in svc.guards  # the fixed bird's-eye camera
    assert svc.submit(CameraId.C5, MoveTo(1, 1)) is None


def test_S1_a_camera_whose_position_changes_is_moving() -> None:
    svc, fakes = service()
    seen: list[frozenset[CameraId]] = []
    svc.on_moving = seen.append
    asyncio.run(svc.poll_positions())  # first read: nothing to compare with
    fakes[C2].pan = 25.0  # turns
    asyncio.run(svc.poll_positions())
    asyncio.run(svc.poll_positions())  # still again
    assert seen == [frozenset(), frozenset({C2}), frozenset()]


def test_H_CAM_MOVE_only_when_nobody_asked() -> None:
    clock = Clock()
    svc, fakes = service(clock)
    asyncio.run(svc.poll_positions())
    # CutCut asks C3 to move; the camera gets there slowly, after the first read-back
    assert svc.submit(CameraId.C3, MoveTo(10, 0)) == "queued"
    drain(svc)
    fakes[CameraId.C3].pan = 12.0
    # C4 has AI-tracking on: moving by itself is its job
    svc.submit(CameraId.C4, AutoTracking(on=True))
    drain(svc)
    fakes[CameraId.C4].tilt = 8.0
    # C2: someone turns it by hand
    fakes[C2].pan = -30.0
    asyncio.run(svc.poll_positions())
    assert svc.moving == {C2, CameraId.C3, CameraId.C4}
    assert set(svc.unexpected) == {C2}
    # long after CutCut's move, C3 moving again is no longer expected
    clock.t += SETTLE_S + 1
    fakes[CameraId.C3].pan = 40.0
    asyncio.run(svc.poll_positions())
    assert set(svc.unexpected) == {C2, CameraId.C3}


def test_run_turns_tracking_off_and_polls() -> None:
    svc, fakes = service()

    async def go() -> None:
        task = asyncio.create_task(svc.run())
        for _ in range(50):
            await asyncio.sleep(0.01)
            if all(f.received[:1] == ["status"] for f in fakes.values()) and all(
                "tracking False" in f.received for f in fakes.values()
            ):
                break
        task.cancel()

    asyncio.run(go())
    for f in fakes.values():
        assert "tracking False" in f.received  # AT6
        assert "status" in f.received
    assert all(g.st.status is not None for g in svc.guards.values())


def test_a_camera_that_is_down_opens_its_breaker() -> None:
    svc, fakes = service()
    fakes[C2].down = True
    for _ in range(3):
        asyncio.run(svc.poll_status())
    g = svc.guards[C2]
    assert g.st.ok is False
    assert g.st.status is not None
    assert g.st.status.online is False
    assert svc.guards[CameraId.C3].st.ok is True  # the others are not affected


def test_new_address_gets_a_new_driver() -> None:
    svc, _fakes = service()
    old = svc.guards[C2]
    cams = dict(DEVICES.cameras)
    cams[C2] = CameraDevice(ip="10.10.10.99", model="OBSBOT Tail 2")  # type: ignore[arg-type]
    svc.reconfigure(DEVICES.model_copy(update={"cameras": cams}))
    assert svc.guards[C2] is not old
    assert svc.guards[CameraId.C3] is not None
    assert getattr(svc.guards[C2].driver, "host", None) == "10.10.10.99"


# -- the checks ---------------------------------------------------------------------------------


def reading(**kw: object) -> hc.CameraReading:
    base: dict[str, object] = {
        "name": "Camera 2",
        "read": True,
        "online": True,
        "steered": True,
        "mode": "manuell",
        "answer_ms": 12.0,
        "since_start_s": 60.0,
    }
    return hc.CameraReading(**{**base, **kw})  # type: ignore[arg-type]


def status(r: hc.CameraReading) -> tuple[str, str]:
    res = hc.camera("H-CAM-C2", lambda: r, now).fn()
    assert not asyncio.iscoroutine(res)
    return res.status, res.value  # type: ignore[union-attr]


def test_H_CAM_green_yellow() -> None:
    assert status(reading()) == ("green", "12 ms")
    assert status(reading(read=False, since_start_s=3)) == ("green", "starter")
    assert status(reading(read=False, since_start_s=30)) == ("yellow", "ukjent")
    assert status(reading(online=False, last_error="svarer ikke")) == ("yellow", "svarer ikke")
    assert status(reading(steered=False)) == ("yellow", "svarer ikke")
    assert status(reading(answer_ms=350.0)) == ("yellow", "350 ms")
    assert status(reading(mode="auto (hvitbalanse 0, eksponering 0)"))[0] == "yellow"


def test_H_CAM_MOVE_red_for_a_while() -> None:
    def run(*rs: hc.CameraReading) -> tuple[str, str]:
        res = hc.camera_move(lambda: list(rs), now).fn()
        return res.status, res.value  # type: ignore[union-attr]

    assert run(reading(), reading(name="Camera 3")) == ("green", "i ro")
    assert run(reading(moved_by_itself_s=1.0)) == ("red", "Camera 2")
    assert run(reading(moved_by_itself_s=hc.CAM_MOVE_RED_S + 1))[0] == "green"


def test_studio_shows_a_check_per_camera(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    try:
        svc, _fakes = service()
        svc.started = svc.clock()
        studio = rig.sim.studio
        studio.deps.cameras = svc
        checks = {c.id: c for c in studio._health_checks() if isinstance(c, FuncCheck)}
        assert {"H-CAM-C1", "H-CAM-C2", "H-CAM-C3", "H-CAM-C4", "H-CAM-MOVE"} <= set(checks)
        asyncio.run(svc.poll_status())
        res = checks["H-CAM-C2"].fn()
        assert isinstance(res, CheckResult)
        assert res.status == "green"
        assert res.message == "Camera 2 svarer og står i manuell."
        svc.unexpected[C2] = svc.clock()
        res = checks["H-CAM-MOVE"].fn()
        assert isinstance(res, CheckResult)
        assert res.status == "red"
    finally:
        rig.store.close()


def test_slow_zoom_on_air_in_small_steps_and_stop() -> None:
    """Z1/Z2 (P4): the one move allowed on air, step by step, and stopped at once."""
    svc, fakes = service()
    cam = CameraId.C1  # on program
    g = svc.guards[cam]
    fakes[cam].zoom = 0.40

    async def go(allowed: bool, stop_after: float | None) -> None:
        g.slow_zoom_ok = lambda: allowed
        await g.refresh()
        runner = asyncio.create_task(g.run())
        assert svc.slow_zoom(cam, 0.05, 0.25)
        if stop_after is not None:
            await asyncio.sleep(stop_after)
            svc.stop_zoom(cam)
        await asyncio.sleep(0.4)
        runner.cancel()

    asyncio.run(go(allowed=True, stop_after=None))
    assert 0.44 <= fakes[cam].zoom <= 0.46  # zoomed in 5 % on air
    fakes[cam].zoom = 0.40
    asyncio.run(go(allowed=False, stop_after=None))
    assert fakes[cam].zoom == 0.40  # switch off: the guard refuses on air (I2)
    asyncio.run(go(allowed=True, stop_after=0.06))
    assert 0.40 < fakes[cam].zoom < 0.45  # Z2: stopped part way


def test_framing_preset_is_refused_on_air() -> None:
    svc, _fakes = service()
    assert svc.frame(CameraId.C1, 2) == "on_program"  # I2
    assert svc.frame(CameraId.C2, 2) == "queued"  # off air
