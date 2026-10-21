"""Safety (S, 5.7), override (5.2 step 1, I5), shadow mode (PL-05) and bird's-eye B2–B5."""

from __future__ import annotations

import itertools

from cutcut.common.ids import AUDIO_ONLY, BIRD, CameraId, RuleId, SourceId
from cutcut.core.inputs import (
    AtemReadback,
    ManualCut,
    ManualPreview,
    SetAuto,
    SetLock,
    SetShadow,
    StartShow,
    TileFrame,
)
from cutcut.core.intents import DirectCut, ShowAudioOnly, Take
from tests.rules.harness import WARMUP_MS, Harness, started

# --- S --------------------------------------------------------------------------------------


def test_S1_never_cuts_to_a_moving_camera() -> None:
    h = started()
    h.moving.add(CameraId.C2)
    h.talk("P2")
    h.run(3000)
    assert h.program == BIRD
    assert h.waits(RuleId.S1)
    h.moving.clear()
    h.run(600)
    assert h.program == "CU:P2"


def test_S1_does_not_block_a_still_camera() -> None:
    h = started()
    h.moving.add(CameraId.C3)  # another camera moving does not matter
    h.talk("P2")
    h.run(1200)
    assert h.program == "CU:P2"


def test_S2_needs_a_valid_face_with_video_confirm() -> None:
    h = started(features={"video_confirm": True})
    h.vision = {SourceId.C2: TileFrame(face_ok=False)}
    h.talk("P2")
    h.run(3000)
    assert h.program == BIRD
    assert h.waits(RuleId.S2)


def test_S2_ignored_without_video_layer() -> None:
    h = started(features={"video_confirm": True})
    h.vision = None  # video layer down: audio alone decides (6.6)
    h.talk("P2")
    h.run(1200)
    assert h.program == "CU:P2"


def test_S3_at_most_one_automatic_cut_per_second() -> None:
    # Loosen every other limit so that only S3 stands between the engine and rapid cuts.
    loose = {
        "T3_min_shot_s": 0.5,
        "T3_guest_extra_s": 0,
        "H2_no_return_s": 0,
        "H1_factor": 1,
        "T2_confirm_ms": 200,
        "T4_ignore_interrupt_s": 0,
        "PV1_min_preview_s": 0,
        "K1_pause_ms": 0,
    }
    h = started(4, overrides=loose)
    for i in range(40):
        h.stop_all()
        h.talk(("P1", "P2", "P3", "P4")[i % 4])
        h.run(450)
    times = h.cut_times()
    assert len(times) >= 3
    assert min(b - a for a, b in itertools.pairwise(times)) >= 1000
    assert h.waits(RuleId.S3)


def test_S3_does_not_hold_back_a_single_cut() -> None:
    h = started()
    h.talk("P2")
    h.run(1200)
    assert not h.waits(RuleId.S3)


def test_S4_audio_lost_cuts_to_bird_and_pauses() -> None:
    h = started()
    h.talk("P2")
    h.run(2000)
    assert h.program == "CU:P2"
    h.run(2000)
    h.audio_lost = True
    h.run(2100)
    assert h.program == BIRD
    assert h.engine.paused
    assert [d for d in h.decisions if d.rule is RuleId.S4]
    assert isinstance(h.intents_of(DirectCut)[-1][1], DirectCut)
    h.audio_lost = False
    h.run(1000)
    assert h.engine.paused  # waits 2 s of stable audio
    h.run(1200)
    assert not h.engine.paused


def test_S4_does_not_fire_on_short_gap() -> None:
    h = started()
    h.talk("P2")
    h.run(2000)
    h.audio_lost = True
    h.run(1500)
    h.audio_lost = False
    h.run(100)
    assert h.program == "CU:P2"
    assert not [d for d in h.decisions if d.rule is RuleId.S4]


def test_S6_no_cut_to_a_mic_muted_on_the_mixer() -> None:
    h = started()
    h.voice("P2").muted = True
    h.talk("P2")
    h.run(3000)
    assert h.program == BIRD


def test_S6_unmuted_mic_is_cut_to() -> None:
    h = started()
    h.voice("P2").muted = False
    h.talk("P2")
    h.run(1200)
    assert h.program == "CU:P2"


# --- override (5.2 step 1, I5) -------------------------------------------------------------


def test_manual_cut_wins_and_engine_waits() -> None:
    h = started()
    h.talk("P2")
    h.run(4000)
    h.command(ManualCut("CU:P1"))
    h.run(4000)  # P2 still talking, but the operator chose P1
    assert h.program == "CU:P1"
    h.run(1500)  # after manual_quiet_s (5 s) the engine is free again
    assert h.program == "CU:P2"


def test_auto_off_stops_all_automatic_cuts() -> None:
    h = started()
    h.command(SetAuto(on=False))
    h.talk("P2")
    h.run(3000)
    assert h.program == BIRD
    h.command(SetAuto(on=True))
    h.run(1000)
    assert h.program == "CU:P2"


def test_lock_holds_the_current_shot() -> None:
    h = started()
    h.talk("P2")
    h.run(2000)
    h.command(SetLock(on=True))
    h.stop("P2")
    h.talk("P1")
    h.run(5000)
    assert h.program == "CU:P2"


def test_manual_preview_is_taken_at_next_cut_point() -> None:
    h = started()
    h.talk("P1")
    h.run(5000)
    h.command(ManualPreview("CU:P2"))
    h.stop("P1")
    h.run(1000)
    assert h.program == "CU:P2"
    assert h.last_cut().rule is RuleId.MANUAL
    assert h.intents_of(Take)


def test_I5_person_changing_atem_is_respected() -> None:
    h = started()
    h.atem = AtemReadback(program=SourceId.C5, preview=SourceId.C1)
    h.talk("P2")
    h.run(1500)  # engine cuts to P2, ATEM readback still says C5 after settling...
    h.atem = AtemReadback(program=SourceId.C1, preview=SourceId.C2)  # ...a person took C1
    h.run(700)
    assert h.program == "CU:P1"
    assert [d for d in h.decisions if d.rule is RuleId.MANUAL and d.action == "hold"]
    h.run(3000)
    assert h.program == "CU:P1"  # quiet for 5 s


def test_audio_only_mode_shows_graphic_and_never_cuts() -> None:
    h = started()
    h.command(StartShow(audio_only=True))
    h.talk("P2")
    h.run(5000)
    assert h.program == AUDIO_ONLY
    assert h.intents_of(ShowAudioOnly)
    assert not h.intents_of(Take)


# --- shadow mode (PL-05) -------------------------------------------------------------------


def test_shadow_mode_decides_but_sends_nothing() -> None:
    h = Harness(participants=2, shadow=True)
    h.run(WARMUP_MS)
    h.talk("P2")
    h.run(1500)
    assert h.program == "CU:P2"
    assert h.intents == []
    assert all(d.shadow for d in h.decisions)


def test_shadow_can_be_switched_off_live() -> None:
    h = Harness(participants=2, shadow=True)
    h.run(WARMUP_MS)
    h.command(SetShadow(on=False))
    h.talk("P2")
    h.run(1500)
    assert h.intents_of(Take)


# --- B2–B5 ---------------------------------------------------------------------------------


def test_B2_three_talking_at_once_goes_to_bird() -> None:
    h = started(3)
    h.talk("P1")
    h.run(5000)
    h.talk("P2")
    h.talk("P3")
    h.run(2000)
    assert h.program == BIRD
    assert h.last_cut().rule is RuleId.B2


def test_B2_not_with_bird_switched_off() -> None:
    h = started(3, features={"bird": False})
    h.talk("P1")
    h.run(5000)
    h.talk("P2")
    h.talk("P3")
    h.run(2000)
    assert h.program != BIRD


def test_B3_long_silence_goes_to_bird() -> None:
    h = started(3)
    h.talk("P1")
    h.run(5000)
    h.stop("P1")
    h.run(3500)
    assert h.program == BIRD
    assert h.last_cut().rule is RuleId.B3


def test_B3_not_with_bird_off_and_no_wide() -> None:
    h = started(3, features={"bird": False})
    h.talk("P1")
    h.run(5000)
    h.stop("P1")
    h.run(5000)
    assert h.program == "CU:P1"


def test_B4_laughter_goes_to_bird() -> None:
    h = started(3)
    h.talk("P1")
    h.run(5000)
    h.voice("P2").laughing = True
    h.voice("P3").laughing = True
    h.run(2500)
    assert h.program == BIRD
    assert h.last_cut().rule is RuleId.B4


def test_B4_one_person_laughing_is_not_enough() -> None:
    h = started(3)
    h.talk("P1")
    h.run(5000)
    h.voice("P2").laughing = True
    h.run(3000)
    assert h.program == "CU:P1"


def test_B5_short_bird_in_long_answer_alternates_with_reaction() -> None:
    h = started(overrides={"B5_min_gap_s": 20})
    h.talk("P2")
    h.run(1000)
    h.phrases("P2", 70000)
    rules = h.cut_rules()
    assert RuleId.T7 in rules
    assert RuleId.B5 in rules
    bird = next(d for d in h.cuts() if d.rule is RuleId.B5)
    assert bird.shot == BIRD


def test_B5_respects_max_share() -> None:
    h = started(overrides={"B5_max_share": 0.0})
    h.talk("P2")
    h.run(1000)
    h.phrases("P2", 70000)
    assert RuleId.B5 not in h.cut_rules()
