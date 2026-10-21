"""AU-1, AU-2: measurements per mic from synthetic multitrack (no persondata, no real audio)."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import numpy as np

from cutcut.audio.analyzer import FRAME, Analyzer
from cutcut.audio.backend import WavBackend, write_wav
from cutcut.audio.channels import CHANNELS, mic_channel
from cutcut.audio.dsp import Array, Decimator, rms_db
from cutcut.audio.process import run
from cutcut.common.clock import FakeClock
from cutcut.common.config import effective_rules, example_site_dir, load_rule_presets, load_site
from cutcut.common.ids import MicId
from cutcut.core.engine import Engine
from cutcut.core.inputs import EngineConfig
from cutcut.core.runtime import TICK_MS, CoreRuntime, RecordingExecutor

SR = 48_000
RNG = np.random.default_rng(7)


def speechlike(seconds: float, level_db: float = -20.0) -> Array:
    """Noise shaped like syllables: 4 Hz bursts with short gaps, band-limited."""
    n = int(seconds * SR)
    noise: Array = RNG.standard_normal(n).astype(np.float32)
    noise = np.convolve(noise, np.ones(8, dtype=np.float32) / 8, mode="same").astype(np.float32)
    t = np.arange(n) / SR
    envelope = np.clip(np.sin(2 * np.pi * 4 * t), 0.15, 1.0)
    x = noise * envelope.astype(np.float32)
    out: Array = (x / np.sqrt(np.mean(x**2)) * 10 ** (level_db / 20)).astype(np.float32)
    return out


def multitrack(
    seconds: float, talkers: dict[MicId, tuple[float, float]], leak_db: float = -22.0
) -> np.ndarray:
    """``talkers``: mic → (start s, stop s). Every mic also picks up the others at ``leak_db``."""
    n = int(seconds * SR)
    out = np.zeros((n, CHANNELS), dtype=np.float32)
    noise_floor = (RNG.standard_normal((n, CHANNELS)) * 10 ** (-65 / 20)).astype(np.float32)
    voices = {}
    for mic, (a, b) in talkers.items():
        v = np.zeros(n, dtype=np.float32)
        ia, ib = int(a * SR), int(b * SR)
        v[ia:ib] = speechlike((ib - ia) / SR)
        voices[mic] = v
    for mic in MicId:
        ch = mic_channel(mic)
        out[:, ch] = noise_floor[:, ch]
        for other, v in voices.items():
            out[:, ch] += v if other is mic else v * 10 ** (leak_db / 20)
    return out


def frames(x: Array, analyzer: Analyzer) -> list[dict[str, Any]]:
    return [analyzer.feed(x[i : i + FRAME]) for i in range(0, len(x) - FRAME + 1, FRAME)]


def test_channel_map_follows_the_rodecaster_setup() -> None:
    assert [mic_channel(m) for m in MicId] == [2, 4, 6, 8, 10]  # 1-based 3, 5, 7, 9, 11


def test_decimator_streams_like_one_shot() -> None:
    t = np.arange(SR) / SR
    x = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    whole = Decimator()(x)
    d = Decimator()
    parts = np.concatenate([d(x[i : i + FRAME]) for i in range(0, len(x), FRAME)])
    assert len(parts) == len(whole) == SR // 3
    assert np.allclose(parts, whole, atol=1e-5)
    assert abs(rms_db(whole[1000:]) - rms_db(x)) < 0.5  # 1 kHz passes unchanged


def test_one_talker_is_active_dominant_and_the_others_quiet() -> None:
    x = multitrack(4.0, {MicId.M2: (1.0, 3.0)})
    out = frames(x, Analyzer())

    def at(s: float) -> dict[str, Any]:
        mics: dict[str, Any] = out[int(s * 100)]["mics"]
        return mics

    assert at(2.0)["M2"]["vad"] > 0.5
    assert at(2.0)["M2"]["dominance_db"] > 12
    assert at(2.0)["M2"]["pause_ms"] == 0
    # M1 hears M2's voice 22 dB down. A VAD may call that speech (it is!); dominance is what
    # tells the engine it is not M1 talking (leakage proper comes in AU-4).
    assert at(2.0)["M1"]["dominance_db"] < -12
    assert at(0.8)["M2"]["vad"] < 0.5
    assert at(3.9)["M2"]["pause_ms"] >= 500  # counts up after the talker stops


def test_analysis_fits_the_time_budget() -> None:
    """Spec: one 10 ms frame for five mics in under 3 ms (CI machines: allow 6 ms)."""
    x = multitrack(3.0, {MicId.M1: (0.0, 3.0)})
    a = Analyzer()
    t0 = time.perf_counter()
    n = len(frames(x, a))
    per_frame_ms = (time.perf_counter() - t0) * 1000 / n
    assert per_frame_ms < 6


def test_wav_backend_and_process_publish_frames(tmp_path: Path) -> None:
    path = tmp_path / "mt.wav"
    write_wav(path, multitrack(1.0, {MicId.M1: (0.2, 0.8)}))
    sent: list[tuple[str, dict[str, Any]]] = []

    async def publish(topic: str, payload: dict[str, Any]) -> None:
        sent.append((topic, payload))

    n = asyncio.run(run(WavBackend(path, loop=False), Analyzer(), publish, realtime=False))
    assert n == 100
    assert sum(t == "audio.frame" for t, _ in sent) == 100
    assert sent[0][0] == "audio.status"  # status first, so core knows the backend at once
    assert any(t == "audio.status" for t, _ in sent)


def test_core_cuts_on_the_measurements_AU1() -> None:
    """«core kjører på den»: real analyzer output drives the real engine to the talker."""
    site = load_site(example_site_dir())
    show = site.shows["samtale"]
    eng = Engine(EngineConfig.from_show(show, effective_rules(show, load_rule_presets())), now_ms=0)
    clock = FakeClock()
    ex = RecordingExecutor()
    rt = CoreRuntime(eng, clock, ex)
    x = multitrack(12.0, {MicId.M1: (0.5, 4.0), MicId.M2: (4.5, 11.5)})
    out = frames(x, Analyzer())
    shots = []
    for i, payload in enumerate(out):
        rt.feed_bus("audio.frame", payload)
        if i % (TICK_MS // 10) == 0:
            clock.advance(TICK_MS)
            rt.tick()
            shots.append(rt.engine.program)
    assert "CU:P1" in shots
    assert shots[-1] == "CU:P2"


MODEL = Path(__file__).resolve().parents[3] / "models" / "silero_vad.onnx"


def test_silero_vad_when_installed() -> None:
    """The studio VAD (extra «silero» + tools/fetch_models.py). Skipped where not installed."""
    import pytest

    pytest.importorskip("onnxruntime")
    if not MODEL.exists():
        pytest.skip("models/silero_vad.onnx mangler (tools/fetch_models.py)")
    from cutcut.audio.vad import make_vad

    vad = make_vad(MODEL)
    assert vad.name == "silero"
    quiet = (RNG.standard_normal(512) * 1e-3).astype(np.float32)
    assert all(0.0 <= vad(quiet) < 0.2 for _ in range(5))
    a = Analyzer(vad_model=MODEL)
    assert a.vad_name == "silero"
    out = frames(multitrack(1.0, {}), a)
    assert max(f["mics"]["M1"]["vad"] for f in out) < 0.5


def test_missing_model_falls_back_to_energy_vad(tmp_path: Path) -> None:
    assert Analyzer(vad_model=tmp_path / "finnes-ikke.onnx").vad_name == "energy"
