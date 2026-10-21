"""Content detection on the laptop tile (VI-2, spec 6.2).

Four states, from the tile's brightness and how much of it changed since the last frame:

| State | When |
| --- | --- |
| ``NO_SIGNAL`` | The tile is (nearly) black for 0.3 s: laptop unplugged or asleep |
| ``STATIC`` | A picture, little change |
| ``NEW_SLIDE`` | A big change (over 15 % of the pixels), then a still picture for 0.5 s; held 2 s |
| ``VIDEO`` | Movement in most frames for 1 s |

Laptop audio on ``M5`` also counts as video (CT3, CT5), but that is the engine's to combine: the
video layer only looks. Times are in ms so the detector works at any frame rate.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Final

from cutcut.core.inputs import ContentState

BLACK_MS: Final = 300
BIG_CHANGE: Final = 0.15  # spec 6.2: over 15 % of the pixels
STILL_CHANGE: Final = 0.01
MOVING_CHANGE: Final = 0.02
STILL_MS: Final = 500  # spec 6.2: still for 0.5 s after the change
VIDEO_MS: Final = 1_000  # spec 6.2: movement for 1 s
VIDEO_SHARE: Final = 0.7  # «sustained»: most frames in the last second moved
SLIDE_HOLD_MS: Final = 2_000


@dataclass
class ContentDetector:
    state: ContentState = ContentState.NO_SIGNAL
    changed_ratio: float = 0.0
    _black_since: int | None = None
    _signal_since: int | None = None
    _burst_at: int | None = None  # last big change, waiting for a still picture
    _burst_ratio: float = 0.0
    _still_since: int | None = None
    _slide_until: int = 0
    _recent: deque[tuple[int, float]] = field(default_factory=deque)

    def feed(self, now: int, signal: bool, change: float) -> ContentState:
        if not signal:
            self._signal_since = None
            if self._black_since is None:
                self._black_since = now
            if now - self._black_since >= BLACK_MS:
                self._set(ContentState.NO_SIGNAL, 0.0)
                self._burst_at = None
                self._recent.clear()
            return self.state
        self._black_since = None
        if self._signal_since is None:
            self._signal_since = now
            self._recent.clear()
            self._still_since = now
            return self.state  # the first frame with a picture: nothing to compare yet

        self._recent.append((now, change))
        while self._recent and now - self._recent[0][0] > VIDEO_MS + 200:
            self._recent.popleft()
        moving = [(t, c) for t, c in self._recent if c >= MOVING_CHANGE]
        # «over 1 s»: from the first moving frame in the window, most frames since moved
        span = now - moving[0][0] if moving else 0
        since = [c for t, c in self._recent if moving and t >= moving[0][0]]
        if span >= VIDEO_MS - 50 and len(moving) >= VIDEO_SHARE * len(since):
            self._set(ContentState.VIDEO, max(c for _, c in self._recent))
            self._burst_at = None
            return self.state

        if change >= BIG_CHANGE:
            self._burst_at = now
            self._burst_ratio = max(self._burst_ratio, change) if self._burst_at else change
            self._still_since = None
        elif change <= STILL_CHANGE:
            if self._still_since is None:
                self._still_since = now
        else:
            self._still_since = None

        still_for = 0 if self._still_since is None else now - self._still_since
        if self._burst_at is not None and still_for >= STILL_MS:
            self._set(ContentState.NEW_SLIDE, round(self._burst_ratio, 3))
            self._slide_until = now + SLIDE_HOLD_MS
            self._burst_at = None
            self._burst_ratio = 0.0
        elif self.state is ContentState.NEW_SLIDE and now < self._slide_until:
            pass  # hold, so the engine sees it (CT2 reacts to the edge)
        elif self._burst_at is None and (
            self.state in (ContentState.NO_SIGNAL, ContentState.VIDEO, ContentState.NEW_SLIDE)
        ):
            if self.state is ContentState.NO_SIGNAL and now - self._signal_since < BLACK_MS:
                return self.state
            if self.state is ContentState.VIDEO and still_for < STILL_MS:
                return self.state
            self._set(ContentState.STATIC, 0.0)
        return self.state

    def _set(self, state: ContentState, ratio: float) -> None:
        self.state = state
        self.changed_ratio = ratio
