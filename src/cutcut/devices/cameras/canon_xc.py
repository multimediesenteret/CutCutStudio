"""Canon CR-N300 (CA-4). Canon's own protocol is XC over HTTP, but its command list is not
here yet (Q6). Until then the camera is driven over VISCA, which CR-N cameras also speak:
status, position and presets work; colour and exposure wait for XC and answer
:class:`Unsupported`, so the screens hide those buttons. CR-N300 has no AI-tracking."""

from __future__ import annotations

from dataclasses import dataclass

from cutcut.devices.cameras.base import Unsupported
from cutcut.devices.cameras.visca_ptz import ViscaPtz


@dataclass
class CanonXcDriver(ViscaPtz):
    async def set_white_balance(
        self, kelvin: int | None = None, r: int | None = None, b: int | None = None
    ) -> None:
        raise Unsupported("hvitbalanse på Canon kommer med XC (Q6)")

    async def set_exposure(
        self, iris: float | None = None, gain_db: float | None = None, shutter: str | None = None
    ) -> None:
        raise Unsupported("eksponering på Canon kommer med XC (Q6)")
