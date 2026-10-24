"""P10: something else on air (a logo, black, a media player) is the technician's, and AUTO
waits until a known source is back (I5, ADR-0004). With an ATEM to read, AUTO also stops
taking once it cannot be read (Q45): Companion would cut blind."""

from __future__ import annotations

from cutcut.common.ids import AUDIO_ONLY, RuleId, SourceId
from cutcut.core.inputs import AtemReadback, StartShow
from cutcut.core.intents import DirectCut, Take
from cutcut.core.shots import source_for
from tests.rules.harness import Harness, started

BLACK = AtemReadback(program=SourceId.OTHER, preview=SourceId.C1, program_input=0)
LOGO_MP1 = AtemReadback(
    program=SourceId.SUPERSOURCE, preview=SourceId.C1, program_layout=AUDIO_ONLY
)


def follow(h: Harness) -> None:
    """The ATEM shows what the engine took (as a real one does)."""
    h.atem = AtemReadback(program=source_for(h.program, h.show), preview=SourceId.C1)


def takes(h: Harness, since: int) -> list[int]:
    return [t for t, i in h.intents if t > since and isinstance(i, (Take, DirectCut))]


def test_P10_black_on_air_waits_and_takes_nothing() -> None:
    h = started()
    follow(h)
    h.run(200)
    h.atem = BLACK
    t0 = h.now
    h.talk("P2")
    h.run(4000)
    assert not takes(h, t0)
    assert h.engine.hold == "graphic"
    held = [d for d in h.decisions if d.action == "hold" and "Annen kilde" in d.reason]
    assert held
    assert held[0].rule is RuleId.MANUAL
    assert "inngang 0" in held[0].reason


def test_P10_a_logo_on_media_player_1_is_not_audio_only_in_a_normal_show() -> None:
    h = started()
    follow(h)
    h.atem = LOGO_MP1
    t0 = h.now
    h.talk("P2")
    h.run(8000)  # longer than manual_quiet_s: the old behaviour cut away after 5 s
    assert not takes(h, t0)
    assert h.engine.hold == "graphic"


def test_P10_a_camera_back_counts_as_manual_and_auto_goes_on_after_the_quiet() -> None:
    h = started()
    follow(h)
    h.atem = BLACK
    h.talk("P2")
    h.run(2000)
    h.atem = AtemReadback(program=SourceId.C1, preview=SourceId.C2)  # the technician is back
    t0 = h.now
    h.run(3000)
    assert h.engine.hold is None
    assert h.program == "CU:P1"
    assert not takes(h, t0)  # quiet for manual_quiet_s (5 s)
    h.run(5000)
    assert takes(h, t0)  # AUTO is back


def test_P10_safety_rules_do_not_cut_over_a_graphic() -> None:
    h = started()
    follow(h)
    h.atem = BLACK
    h.audio_lost = True  # S4 would otherwise go to the bird's-eye camera
    t0 = h.now
    h.run(6000)
    assert not takes(h, t0)


def test_P10_audio_only_show_still_shows_its_graphic() -> None:
    h = started()
    h.command(StartShow(audio_only=True))
    h.run(500)
    h.atem = LOGO_MP1  # media player 1 is the «Kun lyd» graphic here
    h.talk("P2")
    h.run(3000)
    assert h.engine.hold is None
    assert h.program == AUDIO_ONLY


def test_Q45_no_blind_take_without_the_atem() -> None:
    h = started(atem_required_ms=2000)
    follow(h)
    h.run(200)
    h.atem = None  # atem-bridge stopped
    t0 = h.now
    h.talk("P2")
    h.run(1000)
    h.run(4000)
    late = [t for t in takes(h, t0) if t > t0 + 2000]
    assert not late
    assert h.engine.hold == "atem"
    assert [d for d in h.decisions if d.rule is RuleId.S5 and "ATEM kan ikke leses" in d.reason]


def test_Q45_without_an_atem_at_all_the_rule_is_off() -> None:
    h = started()  # the offline simulation and the rule tests have no ATEM
    h.talk("P2")
    h.run(3000)
    assert h.program == "CU:P2"


def test_P10_the_show_opens_over_the_logo_the_studio_rests_on() -> None:
    h = started()
    h.atem = LOGO_MP1  # between sessions the studio shows the podcast logo
    h.run(500)
    assert h.engine.hold == "graphic"
    t0 = h.now
    h.command(StartShow())
    h.run(100)
    follow(h)  # the ATEM now shows the opening shot
    h.run(100)
    assert takes(h, t0)
    assert h.engine.hold is None
    assert h.engine.quiet_until < h.now  # no manual pause after our own opening
