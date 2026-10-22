"""Is the multiview set up the way CutCut reads it? (spec 2.1, 6.1; D-055)

Three checks, all pure functions so they run the same in tests, in the simulator and in studio:

1. ``check_map``: the rutekart against the studio's shows. Every camera CutCut can cut to must
   be read from the window that shows its ATEM input.
2. ``check_readback``: the rutekart against what the ATEM reports (atem-bridge, M2). Finds a
   window that shows the wrong input, a swapped preview/program, safe area or audio meters on.
3. ``recommended``: the optimal 2 + 8 layout for this studio, so the setup screen can show
   what to change and why.

Findings carry check IDs (``H-MV-n``) and Norwegian text for the technician.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from cutcut.common.config import Site
from cutcut.common.ids import SourceId
from cutcut.common.models.multiview import (
    SMALL_RECTS,
    MultiviewMap,
    MultiviewReadback,
    Tile,
    input_number,
    input_source,
)

Level = Literal["error", "warn", "info"]

SOURCE_NAMES = {
    "preview": "Preview",
    "program": "Program",
    "mediaplayer1": "Media Player 1",
    "mediaplayer2": "Media Player 2",
    "supersource": "SuperSource",
    "recording_status": "opptaksstatus",
    "streaming_status": "strømmestatus",
    "audio_meters": "lydmålere",
    "black": "svart",
    "colorbars": "fargestriper",
    "other": "annet",
}


@dataclass(frozen=True)
class Finding:
    check: str
    level: Level
    where: str
    message: str
    fix: str


def source_name(source: str) -> str:
    n = input_number(source)
    return f"Camera {n}" if n else SOURCE_NAMES.get(source, source)


@dataclass(frozen=True)
class StudioInputs:
    """Which ATEM input each CutCut source uses, from all shows in the studio."""

    inputs: dict[SourceId, int]
    names: dict[SourceId, str]

    @classmethod
    def from_site(cls, site: Site) -> StudioInputs:
        inputs: dict[SourceId, int] = {}
        names: dict[SourceId, str] = {}
        for show in site.shows.values():
            for p in show.participants:
                cam = show.cameras.get(p.camera)
                if cam is not None:
                    sid = SourceId(p.camera.value)
                    inputs[sid] = cam.atem_input
                    names[sid] = p.name.lower() if p.role == "host" else p.name
            for cid, cam in show.cameras.items():
                sid = SourceId(cid.value)
                inputs.setdefault(sid, cam.atem_input)
                if cam.role == "bird":
                    names[sid] = "fugleperspektivet"
                elif cam.role == "wide":
                    names[sid] = "halvtotalen"
            inputs[SourceId.LAPTOP] = show.content.atem_input
            names[SourceId.LAPTOP] = "laptopen"
        return cls(inputs, names)

    def name(self, sid: SourceId) -> str:
        return self.names.get(sid, sid.value)


def atem_input_names(site: Site) -> dict[int, str]:
    """ATEM input number → the name it should have: ``C1``–``C4``, ``BIRD``, ``LAPTOP``,
    ``C7`` (spec 8.4 step 3). The bird's-eye camera is called ``BIRD`` whatever its ID."""
    names: dict[int, str] = {}
    for show in site.shows.values():
        for cid, cam in show.cameras.items():
            names.setdefault(cam.atem_input, "BIRD" if cam.role == "bird" else cid.value)
        names.setdefault(show.content.atem_input, SourceId.LAPTOP.value)
    return dict(sorted(names.items()))


def recommended(studio: StudioInputs, switcher: str | None = None) -> MultiviewMap:
    """The optimal multiview for CutCut and for people (D-055):

    * preview left, program right (the normal ATEM order, and how the screens draw it);
    * row 1: the four close-up cameras in seat order, so the seats read left to right;
    * row 2: bird's-eye and laptop (CutCut reads both), then the half-total or SuperSource,
      then Media Player 1 with the «Kun lyd» graphic, so the technician sees what mode A shows.
    """
    order: list[tuple[str, SourceId | None]] = []
    for sid in (SourceId.C1, SourceId.C2, SourceId.C3, SourceId.C4):
        n = studio.inputs.get(sid)
        order.append((input_source(n), sid) if n else ("black", None))
    for sid in (SourceId.C5, SourceId.LAPTOP):
        n = studio.inputs.get(sid)
        order.append((input_source(n), sid) if n else ("black", None))
    if SourceId.C7 in studio.inputs:
        order.append((input_source(studio.inputs[SourceId.C7]), SourceId.C7))
        order.append(("supersource", SourceId.SUPERSOURCE))
    else:
        order.append(("supersource", SourceId.SUPERSOURCE))
        order.append(("mediaplayer1", None))
    tiles = [
        Tile(id="PVW", label="Preview", rect=(0.0, 0.0, 0.5, 0.5), source="preview"),
        Tile(id="PGM", label="Program", rect=(0.5, 0.0, 0.5, 0.5), source="program"),
    ]
    for i, ((source, camera), rect) in enumerate(zip(order, SMALL_RECTS, strict=True), start=1):
        tiles.append(
            Tile(id=f"W{i}", label=source_name(source), rect=rect, source=source, camera=camera)
        )
    return MultiviewMap(
        status="recommended",
        source="CutCut (anbefalt oppsett)",
        switcher=switcher,
        layout="2+8, preview venstre",
        tiles=tiles,
    )


Rect = tuple[float, float, float, float]


def suggest_map(
    big: tuple[Rect, Rect],
    small: Sequence[Rect],
    studio: StudioInputs,
    *,
    readback: MultiviewReadback | None,
    current: MultiviewMap | None,
    program_side: str | None = None,
    switcher: str | None = None,
) -> tuple[MultiviewMap, list[str]]:
    """A rutekart from the picture (where the windows are) and the ATEM (what they show).

    The windows come from :func:`cutcut.vision.grid.find_grid`. What each window shows comes
    from the ATEM when it can be read, otherwise from the rutekart in use, otherwise from the
    recommended layout. Returns the map and one Norwegian line per choice, for the screen.
    """
    notes: list[str] = []
    rec = recommended(studio, switcher)
    if readback is not None:
        sources = list(readback.windows)
        labels = list(readback.labels) if len(readback.labels) == 8 else []
        notes.append("Kildene i rutene er lest fra ATEM.")
    elif current is not None and len(current.small_windows()) == 8:
        sources = [t.source for t in current.small_windows()]
        labels = [t.label for t in current.small_windows()]
        notes.append("ATEM kan ikke leses nå: kildene er tatt fra rutekartet som brukes.")
    else:
        sources = [t.source for t in rec.small_windows()]
        labels = []
        notes.append("ATEM kan ikke leses nå: kildene er tatt fra det anbefalte oppsettet.")
    if readback is not None:
        preview_left = readback.preview_left
    elif program_side is not None:
        preview_left = program_side == "right"
        notes.append("Program er funnet på den røde tally-rammen.")
    else:
        preview_left = current.preview_left if current is not None else True
    by_input = {n: sid for sid, n in studio.inputs.items()}
    tiles = [
        Tile(id="PVW", label="Preview", rect=big[0 if preview_left else 1], source="preview"),
        Tile(id="PGM", label="Program", rect=big[1 if preview_left else 0], source="program"),
    ]
    for i, (source, rect) in enumerate(zip(sources, small, strict=True), start=1):
        n = input_number(source)
        camera: SourceId | None = by_input.get(n) if n is not None else None
        if source == "supersource" and SourceId.SUPERSOURCE in {t.camera for t in rec.tiles}:
            camera = SourceId.SUPERSOURCE
        label = labels[i - 1] if labels else source_name(source)
        tiles.append(Tile(id=f"W{i}", label=label, rect=rect, source=source, camera=camera))
    side = "venstre" if preview_left else "høyre"
    out = MultiviewMap(
        status="suggested",
        source="Forslag fra bildet i setup-hjelperen",
        switcher=switcher,
        layout=f"2+8, preview {side}",
        tiles=tiles,
    )
    return out, notes


def check_map(mv: MultiviewMap | None, studio: StudioInputs) -> list[Finding]:
    """The rutekart against the shows: CutCut must read each camera where its input is."""
    if mv is None:
        return [
            Finding(
                "H-MV-0",
                "error",
                "rutekart",
                "Studioet har ikke noe rutekart for multiview.",
                "Lag equipment/multiview_map.yaml fra det anbefalte oppsettet under.",
            )
        ]
    out: list[Finding] = []
    for sid, n in sorted(studio.inputs.items(), key=lambda kv: kv[1]):
        tile = next((t for t in mv.tiles if t.camera is sid), None)
        name = studio.name(sid)
        if tile is None:
            by_input = next((t for t in mv.tiles if t.source == input_source(n)), None)
            fix = (
                f"Merk rute {by_input.id} med camera: {sid.value}."
                if by_input
                else f"Legg Camera {n} i en ledig rute og merk den med camera: {sid.value}."
            )
            out.append(
                Finding("H-MV-1", "error", "rutekart", f"Rutekartet sier ikke hvor {name} er.", fix)
            )
        elif tile.source != input_source(n):
            out.append(
                Finding(
                    "H-MV-2",
                    "error",
                    f"rute {tile.id}",
                    f"Rute {tile.id} skal vise {name}, men viser {source_name(tile.source)}; "
                    f"{name} er på Camera {n}.",
                    f"Sett rute {tile.id} til Camera {n} (eller rett inngangen i show-oppsettet).",
                )
            )
    return out


def check_readback(mv: MultiviewMap, rb: MultiviewReadback | None) -> list[Finding]:
    """What the ATEM shows against the rutekart."""
    if rb is None:
        return [
            Finding(
                "H-MV-9",
                "info",
                "ATEM",
                "ATEM-multiviewen kan ikke leses ennå: atem-bridge har ikke svart.",
                "Sjekk ruten manuelt mot tabellen.",
            )
        ]
    out: list[Finding] = []
    if rb.layout != "2+8":
        out.append(
            Finding(
                "H-MV-3",
                "error",
                "layout",
                "Multiviewen har ikke 2 store og 8 små ruter.",
                "ATEM Software Control → Multiview → velg layouten med to store ruter øverst.",
            )
        )
        return out
    if rb.preview_left != mv.preview_left:
        out.append(
            Finding(
                "H-MV-4",
                "error",
                "preview/program",
                "Preview og program har byttet plass i forhold til rutekartet.",
                "ATEM Software Control → Multiview → «Swap program/preview».",
            )
        )
    for i, (tile, actual) in enumerate(zip(mv.small_windows(), rb.windows, strict=False), 1):
        if tile.source == actual:
            continue
        critical = tile.camera is not None
        out.append(
            Finding(
                "H-MV-5",
                "error" if critical else "warn",
                f"rute {tile.id}",
                f"Rute {i} viser {source_name(actual)}, men skal vise {source_name(tile.source)}"
                + (" – CutCut ville lest feil kamera." if critical else "."),
                f"ATEM Software Control → Multiview → rute {i}: {source_name(tile.source)}.",
            )
        )
    if rb.safe_area:
        out.append(
            Finding(
                "H-MV-6",
                "warn",
                "overlegg",
                "Safe area-merker er på i multiviewen. De gir støy i bildeanalysen.",
                "ATEM Software Control → Multiview → slå av «Safe area».",
            )
        )
    if rb.audio_meters:
        out.append(
            Finding(
                "H-MV-7",
                "warn",
                "overlegg",
                "Lydmålere er på i multiviewen. De dekker en del av bildet CutCut leser.",
                "ATEM Software Control → Multiview → slå av lydmålere.",
            )
        )
    if not rb.tally:
        out.append(
            Finding(
                "H-MV-8",
                "warn",
                "overlegg",
                "Tally-rammer er av. Da ser ingen i multiviewen hva som er på lufta.",
                "ATEM Software Control → Multiview → slå på tally.",
            )
        )
    if rb.video_mode != "1080p50":
        out.append(
            Finding(
                "H-MV-10",
                "warn",
                "format",
                f"Multiviewen går i {rb.video_mode}, studioet bruker 1080p50.",
                "Sett ATEM og multiview til 1080p50 (norsk lysnett, spesifikasjonen 2).",
            )
        )
    return out


def compare_recommended(mv: MultiviewMap, rec: MultiviewMap) -> list[Finding]:
    """Suggestions where the rutekart differs from the recommended layout (never errors)."""
    out: list[Finding] = []
    if mv.preview_left != rec.preview_left:
        out.append(
            Finding(
                "H-MV-11",
                "info",
                "preview/program",
                "Anbefalt: preview til venstre og program til høyre.",
                "Bytt plass i ATEM og i rutekartet samtidig.",
            )
        )
    for tile, want in zip(mv.small_windows(), rec.small_windows(), strict=False):
        if tile.source != want.source:
            out.append(
                Finding(
                    "H-MV-11",
                    "info",
                    f"rute {tile.id}",
                    f"Anbefalt i rute {tile.id[1:]}: {source_name(want.source)} "
                    f"(nå {source_name(tile.source)}).",
                    "Endre i ATEM og rutekartet samtidig, og kjør sjekken på nytt.",
                )
            )
    return out


def readback_from_map(mv: MultiviewMap, *, safe_area: bool = False) -> MultiviewReadback:
    """What a correctly set up ATEM reports. Used by the simulator's fake ATEM."""
    return MultiviewReadback(
        layout="2+8",
        preview_left=mv.preview_left,
        windows=[t.source for t in mv.small_windows()],
        labels=[t.label for t in mv.small_windows()],
        safe_area=safe_area,
    )
