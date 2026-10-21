"""VI-4: the capture-card machine test against the drawn multiview on a fake clock."""

from __future__ import annotations

from typing import Any

from cutcut.common.ids import SourceId
from cutcut.hwtest.report import Report
from cutcut.hwtest.vision import VisionTest
from cutcut.vision.capture import SyntheticSource
from tests.unit.hwtest.test_camera import Yes
from tests.unit.vision.test_vision import MV

TILE = {t.camera: t.id for t in MV.tiles if t.camera is not None}


class Clock:
    t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


class Card:
    """The drawn multiview as a 50 fps card: every read moves the clock one frame on."""

    name = "test"

    def __init__(self, clock: Clock, *, fps: float = 50.0, size: tuple[int, int] = (1920, 1080)):
        self.clock = clock
        self.src = SyntheticSource(MV, width=size[0], height=size[1])
        self.src.preview = "W1"
        self.period = 1 / fps
        self.opened = 1
        self.dead = False
        self.hiccup_at: float | None = None
        self.preview_at: tuple[float, str] | None = None
        self.hiccup_in_v5 = False
        self._frames: dict[str, Any] = {}  # drawing 1080p is slow: one frame per preview

    def read(self) -> Any:
        self.clock.t += self.period
        if self.dead:
            return None
        if self.hiccup_at is not None and self.clock.t >= self.hiccup_at:
            self.hiccup_at = None
            self.clock.t += 0.5  # half a second without frames
        if self.preview_at is not None and self.clock.t >= self.preview_at[0]:
            self.src.preview = self.preview_at[1]
            self.preview_at = None
        key = self.src.preview or ""
        if key not in self._frames:
            self._frames[key] = self.src.read()
        return self._frames[key]

    def close(self) -> None:
        pass


class Switch:
    """Companion and the ATEM: the ATEM reads the new preview after 30 ms, the card shows it
    after 100 ms."""

    def __init__(self, clock: Clock, card: Card) -> None:
        self.clock, self.card = clock, card
        self.want: tuple[float, SourceId] | None = None
        self.now = SourceId.C1

    def set(self, source: SourceId) -> None:
        self.want = (self.clock.t, source)
        self.card.preview_at = (self.clock.t + 0.1, TILE[source])

    def shown(self) -> SourceId | None:
        if self.want is not None and self.clock.t - self.want[0] >= 0.03:
            self.now = self.want[1]
        return self.now


def run(card_kw: dict[str, Any] | None = None, *, switch: bool = True, **kw: Any) -> Report:
    clock = Clock()
    card = Card(clock, **(card_kw or {}))
    for k, v in kw.items():
        setattr(card, k, v)

    class Op(Yes):
        def wait(self, text: str) -> bool:
            if text.startswith("V5") and card.hiccup_in_v5:
                card.hiccup_at = clock.t + 1.0
            return super().wait(text)

    test = VisionTest(
        MV,
        card,
        Op(),
        Switch(clock, card) if switch else None,
        minutes=0.1,
        clock=clock,
        sleep=clock.sleep,
    )
    return test.run()


def results(r: Report) -> dict[str, str]:
    return {s.id: s.result for s in r.steps}


def test_a_good_card_passes() -> None:
    r = run()
    assert results(r) == {f"V{i}": "ok" for i in range(1, 6)}, r.to_markdown()
    v4 = next(s for s in r.steps if s.id == "V4")
    # 100 ms to the picture, 30 ms to the ATEM, both seen on the next 20 ms frame
    assert "ATEM → PC ca. 80 ms" in v4.summary


def test_wrong_format_and_slow_card() -> None:
    r = run({"fps": 25.0, "size": (1280, 720)})
    v2 = next(s for s in r.steps if s.id == "V2")
    assert v2.result == "advarsel"
    assert "1280 × 720" in v2.summary
    assert "25.0 bilder/s" in v2.summary


def test_lost_frames_are_found() -> None:
    r = run(hiccup_in_v5=True)
    v5 = next(s for s in r.steps if s.id == "V5")
    assert v5.result == "advarsel", r.to_markdown()
    assert v5.details["gaps"] == 1


def test_without_cutcut_the_delay_is_skipped() -> None:
    r = run(switch=False)
    assert results(r)["V4"] == "hoppet over"


def test_no_picture() -> None:
    r = run(dead=True)
    assert results(r)["V1"] == "feil"
    assert r.result == "feil"
