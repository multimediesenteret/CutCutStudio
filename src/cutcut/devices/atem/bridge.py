"""Core's side of atem-bridge (DA-2): what the ATEM shows, and direct cuts as reserve (S5).

The Node bridge reports raw ATEM input numbers (``atem.state``); this client maps them to
CutCut sources from the studio's show setup, so the bridge never needs to know the studio.
It is also the fallback executor for the Companion executor: a direct cut (override, ``S5``)
or «Kun lyd» becomes an ``atem.cmd`` on the bus, answered by ``atem.ack``.

Nothing blocks: ``submit`` hands the command to ``send`` (the bus publisher) and returns.
"""

from __future__ import annotations

import itertools
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, ValidationError

from cutcut.common.ids import SourceId
from cutcut.common.models.multiview import MultiviewReadback
from cutcut.common.models.show import ShowConfig
from cutcut.core.inputs import AtemReadback
from cutcut.core.intents import DirectCut, Intent, SetPreview, ShowAudioOnly

log = logging.getLogger(__name__)

MP1: Final = 3010
SUPERSOURCE: Final = 6000
STALE_S: Final = 3.0  # the bridge sends at least once a second


def input_map(show: ShowConfig) -> dict[int, SourceId]:
    """ATEM input number → CutCut source, from the show (D-054: the studio decides)."""
    out: dict[int, SourceId] = {
        cam.atem_input: SourceId(cid.value) for cid, cam in show.cameras.items()
    }
    out[show.content.atem_input] = SourceId.LAPTOP
    out[SUPERSOURCE] = SourceId.SUPERSOURCE
    return out


def site_input_map(shows: list[ShowConfig]) -> dict[int, SourceId]:
    """The same, across all shows of the studio (the inputs do not change with the show)."""
    out: dict[int, SourceId] = {}
    for show in shows:
        out.update(input_map(show))
    return out


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class AtemMacroRaw(_Payload):
    number: int
    name: str


class AtemInputName(_Payload):
    number: int
    short: str = ""
    long: str = ""


class AtemIso(_Payload):
    """ISO recording on the ATEM's own disk (H-ATEM-4)."""

    state: str | None = None
    error: str | None = None
    time_available_s: float | None = None
    disk: str | None = None
    disk_status: str | None = None
    all_inputs: bool = False


class AtemStateRaw(_Payload):
    connected: bool = True
    model: str = "Unknown"
    program_input: int
    preview_input: int
    multiview: MultiviewReadback | None = None
    recording: str | None = None
    macros: list[AtemMacroRaw] = []
    inputs: list[AtemInputName] = []
    aux: list[str] = []
    iso: AtemIso | None = None


@dataclass
class AtemBridgeStatus:
    connected: bool
    model: str | None
    age_s: float | None
    sent: int
    failed: int
    last_error: str | None


@dataclass
class AtemBridgeClient:
    send: Callable[[str, dict[str, Any]], None]  # publish on the bus (``atem.cmd``)
    inputs: dict[int, SourceId] = field(default_factory=dict)
    clock: Callable[[], float] = time.monotonic

    _state: AtemStateRaw | None = field(init=False, default=None)
    _state_at: float | None = field(init=False, default=None)
    _connected: bool = field(init=False, default=False)
    _ids: itertools.count[int] = field(init=False, default_factory=itertools.count)
    _waiting: dict[str, str] = field(init=False, default_factory=dict)
    sent: int = field(init=False, default=0)
    failed: int = field(init=False, default=0)
    last_error: str | None = field(init=False, default=None)

    def use_show(self, show: ShowConfig) -> None:
        self.inputs = input_map(show)

    # -- from the bus ---------------------------------------------------------------------

    def on_message(self, topic: str, payload: dict[str, Any]) -> None:
        try:
            if topic == "atem.state":
                self._state = AtemStateRaw.model_validate(payload)
                self._state_at = self.clock()
                self._connected = self._state.connected
            elif topic == "atem.status":
                self._connected = bool(payload.get("connected"))
                if payload.get("last_error"):
                    self.last_error = str(payload["last_error"])
            elif topic == "atem.ack":
                what = self._waiting.pop(str(payload.get("id")), None)
                if what is not None and not payload.get("ok"):
                    self.failed += 1
                    self.last_error = f"{what}: {payload.get('error')}"
                    log.error("ATEM avviste %s: %s", what, payload.get("error"))
        except ValidationError as exc:
            log.warning("ugyldig %s fra atem-bridge: %s", topic, exc)

    # -- what the ATEM shows --------------------------------------------------------------

    def raw(self) -> AtemStateRaw | None:
        """The latest ``atem.state`` as ATEM input numbers (machine test, setup screen)."""
        return self._fresh()

    def macros(self) -> dict[int, str] | None:
        """Macros in the ATEM (number → name), or None while the bridge is not connected."""
        st = self._fresh()
        return None if st is None else {m.number: m.name for m in st.macros}

    def _fresh(self) -> AtemStateRaw | None:
        if not self._connected or self._state is None or self._state_at is None:
            return None
        if self.clock() - self._state_at > STALE_S:
            return None
        return self._state

    def _source(self, number: int) -> tuple[SourceId, str | None] | None:
        if number == MP1:
            return SourceId.SUPERSOURCE, "AUDIO_ONLY"  # «Kun lyd» graphic (spec 2.2, D-054)
        source = self.inputs.get(number)
        return (source, None) if source is not None else None

    def readback(self) -> AtemReadback | None:
        """None when the ATEM is not readable; core then makes no cuts (I1)."""
        st = self._fresh()
        if st is None:
            return None
        program = self._source(st.program_input)
        if program is None:
            return None  # something CutCut does not know (black, bars): leave it to people
        preview = self._source(st.preview_input)
        return AtemReadback(
            program=program[0],
            preview=preview[0] if preview else program[0],
            program_layout=program[1],
        )

    def multiview_readback(self) -> MultiviewReadback | None:
        st = self._fresh()
        return st.multiview if st else None

    def status(self) -> AtemBridgeStatus:
        age = None if self._state_at is None else self.clock() - self._state_at
        return AtemBridgeStatus(
            connected=self._fresh() is not None,
            model=self._state.model if self._state else None,
            age_s=age,
            sent=self.sent,
            failed=self.failed,
            last_error=self.last_error,
        )

    # -- commands (fallback executor for Companion, S5) ------------------------------------

    def submit(self, intent: Intent) -> None:
        match intent:
            case DirectCut(source=source):
                self._command("cut", self._number(source), f"kutt til {source}")
            case SetPreview(source=source):
                self._command("preview", self._number(source), f"preview {source}")
            case ShowAudioOnly():
                self._command("cut", MP1, "kun lyd")
            case _:
                log.info("atem-bridge tar ikke %s", type(intent).__name__)

    def set_input_name(self, number: int, long: str) -> bool:
        """«Fiks for meg» in setup step 3. The short name is the first four letters. Changes
        only the label; the picture on program and preview is not touched."""
        if self._fresh() is None:
            self.failed += 1
            self.last_error = f"navn på inngang {number}: ATEM er ikke tilkoblet"
            return False
        cid = f"a{next(self._ids)}"
        self._waiting[cid] = f"navn på inngang {number}"
        self.sent += 1
        args = {"input": number, "long": long[:20], "short": long[:4]}
        self.send("atem.cmd", {"id": cid, "op": "input_name", "args": args})
        return True

    def _number(self, source: SourceId) -> int | None:
        return next((n for n, s in self.inputs.items() if s is source), None)

    def _command(self, op: str, number: int | None, what: str) -> None:
        if number is None:
            self.failed += 1
            self.last_error = f"{what}: kilden finnes ikke i oppsettet"
            return
        if self._fresh() is None:
            self.failed += 1
            self.last_error = f"{what}: ATEM er ikke tilkoblet"
            return
        cid = f"a{next(self._ids)}"
        self._waiting[cid] = what
        del_old = [k for k in self._waiting if k != cid][:-50]
        for k in del_old:
            self._waiting.pop(k, None)  # never grow without bound
        self.sent += 1
        self.send("atem.cmd", {"id": cid, "op": op, "args": {"input": number}})
