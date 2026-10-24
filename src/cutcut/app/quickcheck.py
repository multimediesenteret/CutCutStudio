"""P14 «Sjekk dagens oppsett»: the checks that exist, in one go, in about two minutes.

Started by the technician (Helse). No new rules: it puts together what is there.

| Step | What | From |
| --- | --- | --- |
| Q1 Helse | Every check green, or explained | the health catalogue |
| Q2 Multiview | The ATEM multiview matches the rutekart | ``multiview_status`` |
| Q3 Navnerunde | Each says their name: mic heard and up, mouth in own camera (P12) | audio, video |
| Q4 Farge | Optional, grey card: each camera against the first, measured only (step 4) | cut-outs |

The result is one report, kept in the log (``quick_check``). Pure but for the callables the
studio hands it; driven by the studio's tick.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from cutcut.app.seatcheck import Seat, SeatCheck
from cutcut.common.ids import CameraId, MicId, ParticipantId, SourceId
from cutcut.core.inputs import MicFrame, TileFrame
from cutcut.health.model import CheckResult
from cutcut.setup.color import DONE, find_grey
from cutcut.vision.tiles import Frame

NAME_ROUND_MS: Final = 45_000  # at most this long for everyone to say their name
HEARD_MS: Final = 1_500  # a name, said alone
VOICED_DB: Final = -50.0

Result = Literal["ok", "advarsel", "feil", "hoppet over"]


@dataclass
class QuickStep:
    id: str
    title: str
    result: Result | None = None  # None: not run yet
    summary: str = ""

    def json(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "result": self.result, "summary": self.summary}


@dataclass
class QuickCheck:
    started_ms: int
    seats: dict[ParticipantId, Seat]
    names: dict[ParticipantId, str]
    health: Callable[[], list[CheckResult]]
    multiview: Callable[[], dict[str, Any]]
    grab: Callable[[CameraId], Frame | None] | None = None  # None: no colour step
    steps: list[QuickStep] = field(default_factory=list)
    phase: Literal["navnerunde", "ferdig"] = "navnerunde"
    heard_ms: dict[ParticipantId, int] = field(default_factory=dict)
    muted: set[ParticipantId] = field(default_factory=set)
    seat: SeatCheck | None = None
    video: bool = False

    def __post_init__(self) -> None:
        self.steps = [
            self._health(),
            self._multiview(),
            QuickStep("Q3", "Navnerunde", summary="Hver person sier navnet sitt, én om gangen."),
            QuickStep("Q4", "Farge"),
        ]
        self.seat = SeatCheck(dict(self.seats), min_solo_ms=HEARD_MS)

    # -- the instant steps -----------------------------------------------------------------

    def _health(self) -> QuickStep:
        rs = self.health()
        red = [r for r in rs if r.status == "red"]
        yellow = [r for r in rs if r.status == "yellow"]
        if red:
            names = ", ".join(r.id for r in red[:4])
            return QuickStep("Q1", "Helse", "feil", f"Rødt: {names}. Se Helse.")
        if yellow:
            names = ", ".join(r.id for r in yellow[:4])
            return QuickStep("Q1", "Helse", "advarsel", f"Gult: {names}.")
        return QuickStep("Q1", "Helse", "ok", f"Alle {len(rs)} sjekkene er grønne.")

    def _multiview(self) -> QuickStep:
        try:
            st = self.multiview()
        except Exception as exc:  # a check must never stop the studio
            return QuickStep("Q2", "Multiview", "feil", f"Kunne ikke sjekkes: {exc}")
        errors = [f for f in st.get("findings", []) if f.get("level") == "error"]
        if errors:
            return QuickStep("Q2", "Multiview", "feil", str(errors[0].get("message", "")))
        if st.get("readback") is None:
            return QuickStep("Q2", "Multiview", "advarsel", "ATEM-multiviewen kan ikke leses.")
        return QuickStep("Q2", "Multiview", "ok", "Multiviewen stemmer med rutekartet.")

    # -- the name round --------------------------------------------------------------------

    def tick(
        self,
        now: int,
        dt_ms: int,
        mics: Mapping[MicId, MicFrame],
        tiles: Mapping[SourceId, TileFrame] | None,
    ) -> None:
        if self.phase != "navnerunde":
            return
        self.video = self.video or tiles is not None
        talking = [p for p, s in self.seats.items() if _voiced(mics.get(s.mic))]
        if len(talking) == 1:
            pid = talking[0]
            self.heard_ms[pid] = self.heard_ms.get(pid, 0) + dt_ms
            if not mics[self.seats[pid].mic].in_main_mix:
                self.muted.add(pid)
        if self.seat is not None:
            self.seat.feed(dt_ms, mics, tiles)
        everyone = all(self.heard_ms.get(p, 0) >= HEARD_MS for p in self.seats)
        if everyone or now - self.started_ms >= NAME_ROUND_MS:
            self._finish()

    def _finish(self) -> None:
        self.phase = "ferdig"
        q3 = self.steps[2]
        silent = [self.names[p] for p in self.seats if self.heard_ms.get(p, 0) < HEARD_MS]
        muted = [self.names[p] for p in self.seats if p in self.muted]
        notes = []
        if silent:
            notes.append(f"Ikke hørt: {', '.join(silent)}.")
        if muted:
            notes.append(f"Skrudd ned på mikseren: {', '.join(muted)}.")
        if self.seat is not None and self.video:
            for f in self.seat.findings():
                who = self.names.get(f.pid, f.pid.value)
                if f.kind == "empty":
                    notes.append(f"Kamera {f.expected.value[1:]} ser ikke {who}.")
                elif f.seen is not None:
                    notes.append(f"{who} ser ut til å sitte ved kamera {f.seen.value[1:]}.")
        elif not self.video:
            notes.append("Videolaget kjører ikke, så plassene ble ikke sjekket.")
        q3.result = "feil" if silent or muted else ("advarsel" if notes else "ok")
        q3.summary = (
            " ".join(notes) if notes else "Alle ble hørt, og alle sitter foran sitt kamera."
        )
        self.steps[3] = self._color()

    def _color(self) -> QuickStep:
        if self.grab is None:
            return QuickStep("Q4", "Farge", "hoppet over", "Valgt bort (krever gråkort).")
        cams = sorted({s.camera for s in self.seats.values()}, key=lambda c: c.value)
        patches = {c: (find_grey(img) if (img := self.grab(c)) is not None else None) for c in cams}
        ref_cam = cams[0] if cams else None
        ref = patches.get(ref_cam) if ref_cam is not None else None
        if ref is None or ref_cam is None:
            return QuickStep("Q4", "Farge", "feil", "Fant ikke gråkortet hos referansekameraet.")
        off = []
        for c, p in patches.items():
            if c == ref_cam:
                continue
            if p is None:
                off.append(f"{c.value}: fant ikke kortet")
                continue
            rb = abs(math.log(p.rb / ref.rb))
            luma = abs(math.log(max(p.luma, 1e-3) / ref.luma))
            if rb >= DONE or luma >= DONE:
                off.append(f"{c.value}: {rb * 100:.0f} % i farge, {luma * 100:.0f} % i lys")
        if off:
            return QuickStep(
                "Q4", "Farge", "advarsel", "Ulik referansen: " + "; ".join(off) + ". Kjør steg 4."
            )
        return QuickStep("Q4", "Farge", "ok", f"Alle kameraene er like {ref_cam.value}.")

    # -- the report ------------------------------------------------------------------------

    @property
    def result(self) -> Result | None:
        rs = [s.result for s in self.steps]
        if self.phase != "ferdig":
            return None
        if "feil" in rs:
            return "feil"
        if "advarsel" in rs:
            return "advarsel"
        return "ok"

    def json(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "result": self.result,
            "steps": [s.json() for s in self.steps],
            "waiting_for": [self.names[p] for p in self.seats if self.heard_ms.get(p, 0) < HEARD_MS]
            if self.phase == "navnerunde"
            else [],
        }


def _voiced(f: MicFrame | None) -> bool:
    return f is not None and f.vad >= 0.5 and f.level_db > VOICED_DB and not f.leak
