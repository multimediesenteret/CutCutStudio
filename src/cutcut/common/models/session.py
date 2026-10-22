"""Session (spec 7.5). Only username and display name are stored – never the card UID (I8)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cutcut.common.ids import Mode


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class User(_Model):
    username: str = Field(pattern=r"^[a-z0-9._-]{1,64}$")
    display_name: str = Field(min_length=1, max_length=120)


UNKNOWN_USER = User(username="ukjent", display_name="Ukjent bruker")
# «Start uten kort» (D-057): until the card reader and the card API are switched on.
GUEST_USER = User(username="gjest", display_name="Gjest")


class ShowChoice(_Model):
    """What the user picks on the touch ready screen (D-036)."""

    type: str = "podcast"
    guests: int = Field(default=1, ge=0, le=3)
    video: bool = True
    laptop: bool = False

    @property
    def participants(self) -> int:
        return self.guests + 1


class RecordingStatus(StrEnum):
    """Pearl recorder states (spec 7.4) plus ``idle`` before anything happened."""

    IDLE = "idle"
    STARTING = "starting"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"
    DISABLED = "disabled"


StartedBy = Literal["touch", "tech", "streamdeck"]


class RecordingState(_Model):
    state: RecordingStatus = RecordingStatus.IDLE
    started_by: StartedBy | None = None
    stopped_by: StartedBy | None = None
    duration_s: int = Field(default=0, ge=0)


class PublishState(_Model):
    """Panopto, prepared only (spec 7.6)."""

    target: Literal["panopto"] = "panopto"
    folder: str = "Mine opptak"
    state: Literal["pending", "uploading", "done", "failed", "disabled"] = "disabled"


class TouchStep(StrEnum):
    """Touch flow (D-036): rest → ready → countdown → recording → done."""

    IDLE = "idle"
    READY = "ready"
    COUNTDOWN = "countdown"
    REC = "rec"
    DONE = "done"


class Session(_Model):
    session_id: str
    user: User
    show: ShowChoice = ShowChoice()
    mode: Mode = Mode.N2
    recording: RecordingState = RecordingState()
    publish: PublishState = PublishState()
    touch_step: TouchStep = TouchStep.READY
