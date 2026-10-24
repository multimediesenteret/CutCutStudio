"""P11: WAV files from the RØDECaster are placed in time against feilsøkingsmodus by their
level alone, and packed with the measurements and decisions."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from cutcut.audio.dsp import Array
from cutcut.common.ids import MicId
from cutcut.recordings.importer import (
    MicFile,
    RecordingError,
    align,
    expired,
    load_levels,
    main_import,
    place,
)
from cutcut.recordings.wav import envelope, file_envelope, read_wav, write_wav

RATE = 16_000
T0 = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)


def speech(seconds: float, seed: int) -> Array:
    """Bursts of noise with pauses, like one person talking now and then."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    x = np.zeros(n, dtype=np.float32)
    i = 0
    while i < n:
        talk = int(rng.uniform(0.3, 3.0) * RATE)
        pause = int(rng.uniform(0.1, 2.0) * RATE)
        amp = rng.uniform(0.05, 0.4)
        x[i : i + talk] = (rng.standard_normal(min(talk, n - i)) * amp).astype(np.float32)
        i += talk + pause
    x += (rng.standard_normal(n) * 0.0005).astype(np.float32)  # room noise
    return x


def debug_records(levels: dict[str, Array], start: datetime) -> list[dict[str, Any]]:
    n = min(a.size for a in levels.values())
    out = []
    for i in range(n):
        t = start + timedelta(milliseconds=10 * i)
        mics = {m: {"level_db": float(a[i]), "vad": 0.5} for m, a in levels.items()}
        out.append(
            {
                "t": t.isoformat(timespec="milliseconds"),
                "mono": i * 10,
                "kind": "bus",
                "topic": "audio.frame",
                "data": {"mics": mics},
            }
        )
    return out


@pytest.fixture
def studio(tmp_path: Path) -> dict[str, Any]:
    """Three minutes of two mics. The RØDECaster started 42.37 s after feilsøkingsmodus."""
    a, b = speech(180, 1), speech(180, 2)
    a_leak = a + 0.05 * b  # each mic hears a little of the other
    b_leak = b + 0.05 * a
    debug = debug_records({"M1": envelope(a_leak, RATE), "M2": envelope(b_leak, RATE)}, T0)
    offset = 4237  # samples of 10 ms: the WAV starts 42.37 s in
    cut = offset * RATE // 100
    write_wav(tmp_path / "mic1.wav", a_leak[cut:], RATE)
    write_wav(tmp_path / "mic2.wav", b_leak[cut:], RATE)
    data = tmp_path / "data"
    (data / "debug").mkdir(parents=True)
    with gzip.open(data / "debug" / "2026-11-04T09.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in debug:
            f.write(json.dumps(r) + "\n")
    return {"dir": tmp_path, "data": data, "debug": debug, "start": T0 + timedelta(seconds=42.37)}


def test_wav_round_trip_24_bit(tmp_path: Path) -> None:
    x = np.clip(speech(2, 3), -1.0, 1.0)
    write_wav(tmp_path / "x.wav", x, RATE)
    w = read_wav(tmp_path / "x.wav")
    assert w.rate == RATE
    assert w.channels == 1
    assert np.max(np.abs(w.channel(0) - x)) < 1e-6
    env, h = file_envelope(tmp_path / "x.wav", chunk_s=1)
    assert h.frames == x.size
    assert np.allclose(env, envelope(x, RATE), atol=0.01)


def test_align_finds_the_offset() -> None:
    ref = envelope(speech(120, 5), RATE)
    k, score = align(ref[3000:], ref)
    assert k == 3000
    assert score > 0.99


def test_files_are_placed_to_the_10_ms(studio: dict[str, Any]) -> None:
    levels = load_levels(studio["debug"])
    assert levels is not None
    files = [
        MicFile(MicId.M1, studio["dir"] / "mic1.wav"),
        MicFile.parse(f"M2={studio['dir'] / 'mic2.wav'}"),
    ]
    placed = place(files, levels)
    for p in placed:
        assert abs((p.start - studio["start"]).total_seconds()) <= 0.01
        assert p.score > 0.9


def test_swapped_files_are_noticed(studio: dict[str, Any]) -> None:
    levels = load_levels(studio["debug"])
    assert levels is not None
    swapped = [MicFile(MicId.M1, studio["dir"] / "mic2.wav")]
    (p,) = place(swapped, levels)
    assert p.score < 0.6  # the wrong person's voice does not match M1's level


def test_the_package_needs_consent_and_holds_everything(
    studio: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    out = studio["dir"] / "pakker"
    wavs = [f"M1={studio['dir'] / 'mic1.wav'}", f"M2={studio['dir'] / 'mic2.wav'}"]
    assert main_import(wavs, "ep1", False, studio["data"], out) == 2
    assert "samtykke" in capsys.readouterr().out
    assert not out.exists()
    assert main_import(wavs, "ep1", True, studio["data"], out) == 0
    folder = out / "ep1"
    assert (folder / "mic" / "M1.wav").exists()
    meta = (folder / "meta.yaml").read_text(encoding="utf-8")
    assert "consent: true" in meta
    assert "delete_after: '2027-" in meta or "delete_after: 2027-" in meta
    with gzip.open(folder / "measures.jsonl.gz", "rt", encoding="utf-8") as f:
        first = json.loads(f.readline())
    assert datetime.fromisoformat(first["t"]) >= studio["start"] - timedelta(milliseconds=10)
    assert main_import(wavs, "ep1", True, studio["data"], out) == 1  # never overwritten


def test_parse_mic_specs() -> None:
    assert MicFile.parse("m3=C:\\opptak\\fil.wav") == MicFile(MicId.M3, Path("C:\\opptak\\fil.wav"))
    mf = MicFile.parse("M2=multitrack.wav:3")
    assert (mf.path, mf.channel) == (Path("multitrack.wav"), 2)
    with pytest.raises(RecordingError):
        MicFile.parse("mic1.wav")


def test_expired_packages_are_found(tmp_path: Path) -> None:
    old = tmp_path / "gammel"
    old.mkdir()
    (old / "meta.yaml").write_text("delete_after: '2026-01-01'\n", encoding="utf-8")
    new = tmp_path / "ny"
    new.mkdir()
    (new / "meta.yaml").write_text("delete_after: '2027-10-24'\n", encoding="utf-8")
    assert expired(tmp_path, datetime(2026, 10, 24, tzinfo=UTC)) == [old]
