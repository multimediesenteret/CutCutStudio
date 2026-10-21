"""Pure helpers for the bus: sequence-gap detection and stale-topic detection.

No sockets here, so they are trivially testable and usable in the simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SeqTracker:
    """Counts missing messages per (source, topic) from the ``seq`` field."""

    last: dict[tuple[str, str], int] = field(default_factory=dict)
    gaps: int = 0
    restarts: int = 0

    def observe(self, source: str, topic: str, seq: int) -> int:
        """Return how many messages were missed before this one (0 if none)."""
        key = (source, topic)
        prev = self.last.get(key)
        self.last[key] = seq
        if prev is None:
            return 0
        if seq <= prev:  # sender restarted and began counting from 0 again
            self.restarts += 1
            return 0
        missed = seq - prev - 1
        self.gaps += missed
        return missed


@dataclass
class StaleWatcher:
    """Tracks when each topic was last heard and reports topics that went quiet.

    A topic is stale when nothing has arrived for ``timeout_ms`` (spec 6.6: vision 1 s;
    spec 5.7 S4: audio 2 s – those rules use their own timeouts on top of this).
    """

    timeout_ms: int = 1000
    last_seen: dict[str, int] = field(default_factory=dict)
    stale: set[str] = field(default_factory=set)

    def seen(self, topic: str, now_ms: int) -> bool:
        """Record a message. Returns True if the topic was stale and is now back."""
        self.last_seen[topic] = now_ms
        if topic in self.stale:
            self.stale.discard(topic)
            return True
        return False

    def check(self, now_ms: int) -> list[str]:
        """Return topics that became stale since the last check."""
        newly = [
            t
            for t, seen in self.last_seen.items()
            if t not in self.stale and now_ms - seen > self.timeout_ms
        ]
        self.stale.update(newly)
        return sorted(newly)

    def is_stale(self, topic: str, now_ms: int) -> bool:
        seen = self.last_seen.get(topic)
        return seen is None or now_ms - seen > self.timeout_ms
