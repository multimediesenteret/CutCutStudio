"""Content CT1–CT6 and opening B1 (spec 5.4, 5.5, 6.2)."""

from __future__ import annotations

from cutcut.common.ids import BIRD, CONTENT, Mode, RuleId
from cutcut.core.inputs import ContentState, SetContentEnabled, StartShow
from tests.rules.harness import Harness, started


def with_speaker(pid: str = "P1") -> Harness:
    h = started()
    h.talk(pid)
    h.run(5000)
    assert h.program == f"CU:{pid}"
    return h


def slide(h: Harness) -> None:
    """Laptop shows a new slide: big change, then a still picture (6.2)."""
    h.content = ContentState.NEW_SLIDE
    h.run(60)
    h.content = ContentState.STATIC


def test_CT1_content_counts_as_active_after_two_seconds() -> None:
    h = with_speaker()
    h.content = ContentState.STATIC
    h.run(1500)
    assert h.engine.mode is Mode.N2
    h.run(700)
    assert h.engine.mode.value == "N2C"


def test_CT1_black_or_no_signal_is_not_content() -> None:
    h = with_speaker()
    h.content = ContentState.NO_SIGNAL
    h.run(5000)
    assert h.engine.mode is Mode.N2


def test_CT2_new_slide_goes_to_content_and_holds() -> None:
    h = with_speaker()
    h.content = ContentState.STATIC
    h.run(2500)
    slide(h)
    h.run(800)
    assert h.program == CONTENT
    assert h.last_cut().rule is RuleId.CT2
    cut_at = h.last_cut().mono_ms
    h.run(4000)
    assert h.program == CONTENT  # holds for CT2_hold_s (6 s)
    assert cut_at > 0


def test_CT2_no_new_slide_no_cut_to_content() -> None:
    h = with_speaker()
    h.content = ContentState.STATIC
    h.run(8000)
    assert h.program == "CU:P1"


def test_CT2_new_slide_is_shown_within_one_second() -> None:
    h = with_speaker()
    h.content = ContentState.STATIC
    h.run(2500)
    t0 = h.now
    slide(h)
    h.run(1000)
    assert h.last_cut().shot == CONTENT
    assert h.last_cut().mono_ms - t0 <= 1000  # 10.4


def test_CT3_video_holds_content() -> None:
    h = with_speaker()
    h.content = ContentState.VIDEO
    h.run(15000)
    assert h.program == CONTENT
    assert RuleId.CT3 in h.cut_rules()


def test_CT3_video_is_held_at_most_the_limit() -> None:
    h = started(overrides={"CT3_video_max_s": 8})
    h.talk("P1")
    h.run(5000)
    h.content = ContentState.VIDEO
    h.run(16000)
    assert h.program != CONTENT


def test_CT4_static_content_returns_to_speaker_via_short_bird_B1() -> None:
    h = with_speaker()
    h.content = ContentState.STATIC
    h.run(2500)
    slide(h)
    h.run(12000)
    rules = h.cut_rules()
    assert RuleId.CT2 in rules
    assert RuleId.B1 in rules  # short BIRD after the content block (5.4)
    assert h.program == "CU:P1"


def test_CT4_without_bird_returns_straight_to_speaker() -> None:
    h = started(features={"bird": False})
    h.talk("P1")
    h.run(5000)
    h.content = ContentState.STATIC
    h.run(2500)
    slide(h)
    h.run(12000)
    assert RuleId.CT4 in h.cut_rules()
    assert h.program == "CU:P1"


def test_CT4_revisit_is_off_by_default() -> None:
    h = with_speaker()
    h.content = ContentState.STATIC
    h.run(60000)
    assert CONTENT not in [d.shot for d in h.cuts()]


def test_CT4_revisit_when_switched_on() -> None:
    h = started(overrides={"CT4_revisit_enabled": True, "CT4_revisit_every_s": 20})
    h.talk("P1")
    h.content = ContentState.STATIC
    h.phrases("P1", 30000)
    assert RuleId.CT4 in [d.rule for d in h.cuts() if d.shot == CONTENT]


def test_CT5_laptop_audio_gives_content_priority() -> None:
    h = with_speaker()
    h.content = ContentState.STATIC
    h.run(2500)
    h.laptop.talking = True
    h.run(2000)
    assert h.program == CONTENT
    assert h.last_cut().rule is RuleId.CT5


def test_CT5_no_laptop_audio_no_priority() -> None:
    h = with_speaker()
    h.content = ContentState.STATIC
    h.run(4000)
    assert h.program == "CU:P1"


def test_CT6_lost_signal_cuts_away_at_once() -> None:
    h = with_speaker()
    h.content = ContentState.VIDEO
    h.run(5000)
    assert h.program == CONTENT
    t0 = h.now
    h.content = ContentState.NO_SIGNAL
    h.run(1000)
    assert h.program == "CU:P1"
    cut = h.last_cut()
    assert cut.rule is RuleId.CT6
    assert cut.mono_ms - t0 <= 1000  # 10.4: removed within 1 s


def test_CT6_never_content_during_crosstalk() -> None:
    h = with_speaker()
    h.content = ContentState.STATIC
    h.run(2500)
    h.talk("P2")
    h.run(1200)  # crosstalk established
    slide(h)
    h.run(1500)
    assert h.program != CONTENT


def test_content_switch_off_from_operator() -> None:
    h = with_speaker()
    h.command(SetContentEnabled(enabled=False))
    h.content = ContentState.VIDEO
    h.run(6000)
    assert h.program == "CU:P1"
    assert h.engine.mode is Mode.N2


def test_B1_show_opens_on_bird_then_host() -> None:
    h = Harness(participants=3)
    h.run(3000)
    h.talk("P2")  # a guest is already chatting when recording starts
    h.command(StartShow())
    h.run(4500)
    first = h.cuts()
    assert first[0].shot == "CU:P1"
    assert first[0].rule is RuleId.B1
    assert h.decisions[0].rule is RuleId.B1
    assert h.decisions[0].shot == BIRD


def test_B1_without_bird_opens_on_host() -> None:
    h = Harness(participants=2, features={"bird": False})
    h.command(StartShow())
    h.run(60)
    assert h.program == "CU:P1"
    assert h.last_cut().rule is RuleId.B1
