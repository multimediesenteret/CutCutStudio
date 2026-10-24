"""P10: something else on air (a logo, black, a media player) is the technician's, and AUTO
waits until a known source is back (I5, ADR-0004). With an ATEM to read, AUTO also stops
taking once it cannot be read (Q45): Companion would cut blind."""

from __future__ import annotations

from cutcut.common.ids import AUDIO_ONLY, RuleId, SourceId
from cutcut.core.inputs import AtemReadback, StartShow
from cutcut.core.intents import DirectCut, ShowAudioOnly, Take
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


def on_close_up(h: Harness) -> None:
    """Get a close-up of P2 on air (and on the ATEM), so the safety rules have work to do."""
    h.talk("P2")
    for _ in range(150):
        h.run(100)
        follow(h)
        if h.program == "CU:P2":
            return
    raise AssertionError("got no close-up")


def test_P10_safety_rules_do_not_cut_over_a_graphic() -> None:
    h = started()
    on_close_up(h)
    h.atem = BLACK
    h.run(200)
    h.audio_lost = True  # S4 would otherwise go to the bird's-eye camera
    t0 = h.now
    h.run(6000)
    assert not takes(h, t0)


def test_P10_a_gap_in_the_read_back_does_not_end_the_graphic() -> None:
    """Review finding: black on air, the read-back drops for 0.4 s, sound is lost: S4 must not
    cut over the black in the gap."""
    h = started(atem_required_ms=2000)
    on_close_up(h)
    h.atem = BLACK
    h.run(200)
    h.audio_lost = True
    h.run(1900)
    t0 = h.now
    h.atem = None
    h.run(400)
    h.atem = BLACK
    h.run(2000)
    assert not takes(h, t0)
    assert h.engine.hold == "graphic"
    assert not [d for d in h.decisions if "Kilden er tilbake" in d.reason]


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
    on_close_up(h)  # P2 talks and is on air
    h.atem = None  # atem-bridge stopped
    h.stop("P2")
    h.talk("P1")  # someone else takes over: AUTO would cut, but blind
    h.run(2100)
    t0 = h.now
    h.run(5000)
    assert not takes(h, t0)
    assert h.engine.hold == "atem"
    assert [d for d in h.decisions if d.rule is RuleId.S5 and "ATEM kan ikke leses" in d.reason]
    follow(h)  # the bridge is back: the person on air is what the ATEM shows
    h.run(6000)
    assert h.engine.hold is None
    assert takes(h, t0)  # AUTO cuts again after the quiet


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


def test_P10_an_audio_only_show_takes_over_from_black() -> None:
    h = started()
    h.atem = BLACK
    h.run(300)
    t0 = h.now
    h.command(StartShow(audio_only=True))
    h.run(100)
    assert any(isinstance(i, ShowAudioOnly) for t, i in h.intents if t > t0)
    assert h.program == AUDIO_ONLY


def test_P10_media_player_1_is_named_in_the_log() -> None:
    h = started()
    h.atem = AtemReadback(
        program=SourceId.SUPERSOURCE,
        preview=SourceId.C1,
        program_layout=AUDIO_ONLY,
        program_input=3010,
    )
    h.run(200)
    assert [d for d in h.decisions if "(mediaspiller 1)" in d.reason]


def test_P10_the_opening_survives_a_slow_atem() -> None:
    """Review finding: the ATEM shows the opening 0.8 s late; that is not a person's cut."""
    h = started()
    h.atem = LOGO_MP1
    h.run(300)
    h.command(StartShow())
    h.run(800)
    follow(h)
    h.run(200)
    assert h.engine.hold is None
    assert h.engine.quiet_until < h.now
