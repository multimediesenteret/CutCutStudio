"""Studio setup files in ``site/<studio>/`` (spec 12.2): devices, staff and Companion map.

Shows live in ``site/<studio>/shows/*.yaml`` (models.show). Secrets are never here (12.4).
"""

from __future__ import annotations

import re
from ipaddress import IPv4Address
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from cutcut.common.ids import CameraId, SourceId, is_layout, is_shot


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AtemDevice(_Strict):
    ip: IPv4Address
    model: str | None = None  # found automatically on connect (spec 2.2); noted here when known


class CompanionDevice(_Strict):
    url: HttpUrl = HttpUrl("http://127.0.0.1:8000")
    engine_page: int = Field(default=10, ge=1, le=99)
    operator_page: int = Field(default=11, ge=1, le=99)
    pages_version: int = Field(default=1, ge=1)  # expected cutcut_pages_version


class PearlDevice(_Strict):
    ip: IPv4Address
    recorder_id: str = "1"
    username: str = "cutcut"  # password in Windows Credential Manager (pearl_password)
    scheme: Literal["https", "http"] = "https"
    port: int | None = Field(default=None, ge=1, le=65535)  # None: the scheme's default
    # Pearl ships with a self-signed certificate. On the closed studio network the address is
    # fixed; set to true once a trusted certificate is installed on the Pearl.
    verify_tls: bool = False


class CameraLimits(_Strict):
    """How far CutCut may move a camera (CA-1, 8.4). Commands outside are clamped and logged.

    Pan and tilt in degrees from the camera's home, zoom 0 (widest) to 1 (tightest), speed
    0–1 of the camera's top speed."""

    pan: tuple[float, float] = (-170.0, 170.0)
    tilt: tuple[float, float] = (-30.0, 90.0)
    zoom: tuple[float, float] = (0.0, 1.0)
    max_speed: float = Field(default=0.5, gt=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        for name in ("pan", "tilt", "zoom"):
            lo, hi = getattr(self, name)
            if lo > hi:
                raise ValueError(f"{name}: lowest {lo} is above highest {hi}")
        if not 0 <= self.zoom[0] <= self.zoom[1] <= 1:
            raise ValueError("zoom limits must lie within 0–1")
        return self


class CameraDevice(_Strict):
    ip: IPv4Address | None = None
    model: str
    limits: CameraLimits = CameraLimits()


class CardReaderDevice(_Strict):
    usb_id: str = Field(default="09D8:0320", pattern=r"^[0-9A-F]{4}:[0-9A-F]{4}$")


class AudioDevice(_Strict):
    """The RØDECaster's multitrack over USB (docs/research/lyd-fra-rodecaster.md, AU-5)."""

    backend: Literal["asio", "wasapi"] = "asio"  # WASAPI exclusive is the reserve
    device: str = "RODECaster"  # part of the device name, case-insensitive
    channels: int = Field(default=20, ge=12, le=32)  # USB 1 multitrack
    buffer: int = Field(default=256, ge=64, le=2048)  # samples; raise on dropouts


class NtnuApi(_Strict):
    url: HttpUrl = HttpUrl("https://gw-ntnu.intark.uh-it.no/tia/v4/autorisasjon/mifareid")
    timeout_s: float = Field(default=3.0, gt=0, le=10)


class SmtpConfig(_Strict):
    """The mail relay the studio PC sends alerts through (HS-3). Empty host: no email."""

    host: str = ""
    port: int = Field(default=587, ge=1, le=65535)
    starttls: bool = True
    sender: str = "cutcut-studio@ntnu.no"
    username: str = ""  # password in Windows Credential Manager (smtp_password)


EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


class AlertsConfig(_Strict):
    """Alerts outside the studio (HS-3, Q29): email when something is red for over a minute,
    and at once when a recording fails."""

    email: list[str] = Field(default_factory=list)
    red_after_s: float = Field(default=60.0, ge=0, le=3600)
    max_per_hour: int = Field(default=10, ge=1, le=100)
    smtp: SmtpConfig = SmtpConfig()

    @field_validator("email", mode="before")
    @classmethod
    def _split(cls, v: object) -> object:
        if isinstance(v, str):  # «a@ntnu.no, b@ntnu.no» from the setup screen
            return [x.strip() for x in re.split(r"[,;\s]+", v) if x.strip()]
        return v

    @field_validator("email")
    @classmethod
    def _valid(cls, v: list[str]) -> list[str]:
        for addr in v:
            if not EMAIL.match(addr):
                raise ValueError(f"ugyldig e-postadresse: {addr}")
        return v


class Devices(_Strict):
    schema_version: int = 1
    studio: str = Field(pattern=r"^[a-z0-9-]+$")
    atem: AtemDevice
    companion: CompanionDevice = CompanionDevice()
    pearl: PearlDevice
    cameras: dict[CameraId, CameraDevice]
    audio: AudioDevice = AudioDevice()
    card_reader: CardReaderDevice = CardReaderDevice()
    ntnu_api: NtnuApi = NtnuApi()
    alerts: AlertsConfig = AlertsConfig()
    api_port: int = Field(default=8080, ge=1024, le=65535)

    @model_validator(mode="after")
    def _unique_ips(self) -> Self:
        ips = [str(self.atem.ip), str(self.pearl.ip)] + [
            str(c.ip) for c in self.cameras.values() if c.ip is not None
        ]
        if len(set(ips)) != len(ips):
            raise ValueError("every device needs its own IP address")
        return self


class Staff(_Strict):
    """Approved technicians (spec 12.4, D-045). Usernames only, never card numbers."""

    schema_version: int = 1
    operators: list[str] = Field(default_factory=list)
    admins: list[str] = Field(default_factory=list)

    def role_of(self, username: str) -> str | None:
        if username in self.admins:
            return "admin"
        if username in self.operators:
            return "operator"
        return None


class CompanionButton(_Strict):
    row: int = Field(ge=0, le=7)
    col: int = Field(ge=0, le=7)


class CompanionMap(_Strict):
    """Which button on the engine page (spec 7.1) does what. Kept in the studio repo."""

    schema_version: int = 1
    preview: dict[SourceId, CompanionButton]  # row 0: put a source on preview
    layouts: dict[str, CompanionButton] = Field(default_factory=dict)  # rows 1–2: layout shots
    take_cut: CompanionButton = CompanionButton(row=3, col=0)
    take_mix: CompanionButton = CompanionButton(row=3, col=1)
    layout_off: CompanionButton = CompanionButton(row=1, col=4)
    # Operator page (11): direct program cuts for emergencies and the «Kun lyd» graphic.
    # When a button is missing, the executor uses atem-bridge instead (S5).
    operator_direct: dict[SourceId, CompanionButton] = Field(default_factory=dict)
    operator_audio_only: CompanionButton | None = None

    @model_validator(mode="after")
    def _valid(self) -> Self:
        for shot in self.layouts:
            if not (is_shot(shot) and is_layout(shot)):
                raise ValueError(f"{shot!r} is not a layout shot")
        buttons = [*self.preview.values(), *self.layouts.values()]
        buttons += [self.take_cut, self.take_mix, self.layout_off]
        if len({(b.row, b.col) for b in buttons}) != len(buttons):
            raise ValueError("two actions share the same Companion button")
        operator = list(self.operator_direct.values())
        if self.operator_audio_only is not None:
            operator.append(self.operator_audio_only)
        if len({(b.row, b.col) for b in operator}) != len(operator):
            raise ValueError("two operator actions share the same Companion button")
        return self
