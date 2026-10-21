"""The multiview contract between the ATEM and CutCut (spec 2.1, 6.1).

``site/<studio>/equipment/multiview_map.yaml`` says where each window is and what it shows.
The video layer reads tiles by position, so if the ATEM multiview does not match the map,
CutCut would look at the wrong camera. :mod:`cutcut.setup.multiview` compares the map with
the studio's shows, with what the ATEM reports, and with the recommended layout.
"""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cutcut.common.ids import SourceId

# What a multiview window can show, in the names atem-bridge reports (ADR-0012).
SOURCE_PATTERN = (
    r"^(preview|program|input[1-8]|mediaplayer[12]|supersource|recording_status"
    r"|streaming_status|audio_meters|black|colorbars|other)$"
)


def input_source(atem_input: int) -> str:
    return f"input{atem_input}"


def input_number(source: str) -> int | None:
    m = re.fullmatch(r"input([1-8])", source)
    return int(m.group(1)) if m else None


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Tile(_Strict):
    id: str = Field(pattern=r"^(PVW|PGM|W[1-8])$")
    label: str = ""
    rect: tuple[float, float, float, float]  # x, y, width, height as share of the picture
    source: str = Field(pattern=SOURCE_PATTERN)
    camera: SourceId | None = None  # which CutCut source the video layer reads here

    @model_validator(mode="after")
    def _inside(self) -> Self:
        x, y, w, h = self.rect
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 1.0001 or y + h > 1.0001:
            raise ValueError(f"tile {self.id}: rect must lie inside the picture (0–1)")
        supersource = self.camera is SourceId.SUPERSOURCE and self.source == "supersource"
        if self.camera is not None and input_number(self.source) is None and not supersource:
            raise ValueError(f"tile {self.id}: camera {self.camera} needs an input source")
        return self


class MultiviewMap(_Strict):
    schema_version: int = 1
    status: str = "draft"
    source: str = ""
    switcher: str | None = None
    layout: str = "2+8, preview venstre"
    tiles: list[Tile]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [t.id for t in self.tiles]
        if len(set(ids)) != len(ids):
            raise ValueError("every tile id must be unique")
        for need in ("preview", "program"):
            if sum(t.source == need for t in self.tiles) != 1:
                raise ValueError(f"the map needs exactly one {need} window")
        cams = [t.camera for t in self.tiles if t.camera is not None]
        if len(set(cams)) != len(cams):
            raise ValueError("a camera can only be read from one tile")
        for i, a in enumerate(self.tiles):
            for b in self.tiles[i + 1 :]:
                if _overlap(a.rect, b.rect):
                    raise ValueError(f"tiles {a.id} and {b.id} overlap")
        return self

    def tile(self, tile_id: str) -> Tile | None:
        return next((t for t in self.tiles if t.id == tile_id), None)

    @property
    def preview_left(self) -> bool:
        pvw = next(t for t in self.tiles if t.source == "preview")
        pgm = next(t for t in self.tiles if t.source == "program")
        return pvw.rect[0] < pgm.rect[0]

    def small_windows(self) -> list[Tile]:
        return sorted((t for t in self.tiles if t.id.startswith("W")), key=lambda t: t.id)


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    eps = 1e-6
    return (
        a[0] + a[2] > b[0] + eps
        and b[0] + b[2] > a[0] + eps
        and a[1] + a[3] > b[1] + eps
        and b[1] + b[3] > a[1] + eps
    )


class MultiviewReadback(_Strict):
    """What the ATEM says its multiview is (atem-bridge in M2; FakeAtem in the simulator)."""

    layout: Literal["2+8", "other"] = "2+8"
    preview_left: bool = True
    windows: list[str] = Field(min_length=8, max_length=8)  # small windows 1–8, in order
    labels: list[str] = Field(default_factory=list)  # input names shown, same order
    safe_area: bool = False
    audio_meters: bool = False
    tally: bool = True
    video_mode: str = "1080p50"


# Grid of the 2 + 8 layout, the only one CutCut supports in v1 (spec 2.1).
SMALL_RECTS: tuple[tuple[float, float, float, float], ...] = tuple(
    (col * 0.25, 0.5 + row * 0.25, 0.25, 0.25) for row in range(2) for col in range(4)
)
