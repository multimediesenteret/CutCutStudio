"""OBSBOT Tail 2: VISCA for status, position and presets (CA-2), OSC for colour temperature,
exposure and AI-tracking (CA-3), both straight to the camera (spec 7.3). Always used inside
``GuardedCamera``, which does the on-air guard and the limits; this class only speaks the
protocol.

Camera units are converted to CutCut's (degrees, zoom 0–1) with :class:`Calibration`. The
numbers are OBSBOT's documented ranges and are confirmed by the machine test (CA-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cutcut.common.ids import CameraId
from cutcut.devices.cameras import visca
from cutcut.devices.cameras.base import CameraStatus, PTZPosition, Unsupported
from cutcut.devices.cameras.osc import OscSender

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

NUDGE_DEG = 2.0  # one full nudge step (1.0) in degrees
NUDGE_ZOOM = 0.05  # one full zoom nudge step, of the whole range


@dataclass(frozen=True)
class Calibration:
    pan_units_per_degree: float = 14.4
    tilt_units_per_degree: float = 14.4
    zoom_max: int = 0x4000  # VISCA zoom at full tele

    def to_units(self, p: PTZPosition) -> tuple[int, int, int]:
        return (
            round(p.pan * self.pan_units_per_degree),
            round(p.tilt * self.tilt_units_per_degree),
            round(min(max(p.zoom, 0.0), 1.0) * self.zoom_max),
        )

    def from_units(self, pan: int, tilt: int, zoom: int) -> PTZPosition:
        return PTZPosition(
            pan=round(pan / self.pan_units_per_degree, 2),
            tilt=round(tilt / self.tilt_units_per_degree, 2),
            zoom=round(zoom / self.zoom_max, 4),
        )


def _scale(speed: float, top: int) -> int:
    """0–1 → 1…top (VISCA speeds start at 1)."""
    return max(1, min(top, round(speed * top)))


@dataclass
class ObsbotDriver:
    id: CameraId
    host: str
    cal: Calibration = Calibration()
    osc_port: int = OSC_PORT
    client: visca.ViscaClient = field(init=False)
    osc: OscSender = field(init=False)

    def __post_init__(self) -> None:
        self.client = visca.ViscaClient(self.host)
        self.osc = OscSender(self.host, self.osc_port)

    async def connect(self) -> None:
        await self.client.open()

    async def status(self) -> CameraStatus:
        try:
            power = visca.parse_byte(await self.client.inquiry(visca.INQ_POWER))
            wb = visca.parse_byte(await self.client.inquiry(visca.INQ_WB_MODE))
            ae = visca.parse_byte(await self.client.inquiry(visca.INQ_AE_MODE))
        except (TimeoutError, visca.ViscaError) as e:
            return CameraStatus(online=False, last_error=str(e) or "svarer ikke")
        manual = wb == 0x05 and ae == 0x03
        mode = "manuell" if manual else f"auto (hvitbalanse {wb:x}, eksponering {ae:x})"
        return CameraStatus(online=power == 0x02, mode=mode)

    async def recall_preset(self, n: int, speed: float = 0.5) -> None:
        await self.client.command(visca.preset_speed(_scale(speed, 0x19)))
        await self.client.command(visca.recall_preset(n))

    async def store_preset(self, n: int) -> None:
        await self.client.command(visca.store_preset(n))

    async def position(self) -> PTZPosition | None:
        pan, tilt = visca.parse_pan_tilt(await self.client.inquiry(visca.INQ_PAN_TILT))
        zoom = visca.parse_zoom(await self.client.inquiry(visca.INQ_ZOOM))
        return self.cal.from_units(pan, tilt, zoom)

    async def move_to(self, pan: float, tilt: float, speed: float) -> None:
        p, t, _ = self.cal.to_units(PTZPosition(pan, tilt, 0.0))
        await self.client.command(
            visca.pan_tilt_absolute(p, t, _scale(speed, 0x18), _scale(speed, 0x14))
        )

    async def zoom_to(self, zoom: float, speed: float) -> None:
        _, _, z = self.cal.to_units(PTZPosition(0.0, 0.0, zoom))
        await self.client.command(visca.zoom_direct(z))

    async def nudge(self, pan: float, tilt: float, zoom: float) -> None:
        """A small step from where the camera is now, slowly."""
        at = await self.position()
        if at is None:
            return
        if pan or tilt:
            await self.move_to(at.pan + pan * NUDGE_DEG, at.tilt + tilt * NUDGE_DEG, 0.2)
        if zoom:
            await self.zoom_to(at.zoom + zoom * NUDGE_ZOOM, 0.2)

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
        self.client.close()
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
