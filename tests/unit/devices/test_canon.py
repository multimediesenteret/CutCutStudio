"""CA-4: Canon CR-N300 over VISCA until the XC list arrives (Q6), and the driver factory."""

from __future__ import annotations

import asyncio

import pytest

from cutcut.common.config import example_site_dir, load_site
from cutcut.common.ids import CameraId
from cutcut.common.models.site import CameraDevice
from cutcut.devices.cameras.base import PTZPosition, Unsupported
from cutcut.devices.cameras.canon_xc import CanonXcDriver
from cutcut.devices.cameras.factory import make_driver
from cutcut.devices.cameras.obsbot import ObsbotDriver
from cutcut.sim.fake_camera import FakeCamera
from cutcut.sim.fake_visca import serve


def test_canon_presets_and_position_over_visca() -> None:
    async def go() -> None:
        cam = FakeCamera(CameraId.C1)
        fake, port = await serve(cam)
        drv = CanonXcDriver(CameraId.C1, "127.0.0.1")
        drv.client.port = port
        try:
            await drv.move_to(-20.0, 4.0, 0.3)
            await drv.store_preset(1)
            await drv.move_to(0.0, 0.0, 0.3)
            await drv.recall_preset(1)
            assert await drv.position() == PTZPosition(-20.0, 4.03, 0.0)  # 1/14.4 degree units
            assert (await drv.status()).online is True
            with pytest.raises(Unsupported, match="XC"):
                await drv.set_white_balance(kelvin=5600)
            with pytest.raises(Unsupported, match="XC"):
                await drv.set_exposure(gain_db=0)
            await drv.set_auto_tracking(False)  # AT6: nothing to turn off, and no error
            with pytest.raises(Unsupported, match="AI-tracking"):
                await drv.set_auto_tracking(True)
        finally:
            drv.close()
            if fake._transport is not None:
                fake._transport.close()

    asyncio.run(go())


def test_the_right_driver_for_each_camera() -> None:
    site = load_site(example_site_dir())
    drivers = {c: make_driver(c, d) for c, d in site.devices.cameras.items()}
    assert isinstance(drivers[CameraId.C1], CanonXcDriver)
    assert isinstance(drivers[CameraId.C2], ObsbotDriver)
    assert drivers[CameraId.C5] is None  # fixed bird's-eye camera over HDMI
    assert make_driver(CameraId.C4, CameraDevice(ip="10.0.0.9", model="Panasonic AW")) is None  # type: ignore[arg-type]
