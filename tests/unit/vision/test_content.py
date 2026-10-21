"""VI-2: content detection on the laptop tile (spec 6.2), and the 10.4 criteria:
«ny slide vises innen 1 s; laptop koblet fra fjernes fra utvalget innen 1 s»."""

from __future__ import annotations

import asyncio
from typing import Any

from cutcut.core.inputs import ContentState
from cutcut.vision.capture import SyntheticSource
from cutcut.vision.content import ContentDetector
from cutcut.vision.process import Vision, run
from tests.unit.vision.test_vision import MV

S = ContentState
FRAME_MS = 1000 / 15


class Film:
    """The laptop tile at 15 frames/s; returns the content state after each frame."""

    def __init__(self, content: str = "slide") -> None:
        self.src = SyntheticSource(MV, content=content)  # type: ignore[arg-type]
        self.vision = Vision(MV)
        self.t = 0.0
        self.states: list[tuple[int, ContentState]] = []

    def play(self, seconds: float) -> ContentState:
        for _ in range(round(seconds * 15)):
            self.t += FRAME_MS
            frame = self.src.read()
            assert frame is not None
            out = self.vision.content_state(int(self.t), self.vision.measure(frame))
            assert out is not None
            self.states.append((int(self.t), ContentState(out["state"])))
        return self.states[-1][1]

    def first(self, state: ContentState, after_ms: float) -> float | None:
        """ms from ``after_ms`` until ``state`` was first reported."""
        for t, s in self.states:
            if t > after_ms and s is state:
                return t - after_ms
        return None


def test_a_slide_on_the_laptop_is_static() -> None:
    f = Film("slide")
    assert f.play(2) is S.STATIC


def test_a_new_slide_within_1_s_10_4() -> None:
    f = Film("slide")
    f.play(3)
    changed_at = f.t
    f.src.slide += 1
    f.play(3)
    took = f.first(S.NEW_SLIDE, changed_at)
    assert took is not None
    assert took <= 1000
    assert f.states[-1][1] is S.STATIC  # back to static after the hold
    assert f.vision.content.changed_ratio == 0.0


def test_unplugged_laptop_within_1_s_10_4() -> None:
    f = Film("slide")
    f.play(2)
    at = f.t
    f.src.content = "none"
    f.play(2)
    took = f.first(S.NO_SIGNAL, at)
    assert took is not None
    assert took <= 1000
    f.src.content = "desktop"  # plugged in again
    f.play(1)
    assert f.states[-1][1] is S.STATIC


def test_video_needs_a_second_of_movement() -> None:
    f = Film("slide")
    f.play(2)
    at = f.t
    f.src.content = "video"
    f.play(0.6)
    assert f.states[-1][1] is not S.VIDEO
    f.play(1.0)
    took = f.first(S.VIDEO, at)
    assert took is not None
    assert 800 <= took <= 1300
    f.src.content = "slide"
    f.play(2)
    assert f.states[-1][1] in (S.STATIC, S.NEW_SLIDE)


def test_a_moving_mouse_is_not_a_new_slide() -> None:
    f = Film("cursor")
    f.play(4)
    assert S.NEW_SLIDE not in {s for _, s in f.states}
    assert S.VIDEO not in {s for _, s in f.states}


def test_a_short_flicker_to_black_is_not_unplugged() -> None:
    d = ContentDetector()
    for t in range(0, 1000, 66):
        d.feed(t, True, 0.0)
    assert d.state is S.STATIC
    d.feed(1066, False, 0.0)
    d.feed(1133, False, 0.0)  # 133 ms black: an input switch, not an unplug
    assert d.feed(1200, True, 0.0) is S.STATIC


def test_the_loop_publishes_content_on_change() -> None:
    sent: list[tuple[str, dict[str, Any]]] = []

    async def publish(topic: str, payload: dict[str, Any]) -> None:
        sent.append((topic, payload))

    t = [0.0]
    src = SyntheticSource(MV, content="slide")
    count = [0]

    def on_frame(*_: Any) -> None:
        t[0] += 1 / 15
        count[0] += 1
        if count[0] == 30:
            src.slide += 1

    asyncio.run(
        run(src, MV, publish, max_frames=60, realtime=False, on_frame=on_frame, clock=lambda: t[0])
    )
    states = [p["state"] for topic, p in sent if topic == "vision.content"]
    assert "STATIC" in states
    assert "NEW_SLIDE" in states


def test_core_reads_what_the_video_layer_sends() -> None:
    from cutcut.core.messages import content_state

    f = Film("slide")
    f.play(1)
    out = f.vision.content_state(int(f.t) + 66, f.vision.measure(f.src.read()))  # type: ignore[arg-type]
    assert out is not None
    assert content_state(out) is S.STATIC
