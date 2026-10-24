"""AU-4: leakage between mics and ``S6`` (muted on the mixer), on synthetic multitrack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from cutcut.audio.analyzer import FRAME, Analyzer
from cutcut.audio.channels import CHANNELS, MAIN_MIX, mic_channel
from cutcut.audio.leak import DEFAULT_LEAK_DB, LeakDetector, LeakMeasurer
from cutcut.audio.mainmix import MainMixWatch
from cutcut.common.config import load_site
from cutcut.common.ids import MicId
from cutcut.common.models.baseline import AudioBaseline, Baseline
from tests.unit.audio.test_analyzer import SR, speechlike

ROOT = Path(__file__).resolve().parents[3]


def studio(
    seconds: float,
    talkers: dict[MicId, tuple[float, float]],
    *,
    leak_db: float = -22.0,
    muted: frozenset[MicId] = frozenset(),
    main: bool = True,
    seed: int = 11,
) -> np.ndarray:
    """Every mic hears every voice ``leak_db`` down. The main mix carries the unmuted voices
    through «the mixer»: 2 ms later, gain, and a soft compressor (tanh)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = (rng.standard_normal((n, CHANNELS)) * 10 ** (-65 / 20)).astype(np.float32)
    voices: dict[MicId, np.ndarray] = {}
    for mic, (a, b) in talkers.items():
        v = np.zeros(n, dtype=np.float32)
        ia, ib = int(a * SR), int(b * SR)
        v[ia:ib] = speechlike((ib - ia) / SR)
        voices[mic] = v
    mix = np.zeros(n, dtype=np.float32)
    for mic in MicId:
        ch = mic_channel(mic)
        for other, v in voices.items():
            out[:, ch] += v if other is mic else v * 10 ** (leak_db / 20)
    for mic, v in voices.items():
        if mic not in muted:
            mix += v
    if main:
        delayed = np.concatenate([np.zeros(96, np.float32), mix[:-96]])
        processed = np.tanh(delayed * 3.0) * 0.4
        for ch in MAIN_MIX:
            out[:, ch] += processed
    return out


def run(x: np.ndarray, analyzer: Analyzer | None = None) -> list[dict[str, Any]]:
    a = analyzer or Analyzer()
    return [a.feed(x[i : i + FRAME])["mics"] for i in range(0, len(x) - FRAME + 1, FRAME)]


def share(frames: list[dict[str, Any]], mic: str, key: str, a: float, b: float) -> float:
    """Share of frames between a and b seconds where ``key`` is true (only active frames)."""
    rows = [f[mic] for f in frames[int(a * 100) : int(b * 100)] if f[mic]["pause_ms"] == 0]
    return sum(bool(r[key]) for r in rows) / len(rows) if rows else 0.0


# -- leakage ---------------------------------------------------------------------------------


def test_a_mic_that_only_hears_its_neighbour_is_leak() -> None:
    frames = run(studio(4.0, {MicId.M1: (0.5, 3.5)}, leak_db=-14.0))
    assert share(frames, "M1", "leak", 1.0, 3.4) == 0.0
    # M2 hears M1 14 dB down: loud enough for the VAD, but it is not M2 talking.
    active_m2 = [f["M2"] for f in frames[100:340] if f["M2"]["pause_ms"] == 0]
    assert active_m2, "the test needs M2 to look active"
    assert sum(r["leak"] for r in active_m2) / len(active_m2) > 0.9


def test_two_people_talking_at_once_are_both_talking_not_leak() -> None:
    frames = run(studio(4.0, {MicId.M1: (0.5, 3.5), MicId.M2: (0.5, 3.5)}, leak_db=-14.0))
    assert share(frames, "M1", "leak", 1.0, 3.4) < 0.05
    assert share(frames, "M2", "leak", 1.0, 3.4) < 0.05


def test_the_measured_matrix_is_used_instead_of_the_default() -> None:
    """A badly placed mic leaks −10 dB: the default (−18 dB) misses it, the baseline not."""
    x = studio(4.0, {MicId.M1: (0.5, 3.5)}, leak_db=-10.0)
    default = run(x)
    measured = run(x, Analyzer(leak_db={MicId.M1: {m: -10.0 for m in MicId if m != MicId.M1}}))
    assert share(default, "M2", "leak", 1.0, 3.4) < share(measured, "M2", "leak", 1.0, 3.4)
    assert share(measured, "M2", "leak", 1.0, 3.4) > 0.9


def test_detector_rules() -> None:
    d = LeakDetector()
    assert d.gain(MicId.M1, MicId.M2) == DEFAULT_LEAK_DB
    lv = {MicId.M1: -20.0, MicId.M2: -40.0}
    on = {MicId.M1: True, MicId.M2: True}
    for _ in range(20):
        got = d.feed(lv, on)
    assert got == {MicId.M1: False, MicId.M2: True}
    for _ in range(20):
        got = d.feed({MicId.M1: -20.0, MicId.M2: -24.0}, on)  # own voice, just a bit quieter
    assert got == {MicId.M1: False, MicId.M2: False}
    # A quiet mic is never «leak»: there is nothing to explain away.
    assert d.feed(lv, {MicId.M1: True, MicId.M2: False})[MicId.M2] is False


def test_setup_step_5_measures_the_matrix() -> None:
    m = LeakMeasurer()
    for talker in (MicId.M1, MicId.M2):
        x = studio(3.0, {talker: (0.2, 2.8)}, leak_db=-21.0, main=False)
        a = Analyzer()
        for i in range(0, len(x) - FRAME + 1, FRAME):
            a.feed(x[i : i + FRAME])
            m.feed(talker, {mic: s.level_db for mic, s in a.mics.items()})
    got = m.result()
    assert set(got) == {MicId.M1, MicId.M2}  # M3–M5 never talked: left out
    assert got[MicId.M1][MicId.M2] == pytest.approx(-21.0, abs=1.5)
    assert got[MicId.M2][MicId.M1] == pytest.approx(-21.0, abs=1.5)
    # It goes straight into baseline.yaml.
    Baseline(audio=AudioBaseline(leak_db=got))


def test_too_little_speech_is_not_a_measurement() -> None:
    m = LeakMeasurer()
    for _ in range(50):
        m.feed(MicId.M1, {MicId.M1: -20.0, MicId.M2: -40.0})
    m.feed(MicId.M3, {MicId.M3: -70.0, MicId.M1: -80.0})  # a breath
    assert m.result() == {}
    assert m.frames(MicId.M3) == 0


def test_baseline_rejects_nonsense() -> None:
    with pytest.raises(ValueError, match="lekker ikke til seg selv"):
        AudioBaseline(leak_db={MicId.M1: {MicId.M1: -20.0}})
    with pytest.raises(ValueError, match="mellom"):
        AudioBaseline(leak_db={MicId.M1: {MicId.M2: 5.0}})


def test_site_without_baseline_loads_empty(tmp_path: Path) -> None:
    import shutil

    site = tmp_path / "site"
    shutil.copytree(ROOT / "site" / "example", site)
    assert load_site(site).baseline.audio.leak_db == {}
    (site / "baseline.yaml").write_text(
        "schema_version: 1\naudio:\n  leak_db:\n    M1: { M2: -21.5 }\n", encoding="utf-8"
    )
    assert load_site(site).baseline.audio.leak_db[MicId.M1][MicId.M2] == -21.5


# -- S6: muted on the mixer ------------------------------------------------------------------


def test_S6_a_muted_mic_is_out_of_the_main_mix_within_a_second() -> None:
    frames = run(studio(5.0, {MicId.M2: (0.5, 4.5)}, muted=frozenset({MicId.M2})))
    # Unknown until the main mix has carried sound: assume in the mix (never block a cut).
    assert frames[100]["M2"]["in_main_mix"] is True
    frames = run(
        studio(8.0, {MicId.M1: (0.3, 2.3), MicId.M2: (3.0, 7.5)}, muted=frozenset({MicId.M2}))
    )
    assert share(frames, "M1", "in_main_mix", 1.0, 2.2) == 1.0
    out_at = next(i for i, f in enumerate(frames) if i > 300 and f["M2"]["in_main_mix"] is False)
    assert out_at - 300 <= 120  # 1.2 s after M2 started talking
    assert share(frames, "M2", "in_main_mix", 4.5, 7.4) == 0.0


def test_S6_an_audible_mic_stays_in_the_mix_through_the_mixer() -> None:
    """EQ/compression and 2 ms delay in the mixer must not look like a muted mic."""
    frames = run(studio(8.0, {MicId.M1: (0.3, 2.3), MicId.M2: (3.0, 7.5)}))
    assert share(frames, "M2", "in_main_mix", 3.0, 7.4) == 1.0


def test_S6_crosstalk_with_one_muted() -> None:
    frames = run(
        studio(
            8.0,
            {MicId.M1: (0.3, 7.5), MicId.M2: (2.0, 7.5)},
            muted=frozenset({MicId.M2}),
            seed=5,
        )
    )
    assert share(frames, "M1", "in_main_mix", 1.0, 7.4) == 1.0
    assert share(frames, "M2", "in_main_mix", 4.0, 7.4) == 0.0


def test_S6_unmuting_brings_the_mic_back_at_once() -> None:
    w = MainMixWatch()
    rng = np.random.default_rng(2)
    env = -25 + 8 * np.sin(np.arange(400) * 2 * np.pi / 25)  # syllables, 4 Hz
    for i in range(150):  # main mix alive, mic muted: main stays flat
        w.feed(-30.0 if i < 5 else -60.0 + rng.normal(0, 0.1), {"M2": env[i]}, {"M2": True})
    assert w.feed(-60.0, {"M2": env[150]}, {"M2": True})["M2"] is False
    got = []
    for i in range(151, 260):  # fader up: main follows
        got.append(w.feed(env[i] - 5, {"M2": env[i]}, {"M2": True})["M2"])
    assert got[-1] is True
    assert got.index(True) < 60


def test_S6_without_main_mix_channels_nothing_is_judged() -> None:
    x = studio(4.0, {MicId.M2: (0.5, 3.5)}, muted=frozenset({MicId.M2}))
    frames = run(x, Analyzer(main_mix=None))
    assert all(f["M2"]["in_main_mix"] for f in frames)


@pytest.mark.parametrize("muted", [True, False])
def test_core_does_not_cut_to_a_muted_person_S6(muted: bool) -> None:
    """End to end: analyzer output into the real engine; the muted talker never gets the shot
    (and the same talker, audible, does – so the test shows it is S6 that holds it back)."""
    from cutcut.common.clock import FakeClock
    from cutcut.common.config import (
        effective_rules,
        example_site_dir,
        load_rule_presets,
    )
    from cutcut.core.engine import Engine
    from cutcut.core.inputs import EngineConfig
    from cutcut.core.runtime import TICK_MS, CoreRuntime, RecordingExecutor

    site = load_site(example_site_dir())
    show = site.shows["samtale"]
    eng = Engine(EngineConfig.from_show(show, effective_rules(show, load_rule_presets())), now_ms=0)
    clock = FakeClock()
    rt = CoreRuntime(eng, clock, RecordingExecutor())
    x = studio(
        14.0,
        {MicId.M1: (0.3, 3.0), MicId.M2: (3.5, 13.5)},
        muted=frozenset({MicId.M2}) if muted else frozenset(),
    )
    shots = []
    a = Analyzer()
    for i in range(0, len(x) - FRAME + 1, FRAME):
        rt.feed_bus("audio.frame", a.feed(x[i : i + FRAME]))
        if (i // FRAME) % (TICK_MS // 10) == 0:
            clock.advance(TICK_MS)
            rt.tick()
            shots.append(rt.engine.program)
    assert ("CU:P2" in shots[-100:]) is not muted


# -- P13: the session's own leakage ----------------------------------------------------------


def test_P13_adaptive_leak_learns_the_session_within_limits() -> None:
    from cutcut.audio.leak import ADAPT_LIMIT_DB, AdaptiveLeak

    base = LeakDetector({MicId.M1: {MicId.M2: -18.0}})
    ad = AdaptiveLeak(base)
    # M1 talks alone; M2 hears it 13 dB down (the mic was moved closer)
    for _ in range(20_000):
        assert ad.observe({MicId.M1: -20.0, MicId.M2: -33.0, MicId.M3: -75.0}) is MicId.M1
    assert ad.gain(MicId.M1, MicId.M2) == pytest.approx(-13.0, abs=0.5)
    assert MicId.M3 not in ad.adapted[MicId.M1]  # at the noise floor: not measurable
    # a wild measurement is held within the limit of setup's value
    far = AdaptiveLeak(LeakDetector({MicId.M1: {MicId.M2: -30.0}}))
    for _ in range(20_000):
        far.observe({MicId.M1: -20.0, MicId.M2: -32.0})
    assert far.gain(MicId.M1, MicId.M2) == -30.0 + ADAPT_LIMIT_DB
    # two people talking: nothing is measured
    before = dict(ad.solo_frames)
    assert ad.observe({MicId.M1: -20.0, MicId.M2: -24.0}) is None
    assert ad.solo_frames == before
    ad.reset()
    assert ad.gain(MicId.M1, MicId.M2) == -18.0


def test_P13_shadow_publishes_the_other_opinion_and_on_uses_it() -> None:
    from cutcut.audio.main import apply_config

    x = studio(4.0, {MicId.M1: (0.5, 3.5)}, leak_db=-14.0)
    # setup measured −22 dB; in this session the mics leak −14 dB (within the ±6 dB limit:
    # the session's matrix can reach −16 dB)
    a = Analyzer(leak_db={MicId.M1: {m: -22.0 for m in MicId if m != MicId.M1}})
    off = run(x, a)
    assert "leak_other" not in off[200]["M2"]
    apply_config(a, {"adapt": "shadow", "session": "s1"})
    a.adapt.adapted[MicId.M1] = {m: -14.0 for m in MicId if m != MicId.M1}  # learned
    shadow = run(x, a)
    assert share(shadow, "M2", "leak", 1.0, 3.4) < 0.5  # setup's matrix misses it
    assert share(shadow, "M2", "leak_other", 1.0, 3.4) > 0.9  # the session's catches it
    apply_config(a, {"adapt": "on", "session": "s1"})
    on = run(x, a)
    assert share(on, "M2", "leak", 1.0, 3.4) > 0.9
    apply_config(a, {"session": "s2"})  # a new session starts over
    assert a.adapt.adapted == {}
