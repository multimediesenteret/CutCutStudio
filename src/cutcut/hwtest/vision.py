"""Machine test for the capture card (VI-4, docs/plans/vision.md 5).

``cutcut hwtest vision --site C:\\CutCut\\site [--device N] [--user tekniker1]`` reads the ATEM
multiview through the capture device with the same code as ``cutcut vision``, and writes the
same report as the other machine tests. The device is the one for the capture method chosen in
the setup helper (D-071): the INOGENI 4KXUSB3 on the multiview output, or the ATEM's webcam
output over USB-C with Multi View chosen. ``--metode inogeni|atem_usb`` tests the other one
without changing the setting, so the two can be compared; ``--device`` picks a number instead.
Set the ATEM to 1080p50, and use a USB 3 port straight on the motherboard.

| Step | What |
| --- | --- |
| V1 | The card opens and delivers a picture |
| V2 | Format 1920 × 1080 and how many frames per second arrive (50 expected) |
| V3 | The rutekart fits: every window with a CutCut source has a picture |
| V4 | Delay ATEM → PC: the preview changes (Companion), and the preview window follows. The
  result is saved for the method tested (``video.delay_ms``), and the engine uses it |
| V5 | Stability: no lost frames, black pictures or re-opens over ``--minutes`` (60) |

V4 only changes PREVIEW, never what is on air, and needs CutCut and Companion running
(``--user``). Stop ``cutcut vision`` first (Helse → Prosesser, or the service): the card can
only be opened by one program at a time.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Protocol

import httpx

from cutcut.common.config import Site, load_site
from cutcut.common.ids import SourceId
from cutcut.common.models.multiview import MultiviewMap
from cutcut.common.models.site import CAPTURE_LABELS, CAPTURE_NAMES
from cutcut.devices.atem.bridge import site_input_map
from cutcut.devices.companion.client import CompanionHttp
from cutcut.hwtest.atem import companion_url, cutcut_session
from cutcut.hwtest.audio import ConsoleOperator, Operator
from cutcut.hwtest.report import Report, Result, Step
from cutcut.vision.capture import OpenCvSource, Source
from cutcut.vision.motion import match_program, thumb
from cutcut.vision.process import Vision

OPEN_S: Final = 5.0
FPS_S: Final = 5.0
FPS_OK: Final = 49.0
FPS_MIN: Final = 24.0
DELAY_ROUNDS: Final = 5
DELAY_WAIT_S: Final = 2.0
GAP_FRAMES: Final = 3  # a pause this many frame times long is a lost frame


class PreviewSwitch(Protocol):
    """Changes the ATEM preview and reads it back (Companion and CutCut, as in DA-5)."""

    def set(self, source: SourceId) -> None: ...
    def shown(self) -> SourceId | None: ...


@dataclass
class VisionTest:
    mv: MultiviewMap
    source: Source
    op: Operator
    switch: PreviewSwitch | None = None
    minutes: float = 60.0
    clock: Callable[[], float] = time.perf_counter
    sleep: Callable[[float], None] = time.sleep
    method: str | None = None  # the capture method tested (D-071), for the report
    save_delay: Callable[[int], bool] | None = None  # V4's result to CutCut (video.delay_ms)
    report: Report = field(init=False)
    fps: float = 0.0

    def __post_init__(self) -> None:
        self.report = Report("video", datetime.now().astimezone())
        self.report.env["source"] = self.source.name
        if self.method is not None:
            self.report.env["method"] = CAPTURE_LABELS.get(self.method, self.method)

    def _frame(self, within_s: float) -> Any:
        end = self.clock() + within_s
        while self.clock() < end:
            f = self.source.read()
            if f is not None:
                return f
            self.sleep(0.005)
        return None

    def run(self) -> Report:
        frame = self.step_open()
        if frame is None:
            for sid, title in (
                ("V2", "Format"),
                ("V3", "Rutekart"),
                ("V4", "Forsinkelse"),
                ("V5", "Stabilitet"),
            ):
                self.report.add(Step(sid, title, "hoppet over", "Ingen bilder fra kortet (V1)."))
            return self.report
        self.step_format(frame)
        self.step_tiles()
        self.step_delay()
        self.step_stability()
        return self.report

    def step_open(self) -> Any:
        f = self._frame(OPEN_S)
        if f is None:
            why = getattr(self.source, "last_error", None) or "ingen bilder"
            self.report.add(
                Step("V1", "Kortet", "feil", f"{self.source.name}: {why}. Kjører cutcut vision?")
            )
            return None
        self.report.add(Step("V1", "Kortet", "ok", f"{self.source.name} gir bilder."))
        return f

    def step_format(self, frame: Any) -> None:
        h, w = frame.shape[:2]
        n, t0 = 0, self.clock()
        while self.clock() - t0 < FPS_S:
            if self.source.read() is not None:
                n += 1
            else:
                self.sleep(0.001)
        self.fps = n / FPS_S
        details = {"width": w, "height": h, "fps": round(self.fps, 1)}
        res: Result = "ok"
        notes = []
        if (w, h) != (1920, 1080):
            res = "advarsel"
            notes.append(f"bildet er {w} × {h}, ikke 1920 × 1080")
        if self.fps < FPS_MIN:
            res = "feil"
            notes.append(f"bare {self.fps:.1f} bilder/s")
        elif self.fps < FPS_OK:
            res = "advarsel" if res == "ok" else res
            notes.append(f"{self.fps:.1f} bilder/s, ventet 50")
        msg = "; ".join(notes) if notes else f"{w} × {h}, {self.fps:.1f} bilder/s."
        self.report.add(Step("V2", "Format", res, msg[0].upper() + msg[1:], details))

    def step_tiles(self) -> None:
        v = Vision(self.mv)
        rows: list[dict[str, Any]] = []
        for _ in range(3):  # change needs two frames
            f = self._frame(1.0)
            if f is not None:
                rows = v.measure(f)
        by_tile = {r["tile"]: r for r in rows}
        missing = [
            f"{t.id} ({t.camera.value})"
            for t in self.mv.tiles
            if t.camera is not None and not by_tile.get(t.id, {}).get("signal", False)
        ]
        details = {"tiles": by_tile}
        if missing:
            msg = "Uten bilde: " + ", ".join(missing) + ". Riktig rutekart og multiview-layout?"
            self.report.add(Step("V3", "Rutekart", "advarsel", msg, details))
        else:
            n = sum(1 for t in self.mv.tiles if t.camera is not None)
            self.report.add(
                Step("V3", "Rutekart", "ok", f"Alle {n} kilderutene har bilde.", details)
            )

    def step_delay(self) -> None:
        title = "Forsinkelse"
        if self.switch is None:
            self.report.add(
                Step("V4", title, "hoppet over", "Trenger CutCut og Companion (--user).")
            )
            return
        cams = [
            t.camera for t in self.mv.tiles if t.camera is not None and t.camera.value[0] == "C"
        ]
        if len(cams) < 2:
            self.report.add(Step("V4", title, "hoppet over", "Trenger to kameraruter."))
            return
        if not self.op.wait("V4 bytter PREVIEW mellom to kameraer fem ganger (ikke program)."):
            self.report.add(Step("V4", title, "hoppet over", "Valgt bort."))
            return
        v = Vision(self.mv)
        a, b = cams[0], cams[1]
        delays: list[float] = []
        atem_ms: list[float] = []
        for i in range(DELAY_ROUNDS):
            want, other = (b, a) if i % 2 == 0 else (a, b)
            self.switch.set(other)
            self.sleep(1.0)
            t0 = self.clock()
            self.switch.set(want)
            t_atem = t_pic = None
            while self.clock() - t0 < DELAY_WAIT_S and (t_atem is None or t_pic is None):
                if t_atem is None and self.switch.shown() is want:
                    t_atem = self.clock()
                f = self.source.read()
                if f is None:
                    self.sleep(0.002)
                    continue
                v.measure(f)
                if t_pic is None and self._pvw_shows(v, f) is want:
                    t_pic = self.clock()
            if t_atem is not None and t_pic is not None:
                atem_ms.append((t_atem - t0) * 1000)
                delays.append((t_pic - t0) * 1000)
        details: dict[str, Any] = {
            "to_picture_ms": [round(d) for d in delays],
            "to_atem_ms": [round(d) for d in atem_ms],
        }
        if len(delays) < DELAY_ROUNDS // 2 + 1:
            msg = "Preview-ruta fulgte ikke med. Riktig rutekart for PVW?"
            self.report.add(Step("V4", title, "feil", msg, details))
            return
        pic, atem = statistics.median(delays), statistics.median(atem_ms)
        to_pc = round(max(0.0, pic - atem))
        details["atem_to_pc_ms"] = to_pc
        saved = ""
        if self.save_delay is not None and self.save_delay(to_pc):
            saved = " Lagret som forsinkelse for denne metoden; motoren bruker den."
        self.report.add(
            Step(
                "V4",
                title,
                "ok",
                f"Fra knapp til bilde på PC-en {pic:.0f} ms (ATEM leste preview etter "
                f"{atem:.0f} ms); ATEM → PC ca. {to_pc} ms.{saved}",
                details,
            )
        )

    def _pvw_shows(self, v: Vision, frame: Any) -> SourceId | None:
        pvw = next((m for m in v.meters if m.cut.tile.source == "preview"), None)
        if pvw is None:
            return None
        cams = {
            m.cut.tile.camera.value: thumb(m.cut.of(frame))
            for m in v.meters
            if m.cut.tile.camera is not None
        }
        got, _ = match_program(thumb(pvw.cut.of(frame)), cams)
        return SourceId(got) if got else None

    def step_stability(self) -> None:
        title = "Stabilitet"
        if not self.op.wait(f"V5 leser bilder i {self.minutes:g} minutter. La kortet være i fred."):
            self.report.add(Step("V5", title, "hoppet over", "Valgt bort."))
            return
        period = 1.0 / self.fps if self.fps else 0.02
        opened0 = getattr(self.source, "opened", 0)
        v = Vision(self.mv)
        frames = gaps = black = 0
        worst = 0.0
        last = t0 = self.clock()
        while self.clock() - t0 < self.minutes * 60:
            f = self.source.read()
            now = self.clock()
            if f is None:
                self.sleep(0.001)
                continue
            frames += 1
            gap = now - last
            worst = max(worst, gap)
            if frames > 1 and gap > GAP_FRAMES * period:
                gaps += 1
            last = now
            if frames % 50 == 0 and not any(r["signal"] for r in v.measure(f)):
                black += 1
        reopened = getattr(self.source, "opened", 0) - opened0
        details = {
            "frames": frames,
            "gaps": gaps,
            "black_checks": black,
            "reopened": reopened,
            "worst_gap_ms": round(worst * 1000),
        }
        if reopened or black:
            res: Result = "feil"
            msg = f"Kortet måtte åpnes på nytt {reopened} ganger, {black} svarte bilder."
        elif gaps:
            res, msg = (
                "advarsel",
                f"{gaps} pauser lengre enn {GAP_FRAMES} bilder (verst {worst * 1000:.0f} ms).",
            )
        else:
            res, msg = "ok", f"{frames} bilder på {self.minutes:g} min uten tapte bilder."
        self.report.add(Step("V5", title, res, msg, details))


@dataclass
class CompanionPreview:
    """V4 in the studio: preview buttons on Companion page 10, read back through CutCut."""

    site: Site
    api: httpx.Client
    companion: CompanionHttp

    def __post_init__(self) -> None:
        self.inputs = site_input_map(list(self.site.shows.values()))

    def set(self, source: SourceId) -> None:
        b = self.site.companion_map.preview.get(source)
        if b is not None:
            self.companion.press(self.site.devices.companion.engine_page, b.row, b.col)

    def shown(self) -> SourceId | None:
        n = self.api.get("/api/setup/atem").json().get("preview_input")
        return self.inputs.get(int(n)) if n is not None else None


def main(
    site_dir: Path,
    device: int | None,
    minutes: float,
    out: Path,
    api_url: str | None,
    user: str | None,
    method: str | None = None,
) -> int:
    site = load_site(site_dir)
    switch: PreviewSwitch | None = None
    api: httpx.Client | None = None
    if user is not None:
        api = cutcut_session(site, api_url, user)
        if api is None:
            return 2
        switch = CompanionPreview(site, api, CompanionHttp(companion_url(site, api)))
    if site.multiview is None:
        print("Studioet har ikke noe rutekart (equipment/multiview_map.yaml).")
        return 2
    video = site.devices.video
    chosen: str = video.method
    name = video.device_name
    if api is not None:  # what the setup helper says (the app's setting wins over the file)
        v = api.get("/api/settings/devices").json().get("video") or {}
        chosen, name = str(v.get("method") or chosen), str(v.get("name_used") or name)
    if method is not None and method != chosen:
        chosen, name = method, CAPTURE_NAMES[method]
    source = OpenCvSource(
        device if device is not None else video.index,
        width=video.width,
        height=video.height,
        fps=video.fps,
        device_name=None if device is not None else name,
    )
    print(
        f"Maskintest multiview inn · {CAPTURE_LABELS.get(chosen, chosen)} · {source.name} · "
        f"{len(site.multiview.tiles)} ruter"
    )

    def save_delay(ms: int) -> bool:
        if api is None:
            return False
        res = api.put("/api/settings/devices", json={f"video.delay_ms.{chosen}": str(ms)})
        return res.status_code == 200

    test = VisionTest(
        site.multiview,
        source,
        ConsoleOperator(),
        switch,
        minutes,
        method=chosen,
        save_delay=save_delay if api is not None else None,
    )
    locked = api is not None and api.post("/api/lock", json={"on": True}).status_code == 200
    try:
        report = test.run()
    finally:
        source.close()
        if api is not None and locked:
            api.post("/api/lock", json={"on": False})
    js, md = report.write(out)
    print("\n" + report.to_markdown())
    print(f"Rapport: {md} (lim inn i GitHub-issue VI-4) og {js}")
    return 0 if report.result != "feil" else 1
