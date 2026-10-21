"""Talk rules T1–T9, T12 and roles (spec 5.3, 5.12). One test that fires, one that does not."""

from __future__ import annotations

from cutcut.common.ids import BIRD, RuleId
from tests.rules.harness import WARMUP_MS as WARMUP
from tests.rules.harness import Harness, started


def test_T1_fires_when_vad_and_dominance_are_over_threshold() -> None:
    h = started()
    h.talk("P2", dominance_db=8)
    h.run(1500)
    assert h.program == "CU:P2"


def test_T1_does_not_fire_without_dominance() -> None:
    h = started()
    h.talk("P2", dominance_db=3)  # only leakage-level over the others
    h.run(3000)
    assert h.program == BIRD


def test_T1_does_not_fire_on_low_vad() -> None:
    h = started()
    h.talk("P2", vad=0.4)
    h.run(3000)
    assert h.program == BIRD


def test_T2_fires_after_confirm_time() -> None:
    h = started()
    h.talk("P2")
    h.run(1200)
    cut = h.last_cut()
    assert cut.rule is RuleId.T2
    assert cut.measures["run_ms"] >= 800
    assert cut.mono_ms - WARMUP <= 800 + 60  # cut comes right at confirmation (10.4: ≤150 ms)


def test_T2_does_not_fire_on_short_burst() -> None:
    h = started()
    h.talk("P2")
    h.run(600)
    h.stop("P2")
    h.run(3000)
    assert "CU:P2" not in [d.shot for d in h.cuts()]


def test_T3_blocks_new_cut_before_minimum_shot_length() -> None:
    h = started(3)
    h.talk("P2")
    h.run(1000)
    assert h.program == "CU:P2"
    cut_at = h.last_cut().mono_ms
    h.stop("P2")
    h.talk("P3")
    h.run(4000)
    assert h.waits(RuleId.T3)
    p3 = next(d for d in h.cuts() if d.shot == "CU:P3")
    # guest on program: T3 2.5 s + 1 s extra for guests (5.12)
    assert p3.mono_ms - cut_at >= 3500


def test_T3_allows_cut_after_minimum_shot_length() -> None:
    h = started(3)
    h.talk("P2")
    h.run(1000)
    h.run(4000)
    h.stop("P2")
    h.talk("P3")
    h.run(1200)
    assert h.program == "CU:P3"
    assert not h.waits(RuleId.T3)


def test_T4_ignores_short_interruption_while_speaker_talks() -> None:
    h = started()
    h.talk("P1")
    h.run(5000)
    assert h.program == "CU:P1"
    h.talk("P2")  # P1 keeps talking: interruption of 0.9 s (> T2, < T4)
    h.run(900)
    h.stop("P2")
    h.run(2000)
    assert h.program == "CU:P1"


def test_T4_lets_a_long_enough_interruption_through() -> None:
    h = started()
    h.talk("P1", dominance_db=10)
    h.run(5000)
    h.stop("P1")
    h.run(400)
    h.talk("P1", dominance_db=10)
    h.talk("P2", dominance_db=14)
    h.run(400)
    h.stop("P1")
    h.run(2000)
    assert h.program == "CU:P2"


def test_T4_host_backchannel_never_cuts_under_limit() -> None:
    h = started()
    h.talk("P2")
    h.run(6000)
    assert h.program == "CU:P2"
    h.talk("P1", dominance_db=14)  # host says "ja, mm" over the guest for 1.2 s
    h.run(1200)
    h.stop("P1")
    h.run(1500)
    assert h.program == "CU:P2"


def test_T5_fires_on_crosstalk_to_mode_shot() -> None:
    h = started()
    h.talk("P1")
    h.run(4000)
    h.talk("P2")
    h.run(2500)
    assert h.program == BIRD
    assert h.last_cut().rule is RuleId.T5


def test_T5_uses_wide_in_N2_when_it_exists() -> None:
    h = started(wide=True)
    h.talk("P1")
    h.run(7000)  # past H2 for the opening WIDE
    h.talk("P2")
    h.run(2500)
    assert h.program == "WIDE"
    assert h.last_cut().rule is RuleId.T5


def test_T5_does_not_fire_on_short_overlap() -> None:
    h = started()
    h.talk("P1")
    h.run(4000)
    h.talk("P2")
    h.run(600)
    h.stop("P2")
    h.run(2000)
    assert h.program == "CU:P1"


def test_T6_pingpong_goes_to_group_shot() -> None:
    h = started()
    for _ in range(4):
        for pid, other in (("P1", "P2"), ("P2", "P1")):
            h.stop(other)
            h.talk(pid)
            h.run(1300)
    assert RuleId.T6 in h.cut_rules()


def test_T6_does_not_fire_on_calm_turn_taking() -> None:
    h = started()
    for pid, other in (("P1", "P2"), ("P2", "P1"), ("P1", "P2")):
        h.stop(other)
        h.talk(pid)
        h.run(6000)
    assert RuleId.T6 not in h.cut_rules()


def test_T7_reaction_shot_during_long_answer_and_back_H4() -> None:
    h = started()
    h.talk("P2")
    h.run(1000)
    h.phrases("P2", 22000)
    rules = h.cut_rules()
    assert RuleId.T7 in rules
    reaction = next(d for d in h.cuts() if d.rule is RuleId.T7)
    assert reaction.shot == "CU:P1"  # guest talks → host reaction (5.12)
    assert RuleId.H4 in rules
    back = next(d for d in h.cuts() if d.rule is RuleId.H4)
    assert back.shot == "CU:P2"
    assert 2400 <= back.mono_ms - reaction.mono_ms <= 4000


def test_T7_does_not_fire_on_short_answer() -> None:
    h = started()
    h.talk("P2")
    h.run(1000)
    h.phrases("P2", 10000)
    assert RuleId.T7 not in h.cut_rules()


def test_T8_silence_without_bird_goes_to_wide() -> None:
    h = started(wide=True, features={"bird": False})
    h.talk("P1")
    h.run(4000)
    h.stop("P1")
    h.run(4000)
    assert h.program == "WIDE"
    assert h.last_cut().rule is RuleId.T8


def test_T8_does_not_fire_on_short_silence() -> None:
    h = started()
    h.talk("P1")
    h.run(4000)
    h.stop("P1")
    h.run(2000)
    assert h.program == "CU:P1"


def test_T9_soft_cut_waits_for_a_short_pause() -> None:
    timing = {}
    for preset in ("standard", "energisk"):
        h = Harness(participants=2, preset=preset)
        h.run(WARMUP)
        h.talk("P1")
        h.run(5000)
        h.talk("P2")
        h.run(3000)
        group = [d for d in h.cuts() if d.shot == BIRD]
        assert group, preset
        timing[preset] = group[0]
    # In Energisk T9 is off, so the soft cut is not delayed waiting for a pause
    assert timing["standard"].measures["preview_ms"] >= timing["energisk"].measures["preview_ms"]


def test_T12_host_wins_when_equally_strong() -> None:
    h = started()
    h.talk("P1", dominance_db=12)
    h.talk("P2", dominance_db=12)
    h.run(500)
    first = next(d for d in h.decisions if d.action == "preview" and d.shot.startswith("CU:"))
    assert first.shot == "CU:P1"


def test_T12_does_not_override_a_clearly_louder_guest() -> None:
    h = started()
    h.talk("P1", dominance_db=10)
    h.talk("P2", dominance_db=16)
    h.run(500)
    first = next(d for d in h.decisions if d.action == "preview" and d.shot.startswith("CU:"))
    assert first.shot == "CU:P2"
