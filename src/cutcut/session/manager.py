"""Session and touch flow (spec 7.5, 8.1; D-036, D-043). Pure: time comes in, actions go out.

    IDLE ──card/tech──► READY ──Start──► COUNTDOWN ──3-2-1──► REC ──hold 2 s──► DONE
      ▲                   │ 3 min without touch           (Pearl confirms)       │ 30 s / Ferdig
      └───────────────────┴───────────────────────────────────────────────────────┘
                                                                  "Nytt opptak" → READY

* One active session. A new card during recording is refused; the same card does nothing.
* Never logged out during countdown or recording (D-043). Recording never stops by itself (I7).
* "Starter…" is shown until Pearl confirms; a recorder that does not start within 10 s gives
  a plain error and the user is back on READY (12.5: no optimistic buttons).
* Card numbers never enter this module – only the looked-up user (I8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Literal

from cutcut.common.ids import Mode
from cutcut.common.models.session import (
    RecordingState,
    RecordingStatus,
    Session,
    ShowChoice,
    StartedBy,
    TouchStep,
    User,
)
from cutcut.core.inputs import EndShow, StartShow

COUNTDOWN_MS: Final = 3000
START_TIMEOUT_MS: Final = 10_000
DONE_LOGOUT_MS: Final = 30_000
READY_IDLE_MS: Final = 180_000

Source = Literal["touch", "tech", "streamdeck", "card", "guest"]


@dataclass(frozen=True)
class PearlStart:
    pass


@dataclass(frozen=True)
class PearlStop:
    pass


@dataclass(frozen=True)
class EngineCommand:
    command: StartShow | EndShow


@dataclass(frozen=True)
class Alert:
    level: Literal["info", "warn", "error"]
    code: str
    message_nb: str  # one sentence, no technical words (touch shows it as is)
    for_user: bool = False


@dataclass(frozen=True)
class Notice:
    """Message for the touch screen only, e.g. "Kortet ble ikke gjenkjent"."""

    message_nb: str
    ms: int = 5000


Action = PearlStart | PearlStop | EngineCommand | Alert | Notice


class SessionError(Exception):
    """A request that is not allowed now. ``str()`` is a Norwegian message for the screens."""


@dataclass
class SessionManager:
    default_show: ShowChoice = field(default_factory=lambda: ShowChoice(guests=1, video=True))
    session: Session | None = None
    step: TouchStep = TouchStep.IDLE
    step_since: int = 0
    last_touch: int = 0
    countdown_end: int | None = None
    start_requested_at: int | None = None
    stop_requested: bool = False
    started_by: StartedBy | None = None
    recording_started_at: int | None = None
    pearl: RecordingStatus = RecordingStatus.STOPPED
    help_requested: bool = False
    _session_seq: int = 0

    # -- helpers --------------------------------------------------------------------------

    def _go(self, step: TouchStep, now: int) -> None:
        self.step, self.step_since = step, now
        if self.session is not None:
            self.session.touch_step = step

    @property
    def recording(self) -> bool:
        return self.step in (TouchStep.COUNTDOWN, TouchStep.REC)

    def mode(self) -> Mode:
        if self.session is None:
            return Mode.for_show(self.default_show.participants, False)
        show = self.session.show
        return Mode.for_show(show.participants, False, audio_only=not show.video)

    # -- login ----------------------------------------------------------------------------

    def login(self, user: User, now: int, wall: datetime, source: Source = "card") -> list[Action]:
        if self.session is not None:
            if self.session.user.username == user.username:
                self.last_touch = now
                return []  # same card again: nothing happens
            if self.recording:
                raise SessionError("Et opptak pågår. Vent til det er ferdig.")
            if self.step is TouchStep.DONE:
                self._logout(now)
            else:
                raise SessionError(f"{self.session.user.display_name} er allerede logget inn.")
        self._session_seq += 1
        self.session = Session(
            session_id=f"{wall:%Y-%m-%dT%H:%M:%S}-{user.username}",
            user=user,
            show=self.default_show.model_copy(),
            mode=self.mode(),
        )
        self.last_touch = now
        self._go(TouchStep.READY, now)
        self.session.mode = self.mode()
        return [Alert("info", "SESSION", f"{user.display_name} logget inn ({source})")]

    def card_not_recognised(self) -> list[Action]:
        return [Notice("Kortet ble ikke gjenkjent – prøv igjen")]

    def lookup_failed(self) -> list[Action]:
        return [
            Notice("Kortet kunne ikke sjekkes nå. Trykk Hjelp."),
            Alert("warn", "H-NTNU-1", "NTNU-API svarte ikke ved innlogging"),
        ]

    def logout(self, now: int) -> list[Action]:
        if self.recording:
            raise SessionError("Kan ikke logge ut mens opptaket pågår.")
        return self._logout(now)

    def _logout(self, now: int) -> list[Action]:
        self.session = None
        self.help_requested = False
        self.stop_requested = False
        self.start_requested_at = None
        self.countdown_end = None
        self._go(TouchStep.IDLE, now)
        return []

    def again(self, now: int, wall: datetime) -> list[Action]:
        """«Ta et nytt opptak» on the done screen: same user and choice, a new session."""
        if self.session is None or self.step is not TouchStep.DONE:
            raise SessionError("Det er ikke noe ferdig opptak å fortsette fra.")
        user, show = self.session.user, self.session.show
        self._logout(now)
        actions = self.login(user, now, wall, "touch")
        if self.session is not None:
            self.session.show = show
            self.session.mode = self.mode()
        return actions

    # -- show choice ----------------------------------------------------------------------

    def set_show(self, choice: ShowChoice, now: int) -> list[Action]:
        if self.session is None:
            raise SessionError("Ingen er logget inn.")
        if self.recording:
            raise SessionError("Valget kan ikke endres mens opptaket pågår.")
        self.session.show = choice
        self.session.mode = self.mode()
        self.last_touch = now
        return []

    def touched(self, now: int) -> None:
        self.last_touch = now

    # -- recording ------------------------------------------------------------------------

    def start(self, now: int, by: StartedBy) -> list[Action]:
        if self.session is None:
            raise SessionError("Ingen er logget inn.")
        if self.step is TouchStep.DONE:
            self._go(TouchStep.READY, now)
        if self.step in (TouchStep.COUNTDOWN, TouchStep.REC):
            return []  # idempotent: starting twice is the same as once
        self.started_by = by
        self.countdown_end = now + COUNTDOWN_MS
        self.last_touch = now
        self._go(TouchStep.COUNTDOWN, now)
        return []

    def stop(self, now: int, by: StartedBy) -> list[Action]:
        if not self.recording:
            return []  # idempotent
        if self.step is TouchStep.COUNTDOWN:  # cancelled before Pearl was asked
            self.countdown_end = None
            self._go(TouchStep.READY, now)
            return []
        self.stop_requested = True
        if self.session is not None:
            self.session.recording.stopped_by = by
        return [PearlStop()]

    def help(self, now: int) -> list[Action]:
        self.help_requested = True
        who = self.session.user.display_name if self.session else "Noen"
        return [Alert("warn", "HELP", f"{who} trenger hjelp i studio")]

    def move_to(self, step: TouchStep, now: int) -> list[Action]:
        """Technician moves the touch screen to any step (D-036, POST /touch/step)."""
        if step is TouchStep.IDLE:
            if self.recording:
                raise SessionError("Avslutt opptaket først.")
            return self._logout(now)
        if self.session is None:
            raise SessionError("Start en økt først.")
        if step is TouchStep.COUNTDOWN:
            return self.start(now, "tech")
        if step is TouchStep.REC:
            self.countdown_end = now
            return self.start(now, "tech") + self.tick(now)
        if step is TouchStep.DONE and self.recording:
            return self.stop(now, "tech")
        self._go(step, now)
        return []

    # -- inputs from Pearl ----------------------------------------------------------------

    def pearl_status(self, status: RecordingStatus, now: int) -> list[Action]:
        prev, self.pearl = self.pearl, status
        actions: list[Action] = []
        session = self.session
        if session is not None:
            session.recording.state = status
        started = status is RecordingStatus.STARTED
        if self.step is TouchStep.REC and started and self.recording_started_at is None:
            self.recording_started_at = now
        if self.start_requested_at is not None and status is RecordingStatus.STARTED:
            self.start_requested_at = None
            self.recording_started_at = now
            self._go(TouchStep.REC, now)
            actions.append(
                EngineCommand(StartShow(audio_only=bool(session and not session.show.video)))
            )
        if (
            self.step is TouchStep.REC
            and prev is RecordingStatus.STARTED
            and status in (RecordingStatus.STOPPED, RecordingStatus.ERROR)
        ):
            if self.stop_requested:
                actions += self._done(now)
            else:  # I7: never restarted automatically – alarm a person
                actions.append(
                    Alert(
                        "error",
                        "H-PRL-2",
                        "Opptaket stoppet uten at noen trykket stopp",
                        for_user=True,
                    )
                )
        return actions

    def _done(self, now: int) -> list[Action]:
        self.stop_requested = False
        if self.session is not None and self.recording_started_at is not None:
            self.session.recording.duration_s = (now - self.recording_started_at) // 1000
        self.recording_started_at = None
        self._go(TouchStep.DONE, now)
        return [EngineCommand(EndShow())]

    # -- time -----------------------------------------------------------------------------

    def tick(self, now: int) -> list[Action]:
        actions: list[Action] = []
        countdown_over = self.countdown_end is not None and now >= self.countdown_end
        if self.step is TouchStep.COUNTDOWN and countdown_over:
            self.countdown_end = None
            self.start_requested_at = now
            if self.session is not None:
                self.session.recording = RecordingState(
                    state=RecordingStatus.STARTING, started_by=self.started_by
                )
            actions.append(PearlStart())
        if self.start_requested_at is not None and now - self.start_requested_at > START_TIMEOUT_MS:
            self.start_requested_at = None
            self._go(TouchStep.READY, now)
            actions += [
                Notice("Opptaket startet ikke. Teknikeren er varslet."),
                Alert("error", "H-PRL-1", "Pearl startet ikke opptaket innen 10 s", for_user=True),
            ]
        if self.step is TouchStep.REC and self.session is not None and self.recording_started_at:
            self.session.recording.duration_s = (now - self.recording_started_at) // 1000
        if self.step is TouchStep.DONE and now - self.step_since >= DONE_LOGOUT_MS:
            actions += self._logout(now)
        if self.step is TouchStep.READY and now - self.last_touch >= READY_IDLE_MS:
            actions += self._logout(now)
        return actions

    def countdown_left_ms(self, now: int) -> int:
        if self.countdown_end is None:
            return 0
        return max(0, self.countdown_end - now)
