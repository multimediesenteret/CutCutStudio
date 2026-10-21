"""In-process fake devices for the simulator and tests (SIM-3, SIM-4).

They react to the engine's intents the way the real devices would, and can be told to
fail. Network-level fakes (HTTP Companion and Pearl, VISCA cameras) are added next to the
real clients in M2, sharing these state machines.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cutcut.common.ids import SourceId
from cutcut.common.models.multiview import MultiviewReadback
from cutcut.common.models.session import RecordingStatus
from cutcut.core.inputs import AtemReadback
from cutcut.core.intents import (
    DirectCut,
    Intent,
    PrepareLayout,
    SetCompanionVariable,
    SetPreview,
    ShowAudioOnly,
    Take,
)
from cutcut.devices.atem.macros import LAYOUT_MACROS


@dataclass
class FakeAtem:
    """ATEM switched through Companion (ADR-0009). ``Take`` swaps preview to program."""

    program: SourceId = SourceId.C5
    preview: SourceId = SourceId.C5
    program_layout: str | None = None
    preview_layout: str | None = None
    online: bool = True
    companion_online: bool = True
    companion_vars: dict[str, str] = field(default_factory=dict)
    commands: int = 0
    dropped: int = 0
    multiview: MultiviewReadback | None = None  # what atem-bridge will read in M2
    macro_list: dict[int, str] = field(
        default_factory=lambda: {m.number: m.name for m in LAYOUT_MACROS}
    )  # all layout macros in place (spec 7.2)

    def submit(self, intent: Intent) -> None:
        if not self.online:
            self.dropped += 1
            return
        if not self.companion_online and not isinstance(intent, DirectCut):
            self.dropped += 1  # S5: only direct cuts via atem-bridge get through
            return
        self.commands += 1
        match intent:
            case SetPreview(source=source):
                self.preview, self.preview_layout = source, None
            case PrepareLayout(shot=shot):
                self.preview, self.preview_layout = SourceId.SUPERSOURCE, shot
            case Take():
                self.program, self.preview = self.preview, self.program
                self.program_layout, self.preview_layout = self.preview_layout, self.program_layout
            case DirectCut(source=source):
                self.program, self.program_layout = source, None
            case ShowAudioOnly():
                self.program, self.program_layout = SourceId.SUPERSOURCE, "AUDIO_ONLY"
            case SetCompanionVariable(name=name, value=value):
                self.companion_vars[name] = value

    def operator_cut(self, source: SourceId) -> None:
        """A person presses a button on the ATEM or Stream Deck (I5)."""
        self.program, self.program_layout = source, None

    def multiview_readback(self) -> MultiviewReadback | None:
        return self.multiview if self.online else None

    def macros(self) -> dict[int, str] | None:
        return dict(self.macro_list) if self.online else None

    def readback(self) -> AtemReadback | None:
        if not self.online:
            return None
        return AtemReadback(self.program, self.preview, self.program_layout)


@dataclass
class FakePearl:
    """Epiphan Pearl recorder state (spec 7.4): start/stop are asynchronous and idempotent."""

    state: RecordingStatus = RecordingStatus.STOPPED
    online: bool = True
    storage_minutes: int = 600
    started_at: int | None = None
    _pending: tuple[RecordingStatus, int] | None = None
    start_delay_ms: int = 800

    def start(self, now: int) -> bool:
        if not self.online:
            return False
        if self.state in (RecordingStatus.STARTED, RecordingStatus.STARTING):
            return True
        self.state = RecordingStatus.STARTING
        self._pending = (RecordingStatus.STARTED, now + self.start_delay_ms)
        return True

    def stop(self, now: int) -> bool:
        if not self.online:
            return False
        self.state, self._pending, self.started_at = RecordingStatus.STOPPED, None, None
        return True

    def fail(self) -> None:
        """The recorder stops by itself (disk, signal) – must be alarmed, never restarted (I7)."""
        self.state, self._pending = RecordingStatus.ERROR, None

    def update(self, now: int) -> None:
        if self._pending is not None and now >= self._pending[1]:
            self.state, self._pending = self._pending[0], None
            self.started_at = now

    def duration_s(self, now: int) -> int:
        if self.state is not RecordingStatus.STARTED or self.started_at is None:
            return 0
        return (now - self.started_at) // 1000


@dataclass
class FakeCardReader:
    """ELATEC TWN3 in COM-port mode. Only the fictional test cards exist here (I8)."""

    connected: bool = True
    queue: list[str] = field(default_factory=list)

    def present(self, card: str) -> None:
        self.queue.append(card)

    def read(self) -> str | None:
        if not self.connected or not self.queue:
            return None
        return self.queue.pop(0)


TEST_CARDS: dict[str, tuple[str, str]] = {
    # fictional hex UID -> (username, display name). Never real people or cards.
    "04A1B2C3": ("testa", "Testkort A"),
    "04D4E5F6": ("testb", "Testkort B"),
}


@dataclass
class FakeNtnuApi:
    online: bool = True
    latency_ms: int = 300

    def lookup(self, card_hex: str) -> tuple[str, str] | None:
        if not self.online:
            raise TimeoutError("NTNU-API svarer ikke")
        return TEST_CARDS.get(card_hex.upper())
