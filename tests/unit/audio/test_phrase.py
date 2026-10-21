"""AU-3: phrase boundaries (pause, energy fall, falling pitch) against golden files.

The golden file ``tests/fixtures/audio/phrases.json`` holds, for each synthetic phrase, when
the mic goes active, when the phrase end is reported and whether the pitch fell. Update it
on purpose with ``CUTCUT_UPDATE_GOLDEN=1 uv run pytest tests/unit/audio/test_phrase.py``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from cutcut.audio.analyzer import FRAME, Analyzer
from cutcut.audio.phrase import PhraseTracker, semitones, yin
from tests.unit.audio.voices import Phrase, track

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "audio" / "phrases.json"
TOLERANCE_MS = 30  # a frame or three, for float differences between machines

SCENARIOS: dict[str, tuple[str, Phrase]] = {
    "statement": (
        "Påstand: tonen faller og stemmen dør ut. Frasegrense allerede etter 150 ms.",
        Phrase(0.5, 1.6, (150, 150, 105), fade_db=-9),
    ),
    "statement_steady": (
        "Tonen faller, men stemmen holder styrken. Frasegrense etter 150 ms (tonehøyde).",
        Phrase(0.5, 1.6, (150, 150, 105)),
    ),
    "trailing_off": (
        "Tonen er flat, men stemmen dør ut. Frasegrense etter 150 ms (energi).",
        Phrase(0.5, 1.6, (140, 140, 140), fade_db=-12),
    ),
    "question": (
        "Spørsmål: tonen stiger. Frasegrense først etter 250 ms pause.",
        Phrase(0.5, 1.6, (140, 140, 200)),
    ),
    "flat": (
        "Flat tone og styrke. Frasegrense etter 250 ms pause.",
        Phrase(0.5, 1.6, (140, 140, 140)),
    ),
    "hesitation": (
        "Kort nøling (100 ms) midt i: ingen frasegrense der, bare på slutten.",
        Phrase(0.5, 2.0, (140, 140, 140), gap=(0.9, 1.0)),
    ),
    "low_voice": (
        "Dyp stemme (85 Hz) som faller til 70 Hz.",
        Phrase(0.5, 1.6, (85, 85, 70)),
    ),
}


def events(p: Phrase) -> list[list[Any]]:
    x = track(3.0, [p])
    a = Analyzer()
    out: list[list[Any]] = []
    prev: dict[str, bool] = {}
    for i in range(0, len(x) - FRAME + 1, FRAME):
        f = a.feed(x[i : i + FRAME])["mics"]["M1"]
        now = {
            "active": f["pause_ms"] == 0,
            "phrase_end": f["phrase_end"],
            "pitch_falling": f["pitch_falling"],
        }
        for k, v in now.items():
            if prev.get(k, False) != v and i > 0:
                out.append([i // FRAME * 10, k, v])
        prev = now
    return out


def dump(got: dict[str, Any]) -> str:
    """One event per line, so a change in the golden file reads well in a diff."""
    parts = []
    for name, v in got.items():
        ev = ",\n".join(f"   {json.dumps(e)}" for e in v["events"])
        what = json.dumps(v["what"], ensure_ascii=False)
        parts.append(f' "{name}": {{\n  "what": {what},\n  "events": [\n{ev}\n  ]\n }}')
    return "{\n" + ",\n".join(parts) + "\n}\n"


def test_phrase_boundaries_match_the_golden_file() -> None:
    got = {name: {"what": what, "events": events(p)} for name, (what, p) in SCENARIOS.items()}
    if os.environ.get("CUTCUT_UPDATE_GOLDEN"):
        GOLDEN.write_text(dump(got), encoding="utf-8")
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert set(got) == set(want)
    for name in want:
        g, w = got[name]["events"], want[name]["events"]
        assert [e[1:] for e in g] == [e[1:] for e in w], name
        for ge, we in zip(g, w, strict=True):
            assert abs(ge[0] - we[0]) <= TOLERANCE_MS, (name, ge, we)


def _end(name: str) -> tuple[int, int | None, bool]:
    """(ms the phrase stopped, ms phrase_end came, pitch fell) from the golden events."""
    ev = events(SCENARIOS[name][1])
    stop = max(t for t, k, v in ev if k == "active" and v is False)
    end = next((t for t, k, v in ev if k == "phrase_end" and v and t >= stop), None)
    fell = any(k == "pitch_falling" and v for _, k, v in ev)
    return stop, end, fell


@pytest.mark.parametrize(
    ("name", "pause_ms", "fell"),
    [
        ("statement", 150, True),
        ("statement_steady", 150, True),
        ("trailing_off", 150, False),
        ("question", 250, False),
        ("flat", 250, False),
        ("hesitation", 250, False),
        ("low_voice", 150, True),
    ],
)
def test_the_spec_rules_K2(name: str, pause_ms: int, fell: bool) -> None:
    """Spec 5.10: 250 ms pause, or 150 ms with falling pitch (or a voice that trails off)."""
    stop, end, got_fell = _end(name)
    assert end is not None
    assert end - stop + 10 == pause_ms  # pause_ms is 10 in the first quiet frame
    assert got_fell is fell


def test_a_short_hesitation_is_not_a_phrase_end() -> None:
    ev = events(SCENARIOS["hesitation"][1])
    first_stop = min(t for t, k, v in ev if k == "active" and v is False)
    assert not any(k == "phrase_end" and v and t < first_stop + 200 for t, k, v in ev)


@pytest.mark.parametrize("f0", [70.0, 110.0, 180.0, 260.0, 420.0])
def test_yin_finds_the_pitch_of_a_harmonic_tone(f0: float) -> None:
    t = np.arange(1200) / 16_000
    x = np.sum([np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 9)], axis=0)
    x = x.astype(np.float32)
    got = yin(x)
    assert got is not None
    assert abs(semitones(got) - semitones(f0)) < 0.1


def test_yin_says_nothing_about_noise_or_too_little_audio() -> None:
    rng = np.random.default_rng(1)
    assert yin(rng.standard_normal(1200).astype(np.float32)) is None
    assert yin(np.zeros(100, dtype=np.float32)) is None


def test_silent_mics_cost_no_pitch_analysis() -> None:
    tr = PhraseTracker()
    calls = 0
    import cutcut.audio.phrase as ph

    real = ph.yin

    def counting(x: Any) -> Any:
        nonlocal calls
        calls += 1
        return real(x)

    ph.yin = counting  # type: ignore[assignment]
    try:
        for _ in range(100):
            tr.feed(np.zeros(160, dtype=np.float32), -90.0, active=False, pause_ms=1000)
    finally:
        ph.yin = real
    assert calls == 0


def test_phrase_analysis_fits_the_time_budget() -> None:
    """Five mics all talking: the whole frame stays inside the spec's 3 ms (CI: 6 ms)."""
    from cutcut.audio.channels import mic_channel
    from cutcut.common.ids import MicId

    x = track(2.0, [Phrase(0.0, 2.0, (140, 140, 120))])
    for mic in MicId:
        x[:, mic_channel(mic)] = x[:, mic_channel(MicId.M1)]
    a = Analyzer()
    t0 = time.perf_counter()
    n = 0
    for i in range(0, len(x) - FRAME + 1, FRAME):
        a.feed(x[i : i + FRAME])
        n += 1
    assert (time.perf_counter() - t0) * 1000 / n < 6
