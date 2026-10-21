"""CA-2: OBSBOT over VISCA – the byte tables from spec 7.3, replies, and the driver against a
fake camera over real UDP, inside GuardedCamera."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from cutcut.common.ids import CameraId, SourceId
from cutcut.common.models.site import CameraLimits
from cutcut.core.inputs import AtemReadback
from cutcut.devices.cameras import visca
from cutcut.devices.cameras.base import PTZPosition, RecallPreset, Unsupported, WhiteBalance
from cutcut.devices.cameras.guarded import GuardedCamera, on_air
from cutcut.devices.cameras.obsbot import Calibration, ObsbotDriver
from cutcut.sim.fake_camera import FakeCamera
from cutcut.sim.fake_visca import FakeVisca, serve


def hx(b: bytes) -> str:
    return b.hex(" ").upper()


def test_commands_byte_for_byte_from_the_table() -> None:
    assert hx(visca.recall_preset(0x12)) == "81 01 04 3F 02 12 FF"
    assert hx(visca.store_preset(3)) == "81 01 04 3F 01 03 FF"
    assert hx(visca.preset_speed(0x19)) == "81 01 7E 04 1C 01 09 FF"
    assert hx(visca.preset_speed(5)) == "81 01 7E 04 1C 00 05 FF"
    assert hx(visca.pan_tilt_absolute(0x1234, -1, 0x10, 0x08)) == (
        "81 01 06 02 10 08 01 02 03 04 0F 0F 0F 0F FF"
    )
    assert hx(visca.zoom_direct(0x4000)) == "81 01 04 47 04 00 00 00 FF"
    assert hx(visca.zoom_drive(1, 0)) == "81 01 04 07 20 FF"
    assert hx(visca.zoom_drive(-1, 7)) == "81 01 04 07 37 FF"
    assert hx(visca.zoom_drive(0, 3)) == "81 01 04 07 00 FF"
    assert hx(visca.pan_tilt_drive(-1, 1, 1, 1)) == "81 01 06 01 01 01 01 01 FF"
    assert hx(visca.white_balance_mode(5)) == "81 01 04 35 05 FF"
    assert hx(visca.exposure_mode(3)) == "81 01 04 39 03 FF"
    assert hx(visca.INQ_PAN_TILT) == "81 09 06 12 FF"
    assert hx(visca.INQ_ZOOM) == "81 09 04 47 FF"
    assert hx(visca.INQ_R_GAIN) == "81 09 04 43 FF"
    assert hx(visca.INQ_B_GAIN) == "81 09 04 44 FF"


def test_values_outside_the_table_are_refused() -> None:
    with pytest.raises(ValueError, match="preset 256"):
        visca.recall_preset(256)
    with pytest.raises(ValueError, match="zoom"):
        visca.zoom_direct(0x4001)
    with pytest.raises(ValueError, match="preset-fart"):
        visca.preset_speed(0)


def test_replies_are_parsed() -> None:
    assert visca.parse_pan_tilt(bytes.fromhex("9050 01020304 0f0f0f0f ff")) == (0x1234, -1)
    assert visca.parse_zoom(bytes.fromhex("9050 04000000 ff")) == 0x4000
    assert visca.parse_byte(bytes.fromhex("905005ff")) == 5
    assert visca.parse_gain(bytes.fromhex("9050 00000a0b ff")) == 0xAB
    with pytest.raises(visca.ViscaError, match="uventet svar på posisjon"):
        visca.parse_pan_tilt(b"\x90\x41\xff")
    assert visca.error_of(bytes.fromhex("906102ff")) == "syntaksfeil"
    assert visca.error_of(bytes.fromhex("906141ff")) == "kan ikke utføres nå"
    assert visca.error_of(b"\x90\x41\xff") is None


def test_the_ip_header() -> None:
    f = visca.frame(visca.COMMAND, 7, visca.recall_preset(1))
    assert hx(f[:8]) == "01 00 00 07 00 00 00 07"
    assert visca.unframe(f) == (visca.COMMAND, 7, visca.recall_preset(1))


def test_calibration_round_trips() -> None:
    cal = Calibration()
    p = PTZPosition(pan=-42.5, tilt=12.25, zoom=0.5)
    assert cal.from_units(*cal.to_units(p)) == PTZPosition(-42.5, 12.22, 0.5)


Body = Callable[[ObsbotDriver, FakeCamera, FakeVisca], Awaitable[None]]


def with_camera(body: Body, timeout_s: float = 0.2) -> None:
    async def go() -> None:
        cam = FakeCamera(CameraId.C2)
        fake, port = await serve(cam)
        drv = ObsbotDriver(CameraId.C2, "127.0.0.1")
        drv.client.port = port
        drv.client.timeout_s = timeout_s
        try:
            await body(drv, cam, fake)
        finally:
            drv.close()
            assert fake._transport is not None
            fake._transport.close()

    asyncio.run(go())


def test_presets_position_and_status_over_udp() -> None:
    async def body(drv: ObsbotDriver, cam: FakeCamera, fake: FakeVisca) -> None:
        await drv.connect()
        await drv.move_to(30.0, -5.0, 0.3)
        await drv.zoom_to(0.25, 0.3)
        assert await drv.position() == PTZPosition(30.0, -5.0, 0.25)
        await drv.store_preset(4)
        await drv.move_to(0.0, 0.0, 0.3)
        await drv.recall_preset(4, speed=0.2)
        assert (cam.pan, cam.tilt, cam.zoom) == (30.0, -5.0, 0.25)
        assert "81 01 7e 04 1c 00 05 ff" in fake.log  # 0.2 of 0x19
        st = await drv.status()
        assert st.online is True
        assert st.mode == "manuell"
        fake.wb_mode = 0x00
        assert (await drv.status()).mode.startswith("auto")

    with_camera(body)


def test_a_nudge_is_a_small_step_from_where_it_is() -> None:
    async def body(drv: ObsbotDriver, cam: FakeCamera, fake: FakeVisca) -> None:
        cam.pan, cam.tilt, cam.zoom = 10.0, 0.0, 0.5
        await drv.nudge(0.5, -0.5, 1.0)
        # one camera unit is 1/14.4 degree
        assert (cam.pan, cam.tilt, cam.zoom) == pytest.approx((11.0, -1.0, 0.55), abs=0.05)

    with_camera(body)


def test_camera_errors_and_silence() -> None:
    async def body(drv: ObsbotDriver, cam: FakeCamera, fake: FakeVisca) -> None:
        with pytest.raises(visca.ViscaError, match="syntaksfeil"):
            await drv.client.command(bytes.fromhex("81 01 04 99 ff"))
        fake.silent = True
        with pytest.raises(TimeoutError):
            await drv.recall_preset(1)
        st = await drv.status()
        assert st.online is False

    with_camera(body, timeout_s=0.05)


def test_osc_functions_wait_for_CA3() -> None:
    async def body(drv: ObsbotDriver, cam: FakeCamera, fake: FakeVisca) -> None:
        with pytest.raises(Unsupported):
            await drv.set_white_balance(kelvin=5600)

    with_camera(body)


def test_PV2_the_real_driver_behind_the_guard() -> None:
    """End to end: GuardedCamera + ObsbotDriver + fake camera over UDP."""
    rb: dict[str, Any] = {"rb": AtemReadback(program=SourceId.C1, preview=SourceId.C2)}

    async def body(drv: ObsbotDriver, cam: FakeCamera, fake: FakeVisca) -> None:
        g = GuardedCamera(drv, CameraLimits(), lambda: on_air(rb["rb"], [CameraId.C2]))
        assert g.submit(RecallPreset(1)) == "on_preview"
        rb["rb"] = AtemReadback(program=SourceId.C1, preview=SourceId.C3)
        assert g.submit(RecallPreset(1, speed=0.9)) == "queued"  # clamped to 0.5
        assert g.submit(WhiteBalance(kelvin=5600)) == "queued"
        while await g.step():
            pass
        assert cam.received == ["recall 1 0.48"]  # 0x0C of 0x19
        assert g.st.failed == 0  # not a broken camera: no step towards the circuit breaker
        assert g.st.unsupported == 1
        assert g.st.last_error == "white_balance: fargetemperatur settes med OSC (CA-3)"
        assert g.st.position == PTZPosition(0.0, 0.0, 0.0)

    with_camera(body)
