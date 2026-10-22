"""Colour matching with a grey card (spec 6.4, setup step 4, P8, F-10).

Only on request from the setup page, with a grey card in front of every camera. Each round
the grey card is found in every camera window, its colour (red against blue) and brightness
are measured, and each camera is adjusted towards the reference camera: white balance in
kelvin for the colour, gain for the brightness. 3–5 rounds, until the difference is under
3 %. A camera on program or preview is never adjusted: the camera guard refuses it (I2), and
it is reported as skipped.

Finding the card: the picture is split into small blocks; a grey card is a group of blocks
that are even (little noise), without colour (low saturation) and neither dark nor burnt
out. The middle of those blocks is the card.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final

import numpy as np

from cutcut.common.ids import CameraId
from cutcut.vision.tiles import Frame

BLOCK: Final = 8  # pixels per block side, after scaling to 160 wide
EVEN_STD: Final = 6.0  # a card block varies less than this (0–255)
GREY_SAT: Final = 0.22  # (max − min) / mean of the channels
LUMA: Final = (50.0, 215.0)
MIN_SHARE: Final = 0.02  # the card must cover at least this share of the window
DONE: Final = 0.03  # within 3 % in colour and brightness
KELVIN_PER_LOG: Final = 3000.0  # how far the white balance moves per unit of log(r/b) error
DAMPING: Final = 0.8
KELVIN: Final = (2000, 10000)
GAIN_DB: Final = (-6.0, 18.0)
GAIN_STEP_MAX: Final = 6.0
ROUNDS: Final = 5
SETTLE_S: Final = 1.5  # the camera and the video layer need a moment after a change


@dataclass(frozen=True)
class Patch:
    """The grey card in one window: mean colour (BGR as OpenCV gives it) and brightness."""

    r: float
    g: float
    b: float
    share: float  # how much of the window it covers

    @property
    def luma(self) -> float:
        return 0.299 * self.r + 0.587 * self.g + 0.114 * self.b

    @property
    def rb(self) -> float:
        return self.r / max(self.b, 1e-3)


def find_grey(img: Frame) -> Patch | None:
    """The grey card, or ``None`` when no even, grey area large enough is found."""
    step = max(1, img.shape[1] // 160)
    small = img[::step, ::step].astype(np.float32)
    sh, sw = small.shape[:2]
    by, bx = sh // BLOCK, sw // BLOCK
    if by == 0 or bx == 0:
        return None
    blocks = small[: by * BLOCK, : bx * BLOCK].reshape(by, BLOCK, bx, BLOCK, 3)
    mean = blocks.mean(axis=(1, 3))  # by × bx × 3 (BGR)
    std = blocks.std(axis=(1, 3)).mean(axis=2)
    m = mean.mean(axis=2)
    sat = (mean.max(axis=2) - mean.min(axis=2)) / np.maximum(m, 1)
    ok = (std < EVEN_STD) & (sat < GREY_SAT) & (m > LUMA[0]) & (m < LUMA[1])
    count = int(ok.sum())
    if count / (by * bx) < MIN_SHARE:
        return None
    # the biggest group: the blocks nearest the median colour of the candidates
    cand = mean[ok]
    med = np.median(cand, axis=0)
    close = np.abs(cand - med).max(axis=1) < 12
    chosen = cand[close] if int(close.sum()) else cand
    b, g, r = (float(v) for v in chosen.mean(axis=0))
    return Patch(r=r, g=g, b=b, share=round(len(chosen) / (by * bx), 3))


@dataclass
class CameraColor:
    """Where one camera is, and how the matching went."""

    kelvin: int = 5600
    gain_db: float = 0.0
    error_rb: float | None = None  # log(r/b) against the reference
    error_luma: float | None = None  # log(brightness) against the reference
    state: str = "venter"  # venter, justerer, ferdig, hoppet over, fant ikke kortet
    rounds: int = 0


Grab = Callable[[CameraId], Frame | None]
Apply = Callable[[CameraId, int, float], str | None]  # the guard's verdict: "queued" or why not


@dataclass
class ColorMatcher:
    reference: CameraId
    cameras: dict[CameraId, CameraColor]
    grab: Grab
    apply: Apply
    rounds: int = ROUNDS
    settle_s: float = SETTLE_S
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    state: str = "klar"  # klar, måler, ferdig, feil
    message: str | None = None
    round: int = 0
    log: list[str] = field(default_factory=list)

    async def run(self) -> None:
        self.state = "måler"
        for n in range(1, self.rounds + 1):
            self.round = n
            ref_img = self.grab(self.reference)
            ref = find_grey(ref_img) if ref_img is not None else None
            if ref is None:
                self.state = "feil"
                self.message = (
                    f"Fant ikke gråkortet hos referansekameraet {self.reference.value}. Hold "
                    "kortet midt i bildet, godt lyst, og prøv igjen."
                )
                return
            pending = [c for c, s in self.cameras.items() if s.state in ("venter", "justerer")]
            if not pending:
                break
            for cam in pending:
                self._one(cam, ref)
            if all(s.state not in ("venter", "justerer") for s in self.cameras.values()):
                break
            await self.sleep(self.settle_s)
        for s in self.cameras.values():
            if s.state == "justerer":
                s.state = f"ikke helt likt etter {self.rounds} runder"
        self.state = "ferdig"
        done = sum(s.state == "ferdig" for s in self.cameras.values())
        self.message = f"{done} av {len(self.cameras)} kameraer er like referansen."

    def _one(self, cam: CameraId, ref: Patch) -> None:
        s = self.cameras[cam]
        img = self.grab(cam)
        p = find_grey(img) if img is not None else None
        if p is None:
            s.state = "fant ikke kortet"
            return
        s.rounds += 1
        s.error_rb = round(math.log(p.rb / ref.rb), 4)
        s.error_luma = round(math.log(max(p.luma, 1e-3) / ref.luma), 4)
        if abs(s.error_rb) < DONE and abs(s.error_luma) < DONE:
            s.state = "ferdig"
            return
        # warmer than the reference (more red) → lower kelvin; darker → more gain
        kelvin = s.kelvin - DAMPING * KELVIN_PER_LOG * s.error_rb
        kelvin = int(round(min(max(kelvin, KELVIN[0]), KELVIN[1]) / 50) * 50)
        step = -20 * s.error_luma / math.log(10) * DAMPING
        step = min(max(step, -GAIN_STEP_MAX), GAIN_STEP_MAX)
        gain = round(min(max(s.gain_db + step, GAIN_DB[0]), GAIN_DB[1]), 1)
        verdict = self.apply(cam, kelvin, gain)
        if verdict != "queued":
            s.state = "hoppet over"  # on air (I2), or the camera does not answer
            self.log.append(f"{cam.value}: {verdict}")
            return
        s.kelvin, s.gain_db, s.state = kelvin, gain, "justerer"
        self.log.append(f"{cam.value}: {kelvin} K, {gain:+.1f} dB")

    def status(self) -> dict[str, object]:
        return {
            "state": self.state,
            "reference": self.reference.value,
            "round": self.round,
            "rounds": self.rounds,
            "message": self.message,
            "cameras": {
                c.value: {
                    "kelvin": s.kelvin,
                    "gain_db": s.gain_db,
                    "error_rb": s.error_rb,
                    "error_luma": s.error_luma,
                    "state": s.state,
                    "rounds": s.rounds,
                }
                for c, s in self.cameras.items()
            },
        }
