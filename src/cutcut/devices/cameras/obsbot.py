"""OBSBOT Tail 2: VISCA for status, position and presets (CA-2), OSC for colour temperature,
exposure and AI-tracking (CA-3), both straight to the camera (spec 7.3). Always used inside
``GuardedCamera``, which does the on-air guard and the limits; this class only speaks the
protocol.

The VISCA part is shared with Canon (``visca_ptz``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cutcut.devices.cameras.base import Unsupported
from cutcut.devices.cameras.osc import OscSender
from cutcut.devices.cameras.visca_ptz import Calibration, ViscaPtz

__all__ = ["Calibration", "ObsbotDriver"]

OSC_PORT = 57110  # the camera listens here (OBSBOT's OSC definition for Tail 2)
GENERAL = "/OBSBOT/WebCam/General"
OSC_AUTO_WB = f"{GENERAL}/SetAutoWhiteBalance"
OSC_KELVIN = f"{GENERAL}/SetColorTemperature"
OSC_AUTO_EXPOSURE = f"{GENERAL}/SetAutoExposure"
OSC_SHUTTER = f"{GENERAL}/SetShutterSpeed"
OSC_ISO = f"{GENERAL}/SetISO"
# Not in OBSBOT's published table; named in spec 7.3. Whether the studio's firmware has it is
# Q16, checked by the machine test (CA-5).
OSC_AI_ENABLE = "/OBSBOT/Camera/Tail2/SetAiEnable"
KELVIN = (2000, 10000)
SHUTTERS = frozenset(
    {6400, 5000, 3200, 2500, 2000, 1600, 1250, 1000, 800, 640, 500, 400, 320, 240, 200, 160}
    | {120, 100, 80, 60, 50, 40, 30, 25, 20, 15, 10, 8, 5, 4, 3}
)
ISO = (100, 6400)


@dataclass
class ObsbotDriver(ViscaPtz):
    osc_port: int = OSC_PORT
    osc: OscSender = field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.osc = OscSender(self.host, self.osc_port)

    async def set_white_balance(
        self, kelvin: int | None = None, r: int | None = None, b: int | None = None
    ) -> None:
        """Manual white balance at ``kelvin`` (2000–10000). R/B gain is only on OBSBOT Tiny."""
        if r is not None or b is not None:
            raise Unsupported("R/B-gain finnes ikke på Tail 2; bruk kelvin")
        if kelvin is None:
            raise Unsupported("Tail 2 trenger kelvin")
        lo, hi = KELVIN
        if not lo <= kelvin <= hi:
            raise ValueError(f"kelvin {kelvin} er utenfor {lo}–{hi}")
        await self.osc.send(OSC_AUTO_WB, 0)
        await self.osc.send(OSC_KELVIN, kelvin)

    async def set_exposure(
        self, iris: float | None = None, gain_db: float | None = None, shutter: str | None = None
    ) -> None:
        """Manual exposure. Shutter as «1/50»; gain as ISO (0 dB = ISO 100, 6 dB per stop).
        Tail 2 has a fixed aperture."""
        if iris is not None:
            raise Unsupported("Tail 2 har fast blender")
        values: list[tuple[str, int]] = []
        if shutter is not None:
            values.append((OSC_SHUTTER, shutter_value(shutter)))
        if gain_db is not None:
            values.append((OSC_ISO, iso_of(gain_db)))
        await self.osc.send(OSC_AUTO_EXPOSURE, 0)
        for address, v in values:
            await self.osc.send(address, v)

    async def set_auto_tracking(self, on: bool) -> None:
        await self.osc.send(OSC_AI_ENABLE, 1 if on else 0)

    def close(self) -> None:
        super().close()
        self.osc.close()


def shutter_value(text: str) -> int:
    """«1/50» → 50, one of the speeds OBSBOT accepts."""
    try:
        v = int(text.removeprefix("1/"))
    except ValueError:
        raise ValueError(f"ukjent lukkertid {text!r}; skriv f.eks. 1/50") from None
    if v not in SHUTTERS:
        raise ValueError(f"lukkertid 1/{v} finnes ikke på Tail 2")
    return v


def iso_of(gain_db: float) -> int:
    """Gain in dB as ISO, within what Tail 2 takes."""
    lo, hi = ISO
    return int(min(max(round(100 * 2 ** (gain_db / 6)), lo), hi))
