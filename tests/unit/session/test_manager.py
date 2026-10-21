from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cutcut.common.ids import Mode
from cutcut.common.models.session import RecordingStatus, ShowChoice, TouchStep, User
from cutcut.core.inputs import EndShow, StartShow
from cutcut.session.manager import (
    COUNTDOWN_MS,
    DONE_LOGOUT_MS,
    READY_IDLE_MS,
    START_TIMEOUT_MS,
    Alert,
    EngineCommand,
    Notice,
    PearlStart,
    PearlStop,
    SessionError,
    SessionManager,
)

WALL = datetime(2026, 10, 21, 14, 2, 11, tzinfo=UTC)
KARI = User(username="kanordm", display_name="Kari Nordmann")
OLA = User(username="olanord", display_name="Ola Nordmann")


def recording(m: SessionManager, now: int = 0) -> int:
    m.login(KARI, now, WALL)
    m.start(now, "touch")
    actions = m.tick(now + COUNTDOWN_MS)
    assert PearlStart() in actions
    now += COUNTDOWN_MS + 800
    actions = m.pearl_status(RecordingStatus.STARTED, now)
    assert EngineCommand(StartShow(audio_only=False)) in actions
    assert m.step is TouchStep.REC
    return now


def test_full_flow_card_to_done_and_auto_logout() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    assert m.step is TouchStep.READY
    assert m.session is not None
    assert m.session.session_id == "2026-10-21T14:02:11-kanordm"
    m.set_show(ShowChoice(guests=2, video=True), 100)
    assert m.mode() is Mode.N3
    now = recording(m, 200)
    assert m.stop(now + 60_000, "touch") == [PearlStop()]
    actions = m.pearl_status(RecordingStatus.STOPPED, now + 60_500)
    assert EngineCommand(EndShow()) in actions
    assert m.step is TouchStep.DONE
    assert m.session.recording.duration_s >= 60
    m.tick(now + 60_500 + DONE_LOGOUT_MS)
    assert m.step is TouchStep.IDLE
    assert m.session is None


def test_countdown_shows_starter_until_pearl_confirms() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    m.start(0, "touch")
    assert m.step is TouchStep.COUNTDOWN
    m.tick(COUNTDOWN_MS)
    assert m.session is not None
    assert m.session.recording.state is RecordingStatus.STARTING
    assert m.step is TouchStep.COUNTDOWN  # not REC before Pearl says started (12.5)


def test_pearl_that_does_not_start_gives_plain_error_and_back_to_ready() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    m.start(0, "touch")
    m.tick(COUNTDOWN_MS)
    actions = m.tick(COUNTDOWN_MS + START_TIMEOUT_MS + 1)
    assert m.step is TouchStep.READY
    assert any(isinstance(a, Notice) and "startet ikke" in a.message_nb for a in actions)


def test_audio_only_starts_engine_in_mode_A() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    m.set_show(ShowChoice(guests=1, video=False), 0)
    assert m.mode() is Mode.A
    m.start(0, "touch")
    m.tick(COUNTDOWN_MS)
    actions = m.pearl_status(RecordingStatus.STARTED, COUNTDOWN_MS + 500)
    assert EngineCommand(StartShow(audio_only=True)) in actions


def test_new_card_during_recording_is_refused_same_card_ignored() -> None:
    m = SessionManager()
    now = recording(m)
    assert m.login(KARI, now, WALL) == []
    with pytest.raises(SessionError, match="opptak pågår"):
        m.login(OLA, now, WALL)


def test_never_logged_out_during_recording() -> None:
    m = SessionManager()
    now = recording(m)
    with pytest.raises(SessionError):
        m.logout(now)
    m.tick(now + 10 * READY_IDLE_MS)
    assert m.step is TouchStep.REC


def test_ready_screen_logs_out_after_three_minutes_without_touch() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    m.tick(READY_IDLE_MS - 1)
    assert m.step is TouchStep.READY
    m.touched(READY_IDLE_MS - 1)
    m.tick(READY_IDLE_MS + 1000)
    assert m.step is TouchStep.READY  # touch reset the timer
    m.tick(2 * READY_IDLE_MS)
    assert m.step is TouchStep.IDLE


def test_recording_never_stops_by_itself_but_raises_alarm_I7() -> None:
    m = SessionManager()
    now = recording(m)
    actions = m.pearl_status(RecordingStatus.ERROR, now + 5000)
    assert m.step is TouchStep.REC
    alarm = [a for a in actions if isinstance(a, Alert)]
    assert alarm
    assert alarm[0].level == "error"
    assert alarm[0].for_user
    assert PearlStart() not in actions


def test_start_and_stop_are_idempotent_from_both_sides() -> None:
    m = SessionManager()
    now = recording(m)
    assert m.start(now, "tech") == []  # already recording
    assert m.stop(now + 1000, "touch") == [PearlStop()]
    assert m.stop(now + 1100, "tech") == [PearlStop()]  # the second press is harmless
    m.pearl_status(RecordingStatus.STOPPED, now + 1500)
    assert m.step is TouchStep.DONE
    assert m.stop(now + 1600, "tech") == []


def test_stop_during_countdown_cancels_without_recording() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    m.start(0, "touch")
    assert m.stop(1000, "touch") == []
    assert m.step is TouchStep.READY
    assert m.tick(COUNTDOWN_MS) == []


def test_new_recording_from_done_screen() -> None:
    m = SessionManager()
    now = recording(m)
    m.stop(now, "touch")
    m.pearl_status(RecordingStatus.STOPPED, now + 500)
    m.start(now + 1000, "touch")
    assert m.step is TouchStep.COUNTDOWN


def test_again_from_done_keeps_user_and_choice_in_a_new_session() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    m.set_show(ShowChoice(guests=2, video=False), 0)
    m.start(0, "touch")
    m.tick(COUNTDOWN_MS)
    now = COUNTDOWN_MS + 800
    m.pearl_status(RecordingStatus.STARTED, now)
    m.stop(now + 5000, "touch")
    m.pearl_status(RecordingStatus.STOPPED, now + 5500)
    assert m.step is TouchStep.DONE
    first = m.session.session_id if m.session else ""
    m.again(now + 6000, WALL.replace(minute=9))
    assert m.step is TouchStep.READY
    assert m.session is not None
    assert m.session.user == KARI
    assert m.session.show == ShowChoice(guests=2, video=False)
    assert m.session.session_id != first
    assert m.session.recording.duration_s == 0


def test_again_only_from_done() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    with pytest.raises(SessionError):
        m.again(0, WALL)


def test_technician_can_move_touch_to_any_step() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    m.move_to(TouchStep.DONE, 10)
    assert m.step is TouchStep.DONE
    m.move_to(TouchStep.IDLE, 20)
    assert m.session is None
    with pytest.raises(SessionError):
        m.move_to(TouchStep.READY, 30)


def test_help_raises_alert_for_technician() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    actions = m.help(5)
    assert m.help_requested
    assert isinstance(actions[0], Alert)
    assert "Kari" in actions[0].message_nb


def test_session_model_has_no_card_number() -> None:
    m = SessionManager()
    m.login(KARI, 0, WALL)
    assert m.session is not None
    assert "uid" not in m.session.model_dump_json().lower()
