"""The right driver for each camera in ``devices.yaml`` (CA-4), by model name."""

from __future__ import annotations

from cutcut.common.ids import CameraId
from cutcut.common.models.site import CameraDevice
from cutcut.devices.cameras.base import CameraDriver
from cutcut.devices.cameras.canon_xc import CanonXcDriver
from cutcut.devices.cameras.obsbot import ObsbotDriver


def make_driver(cam: CameraId, dev: CameraDevice) -> CameraDriver | None:
    """``None`` for a camera CutCut does not steer: no address (a fixed bird's-eye camera
    over HDMI) or a model without a driver yet (Panasonic and Sony are phase 2)."""
    if dev.ip is None:
        return None
    model = dev.model.lower()
    if "obsbot" in model:
        return ObsbotDriver(cam, str(dev.ip))
    if "canon" in model:
        return CanonXcDriver(cam, str(dev.ip))
    return None
