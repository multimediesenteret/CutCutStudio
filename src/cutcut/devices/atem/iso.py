"""ISO recording on the ATEM's own disk (spec 7.7, DA-8).

The ATEM records every input as its own file next to the program. Pearl is still the main
recorder; ISO files are for backup and editing. CutCut starts ISO from the technician window,
and together with Pearl when the show type or show says ``iso_record``. Only a person stops it
(``I7``): when Pearl stops, the technician window asks whether ISO should stop too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from cutcut.devices.atem.bridge import AtemIso

IsoState = Literal["idle", "recording", "stopping", "unknown"]


@dataclass(frozen=True)
class IsoStatus:
    state: IsoState
    disk: str | None = None
    time_available_s: float | None = None
    error: str | None = None
    all_inputs: bool = False

    @property
    def recording(self) -> bool:
        return self.state in ("recording", "stopping")


class IsoRecorder(Protocol):
    """The ATEM side: ``AtemBridgeClient`` in studio, ``FakeAtem`` in the simulator."""

    def iso_start(self, filename: str) -> bool: ...
    def iso_stop(self) -> bool: ...
    def iso_status(self) -> IsoStatus | None: ...


def from_raw(iso: AtemIso | None) -> IsoStatus | None:
    if iso is None:
        return None
    state: IsoState = {"Idle": "idle", "Recording": "recording", "Stopping": "stopping"}.get(
        iso.state or "", "unknown"
    )  # type: ignore[assignment]
    return IsoStatus(
        state=state,
        disk=iso.disk,
        time_available_s=iso.time_available_s,
        error=iso.error,
        all_inputs=iso.all_inputs,
    )


def filename(when: datetime, show_type: str, username: str | None) -> str:
    """``<dato>_<show-type>_<brukernavn>`` (7.7), with only letters, digits, ``.``, ``_`` and
    ``-`` so the ATEM and Windows both accept it. Without a session: ``…_tekniker``."""
    raw = f"{when:%Y-%m-%d}_{show_type}_{username or 'tekniker'}"
    return re.sub(r"[^\w.-]", "-", raw, flags=re.ASCII)[:63]
