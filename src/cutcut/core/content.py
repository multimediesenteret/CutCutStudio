"""Content state from the laptop tile and laptop audio (spec 5.5 CT1–CT6, 6.2). Pure."""

from __future__ import annotations

from dataclasses import dataclass

from cutcut.common.config.rules import RuleParams
from cutcut.core.inputs import ContentState


@dataclass
class ContentTracker:
    present_since: int | None = None  # signal on the laptop tile (not NO_SIGNAL)
    active: bool = False  # CT1: present long enough to count as content
    slide_at: int | None = None  # last NEW_SLIDE (CT2)
    video_since: int | None = None  # VIDEO or laptop audio (CT3)
    laptop_audio: bool = False  # CT5
    last_state: ContentState | None = None
    last_on_air_end: int = -(10**9)

    def update(
        self,
        now: int,
        state: ContentState | None,
        laptop_audio: bool,
        enabled: bool,
        rules: RuleParams,
    ) -> None:
        if not enabled or state is None or state is ContentState.NO_SIGNAL:
            self.present_since = None
            self.active = False
            self.slide_at = None
            self.video_since = None
            self.laptop_audio = False
            self.last_state = state
            return
        if self.present_since is None:
            self.present_since = now
        self.active = now - self.present_since >= rules.CT1_active_s * 1000
        if state is ContentState.NEW_SLIDE and self.last_state is not ContentState.NEW_SLIDE:
            self.slide_at = now
        if state is ContentState.VIDEO or laptop_audio:
            if self.video_since is None:
                self.video_since = now
        else:
            self.video_since = None
        self.laptop_audio = laptop_audio and self.active
        self.last_state = state

    def lost(self) -> bool:
        """CT6: no usable signal any more."""
        return self.present_since is None
