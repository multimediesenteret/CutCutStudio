"""CA-5: the camera machine test against a fake OBSBOT and Canon over real UDP."""

from __future__ import annotations

import asyncio

from cutcut.common.ids import CameraId
from cutcut.devices.cameras.canon_xc import CanonXcDriver
from cutcut.devices.cameras.obsbot import ObsbotDriver
from cutcut.devices.cameras.visca_ptz import ViscaPtz
from cutcut.hwtest.camera import CameraTest
from cutcut.hwtest.report import Report
from cutcut.sim import fake_osc, fake_visca
from cutcut.sim.fake_camera import FakeCamera


class Yes:
    def __init__(self) -> None:
        self.said: list[str] = []

    def say(self, text: str) -> None:
        self.said.append(text)

    def wait(self, text: str) -> bool:
        self.said.append(text)
        return True


def run_test(
    obsbot: bool = True,
    *,
    tracking_works: bool = True,
    on_air: bool = False,
    down: bool = False,
) -> tuple[Report, FakeCamera]:
    cam = FakeCamera(CameraId.C2)

    async def go() -> Report:
        visca_side, vport = await fake_visca.serve(cam)
        osc_side, oport = await fake_osc.serve(cam)
        visca_side.silent = down
        driver: ViscaPtz
        if obsbot:
            driver = ObsbotDriver(CameraId.C2, "127.0.0.1", osc_port=oport)
        else:
            driver = CanonXcDriver(CameraId.C2, "127.0.0.1")
        driver.client.port = vport
        driver.client.timeout_s = 0.1

        now = [0.0]

        async def sleep(s: float) -> None:
            await asyncio.sleep(0.005)  # let UDP land; no real waiting in tests
            now[0] += s
            if cam.tracking and tracking_works:
                cam.pan += 3.0  # a person walks; the camera follows

        test = CameraTest(CameraId.C2, driver, Yes(), lambda: on_air, sleep, lambda: now[0])
        try:
            return await test.run()
        finally:
            driver.close()
            for t in (visca_side._transport, osc_side.transport):
                if t is not None:
                    t.close()

    return asyncio.run(go()), cam


def results(report: Report) -> dict[str, str]:
    return {s.id: s.result for s in report.steps}


def test_a_working_obsbot_passes_every_step() -> None:
    report, cam = run_test()
    assert results(report) == {f"KA{i}": "ok" for i in range(1, 8)}, report.to_markdown()
    ka4 = next(s for s in report.steps if s.id == "KA4")
    assert ka4.details["pan_units_for_10_deg"] == 144  # the default Calibration
    assert cam.tracking is False  # left off
    assert cam.kelvin == 5600
    ka7 = next(s for s in report.steps if s.id == "KA7")
    assert ka7.answers == "Q16"


def test_Q16_no_when_tracking_does_not_follow() -> None:
    report, _ = run_test(tracking_works=False)
    assert results(report)["KA7"] == "feil"
    assert "Q16: nei" in next(s.summary for s in report.steps if s.id == "KA7")


def test_canon_skips_what_waits_for_xc() -> None:
    report, _ = run_test(obsbot=False)
    r = results(report)
    assert r["KA4"] == "ok"
    assert r["KA6"] == "hoppet over"
    assert r["KA7"] == "hoppet over"


def test_I2_nothing_moves_on_air() -> None:
    report, cam = run_test(on_air=True)
    r = results(report)
    assert r["KA1"] == "ok"
    for sid in ("KA4", "KA5", "KA6", "KA7"):
        assert r[sid] == "hoppet over", sid
    assert cam.moved == []


def test_a_camera_that_does_not_answer() -> None:
    report, _ = run_test(down=True)
    r = results(report)
    assert r["KA1"] == "feil"
    assert set(list(r.values())[1:]) == {"hoppet over"}
    assert report.result == "feil"
