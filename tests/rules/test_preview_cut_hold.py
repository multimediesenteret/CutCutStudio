"""Preview (PV), cut points (K) and hold/release (H) – spec 5.9–5.11."""

from __future__ import annotations

import itertools

from cutcut.common.ids import BIRD, RuleId, SourceId
from cutcut.core.intents import DirectCut, SetPreview, Take
from tests.rules.harness import WARMUP_MS, Harness, started

# --- PV (5.9) ------------------------------------------------------------------------------


def test_PV1_preview_never_changes_faster_than_limit() -> None:
    h = started(3)
    for i in range(8):  # both talk; the louder one flips every 150 ms
        h.talk("P2", dominance_db=16 if i % 2 else 10)
        h.talk("P3", dominance_db=10 if i % 2 else 16)
        h.run(150)
    times = h.preview_times()
    assert len(times) >= 2
    assert min(b - a for a, b in itertools.pairwise(times)) >= 500


def test_PV1_does_not_block_a_single_preview_change() -> None:
    h = started()
    h.talk("P2")
    h.run(600)
    assert [i for _, i in h.intents_of(SetPreview)][-1] == SetPreview(SourceId.C2)


def test_preview_comes_before_program_for_speaker_cuts() -> None:
    h = started()
    h.talk("P2")
    h.run(1200)
    preview_at = [t for t, i in h.intents_of(SetPreview) if i == SetPreview(SourceId.C2)][-1]
    take_at = [t for t, _ in h.intents_of(Take)][-1]
    assert take_at - preview_at >= 300  # 10.4: preview ≥ 300 ms before program


def test_PV4_manual_cut_goes_straight_to_program() -> None:
    from cutcut.core.inputs import ManualCut

    h = started()
    h.command(ManualCut("CU:P1"))
    h.run(30)
    assert h.program == "CU:P1"
    assert [i for _, i in h.intents_of(DirectCut)] == [DirectCut(SourceId.C1)]
    assert h.last_cut().rule is RuleId.MANUAL


def test_PV4_automatic_cuts_never_go_direct() -> None:
    h = started()
    h.talk("P2")
    h.run(2000)
    assert not h.intents_of(DirectCut)
    assert h.intents_of(Take)


# --- K (5.10) ------------------------------------------------------------------------------


def on_air(pid: str, participants: int = 2) -> Harness:
    h = started(participants)
    h.talk(pid)
    h.run(6000)
    assert h.program == f"CU:{pid}"
    return h


def test_K1_turn_change_cuts_at_once_when_previous_speaker_is_silent() -> None:
    h = on_air("P1")
    h.stop("P1")
    h.run(400)
    h.talk("P2")
    h.run(1200)
    cut = h.last_cut()
    assert cut.shot == "CU:P2"
    assert cut.measures["cut_point"] == 1


def test_K1_does_not_apply_while_previous_speaker_talks() -> None:
    h = on_air("P1")
    h.talk("P2", dominance_db=16)  # P1 keeps talking
    h.run(1200)
    cuts = [d for d in h.cuts() if d.shot == "CU:P2"]
    assert not cuts or cuts[0].measures["cut_point"] != 1


def test_K2_overlap_cuts_at_phrase_end_of_previous_speaker() -> None:
    h = on_air("P1")
    h.talk("P2", dominance_db=16)  # starts while P1 finishes the sentence
    h.run(700)
    h.stop("P1", pitch_falling=True)  # falling pitch + short pause = sentence end
    h.run(400)
    cut = h.last_cut()
    assert cut.shot == "CU:P2"
    assert cut.measures["cut_point"] == 2


def test_K2_does_not_cut_in_a_short_gap_without_falling_pitch() -> None:
    h = started(overrides={"T5_crosstalk_s": 5})  # keep crosstalk out of this test
    h.talk("P1")
    h.run(6000)
    h.talk("P2", dominance_db=16)
    h.run(1100)  # P2 confirmed and on preview, waiting for a cut point
    h.stop("P1")  # 180 ms breath, no falling pitch: not a phrase end
    h.run(180)
    assert h.program == "CU:P1"


def chatter(h: Harness, pid: str, ms: int) -> None:
    """Short words with 220 ms gaps: never a phrase end, never sustained crosstalk."""
    end = h.now + ms
    while h.now < end:
        h.talk(pid, dominance_db=8)
        h.run(240)
        h.stop(pid)
        h.run(240)


def test_K3_takes_after_max_wait_if_new_speaker_still_talks() -> None:
    h = on_air("P1")
    h.talk("P2", dominance_db=16)
    chatter(h, "P1", 4000)
    cut = h.last_cut()
    assert cut.shot == "CU:P2"
    assert cut.measures["cut_point"] == 3


def test_K3_aborts_if_new_speaker_stops_before_cut_point() -> None:
    h = on_air("P1")
    h.talk("P2", dominance_db=16)
    h.run(1100)
    h.stop("P2")
    h.run(3000)
    assert h.program == "CU:P1"


def test_K4_insert_waits_for_speaker_pause() -> None:
    h = started()
    h.talk("P2")
    h.run(1000)
    h.talk("P2")
    h.run(20000)  # one long phrase, never a pause: no reaction shot
    assert RuleId.T7 not in h.cut_rules()
    h.stop("P2")
    h.run(300)
    assert h.last_cut().rule is RuleId.T7


def test_K4_insert_is_taken_in_a_pause() -> None:
    h = started()
    h.talk("P2")
    h.run(1000)
    h.phrases("P2", 20000)
    assert RuleId.T7 in h.cut_rules()


# --- H (5.11) ------------------------------------------------------------------------------


def test_H1_needs_stronger_evidence_right_after_a_cut() -> None:
    h = started(3)
    h.talk("P2")
    h.run(1000)
    h.stop("P2")
    # P3 must wait for T3 anyway; check the required run is raised by H1 in the window
    h.talk("P3")
    h.run(700)
    wait = next(d for d in h.decisions if d.shot == "CU:P3")
    assert wait.rule is RuleId.H1
    assert wait.measures["required_ms"] == 1200


def test_H1_does_not_apply_after_the_window() -> None:
    h = on_air("P2", 3)
    h.stop("P2")
    h.run(400)
    h.talk("P3")
    h.run(1200)
    assert h.last_cut().rule is RuleId.T2


def test_H2_blocks_return_to_previous_shot_too_soon() -> None:
    h = on_air("P1")
    h.stop("P1")
    h.run(400)
    h.talk("P2")
    h.run(1000)
    cut_p2 = h.last_cut().mono_ms
    h.run(2600)  # past T3 for a guest (3.5 s) needs a bit more; P1 comes back now
    h.stop("P2")
    h.talk("P1")
    h.run(2500)
    back = next(d for d in h.cuts() if d.shot == "CU:P1" and d.mono_ms > cut_p2)
    assert back.mono_ms - cut_p2 >= 4000
    assert h.waits(RuleId.H2) or h.waits(RuleId.T3)


def test_H2_allows_return_after_limit() -> None:
    h = on_air("P1")
    h.stop("P1")
    h.run(400)
    h.talk("P2")
    h.run(6000)
    h.stop("P2")
    h.run(400)
    h.talk("P1")
    h.run(1500)
    assert h.program == "CU:P1"
    assert not h.waits(RuleId.H2)


def test_H3_holds_the_shot_after_the_speaker_stops() -> None:
    h = Harness(participants=2, overrides={"T8_silence_s": 0.5, "B3_silence_s": 0.5})
    h.run(WARMUP_MS)
    h.talk("P1")
    h.run(6000)
    h.stop("P1")
    h.run(900)
    assert h.program == "CU:P1"  # released only after H3 1.0 s
    h.run(600)
    assert h.program == BIRD


def test_H3_release_is_not_longer_than_needed() -> None:
    h = Harness(participants=2, overrides={"T8_silence_s": 0.5, "B3_silence_s": 0.5})
    h.run(WARMUP_MS)
    h.talk("P1")
    h.run(6000)
    h.stop("P1")
    h.run(1500)
    assert h.program == BIRD


def test_H4_returns_to_the_same_speaker_after_insert() -> None:
    h = started(3)
    h.talk("P2")
    h.run(1000)
    h.phrases("P2", 22000)
    rules = h.cut_rules()
    assert RuleId.H4 in rules
    assert next(d for d in h.cuts() if d.rule is RuleId.H4).shot == "CU:P2"


def test_H4_listener_who_starts_talking_takes_over() -> None:
    h = started()
    h.talk("P2")
    h.run(1000)
    h.phrases("P2", 18000)
    reaction = [d for d in h.cuts() if d.rule is RuleId.T7]
    assert reaction
    h.stop("P2")
    h.talk("P1")  # R3: the listener on screen starts talking
    h.run(4000)
    assert h.program == "CU:P1"
    assert RuleId.H4 not in [d.rule for d in h.cuts(reaction[0].mono_ms)]
