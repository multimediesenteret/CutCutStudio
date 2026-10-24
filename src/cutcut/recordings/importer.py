"""P11: put the studio period's recordings together into replay packages.

CutCut records no audio itself. In the studio period the RØDECaster records every mic to its
own card, the ATEM records ISO, and feilsøkingsmodus writes every measurement (``level_db``
per mic every 10 ms) and every decision. This module finds where each WAV file sits in time
by comparing its level, 10 ms by 10 ms, with ``level_db`` in the recording: no clap and no
timecode needed (the clap in ``docs/intake/opptak-og-klippeliste.md`` is a check).

``cutcut opptak importer --wav M1=mic1.wav --wav M2=mic2.wav … --episode navn --samtykke``
writes ``<out>/<episode>/``:

| File | What |
| --- | --- |
| ``meta.yaml`` | When each WAV starts, how sure the match is, consent, delete date (D-072) |
| ``mic/`` | The WAV files as recorded (copied, never changed) |
| ``measures.jsonl.gz`` | Feilsøkingsmodus for the same span: measurements, intents, presses |
| ``decisions.jsonl`` | CutCut's decisions for the same span, from the database |

``cutcut opptak rydd`` deletes packages whose time is up. Packages never go into git.
"""

from __future__ import annotations

import gzip
import json
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

import numpy as np
from ruamel.yaml import YAML

from cutcut.app.debugrec import read
from cutcut.audio.dsp import Array
from cutcut.common.ids import MicId
from cutcut.recordings.wav import FRAME_MS, WavError, file_envelope

FLOOR_DB: Final = -70.0  # below this is room noise: flattened so silence does not match silence
MIN_OVERLAP_S: Final = 60.0
GOOD_SCORE: Final = 0.6  # Pearson correlation of the two level curves at the found offset
AGREE_MS: Final = 40  # the mics of one episode must agree this well on where they start
KEEP_DAYS: Final = 365  # D-072, Q43


class RecordingError(RuntimeError):
    """Something the technician must fix. The message is for the screen."""


@dataclass(frozen=True)
class MicFile:
    mic: MicId
    path: Path
    channel: int = 0

    @classmethod
    def parse(cls, spec: str) -> MicFile:
        """``M2=C:\\opptak\\mic2.wav`` or ``M2=multitrack.wav:3`` (channel 3, from 1)."""
        mic, sep, rest = spec.partition("=")
        if not sep or mic.upper() not in MicId.__members__:
            raise RecordingError(f"Skriv mikrofon=fil, f.eks. M2=mic2.wav (fikk «{spec}»)")
        channel = 0
        path = rest
        head, colon, tail = rest.rpartition(":")
        if colon and tail.isdigit() and head and not (len(head) == 1 and head.isalpha()):
            path, channel = head, int(tail) - 1
        return cls(MicId(mic.upper()), Path(path), channel)


@dataclass
class Levels:
    """``level_db`` per mic on a 10 ms grid from ``start`` (from feilsøkingsmodus)."""

    start: datetime
    mics: dict[MicId, Array] = field(default_factory=dict)


def load_levels(records: Sequence[dict[str, Any]]) -> Levels | None:
    frames: list[tuple[datetime, dict[str, Any]]] = []
    for r in records:
        if r.get("kind") == "bus" and r.get("topic") == "audio.frame":
            mics = (r.get("data") or {}).get("mics") or {}
            frames.append((datetime.fromisoformat(str(r["t"])), mics))
    if not frames:
        return None
    start = frames[0][0]
    n = int((frames[-1][0] - start).total_seconds() * 1000 // FRAME_MS) + 1
    out = Levels(start)
    for mic in MicId:
        out.mics[mic] = np.full(n, np.nan, dtype=np.float32)
    for t, mics in frames:
        i = int((t - start).total_seconds() * 1000 // FRAME_MS)
        for name, frame in mics.items():
            if name in MicId.__members__ and isinstance(frame, dict) and "level_db" in frame:
                out.mics[MicId(name)][i] = float(frame["level_db"])
    for mic in list(out.mics):
        a = out.mics[mic]
        if np.isnan(a).all():
            del out.mics[mic]
            continue
        # fill the gaps (a dropped message) with the last value
        idx = np.where(~np.isnan(a), np.arange(a.size), 0)
        np.maximum.accumulate(idx, out=idx)
        out.mics[mic] = a[idx]
    return out


def _prep(x: Array) -> Array:
    y = np.maximum(x.astype(np.float64), FLOOR_DB)
    out: Array = (y - y.mean()).astype(np.float32)
    return out


def align(wav: Array, ref: Array) -> tuple[int, float]:
    """Where ``wav`` frame 0 lies in ``ref`` (in 10 ms frames, may be negative) and how well
    the two level curves agree there (Pearson, -1..1). FFT cross-correlation, then the
    correlation of the overlap at the best few candidates."""
    a, b = _prep(wav), _prep(ref)
    n = a.size + b.size - 1
    size = 1 << (n - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(b, size) * np.conj(np.fft.rfft(a, size)), size)
    # corr[k] = sum b[i + k] a[i]: lag k >= 0 at k, negative lags at the end
    lags = np.concatenate([np.arange(0, b.size), np.arange(-(a.size - 1), 0)])
    vals = np.concatenate([corr[: b.size], corr[size - (a.size - 1) :]])
    best, best_score = 0, -1.0
    min_overlap = int(MIN_OVERLAP_S * 1000 / FRAME_MS)
    for k in lags[np.argsort(vals)[::-1][:20]]:
        k = int(k)
        lo, hi = max(0, k), min(b.size, k + a.size)
        if hi - lo < min(min_overlap, a.size, b.size):
            continue
        x, y = a[lo - k : hi - k], b[lo:hi]
        if x.std() == 0 or y.std() == 0:
            continue
        score = float(np.corrcoef(x, y)[0, 1])
        if score > best_score:
            best, best_score = k, score
    return best, best_score


@dataclass(frozen=True)
class Placed:
    file: MicFile
    start: datetime  # wall time of the WAV's first sample
    seconds: float
    score: float


def place(files: Sequence[MicFile], levels: Levels) -> list[Placed]:
    out = []
    for mf in files:
        if not mf.path.exists():
            raise RecordingError(f"Finner ikke {mf.path}")
        ref = levels.mics.get(mf.mic)
        if ref is None:
            raise RecordingError(
                f"Feilsøkingsopptaket har ingen lyd fra {mf.mic.value} i denne perioden. "
                "Var feilsøkingsmodus på?"
            )
        try:
            env, h = file_envelope(mf.path, mf.channel)
        except WavError as exc:
            raise RecordingError(str(exc)) from exc
        k, score = align(env, ref)
        start = levels.start + timedelta(milliseconds=k * FRAME_MS)
        out.append(Placed(mf, start, h.frames / h.rate, score))
    return out


def check(placed: Sequence[Placed]) -> list[str]:
    """Plain warnings: a weak match, or mics of one recording that disagree."""
    notes = []
    for p in placed:
        if p.score < GOOD_SCORE:
            notes.append(
                f"{p.file.mic.value}: svak match ({p.score:.2f}). Riktig fil for riktig mikrofon?"
            )
    starts = sorted(p.start for p in placed)
    if starts and (starts[-1] - starts[0]) > timedelta(milliseconds=AGREE_MS):
        spread = (starts[-1] - starts[0]).total_seconds() * 1000
        notes.append(
            f"Filene starter {spread:.0f} ms fra hverandre. Fra samme opptak skulle de vært like."
        )
    return notes


def write_package(
    out: Path,
    episode: str,
    placed: Sequence[Placed],
    records: Sequence[dict[str, Any]],
    decisions: Sequence[dict[str, Any]],
    now: datetime,
) -> Path:
    folder = out / episode
    if folder.exists():
        raise RecordingError(f"{folder} finnes fra før. Velg et annet navn på episoden.")
    (folder / "mic").mkdir(parents=True)
    start = min(p.start for p in placed)
    end = max(p.start + timedelta(seconds=p.seconds) for p in placed)
    mics = {}
    for p in placed:
        target = folder / "mic" / f"{p.file.mic.value}{p.file.path.suffix.lower()}"
        shutil.copyfile(p.file.path, target)
        mics[p.file.mic.value] = {
            "file": f"mic/{target.name}",
            "channel": p.file.channel + 1,
            "start": p.start.isoformat(timespec="milliseconds"),
            "seconds": round(p.seconds, 3),
            "match": round(p.score, 3),
        }
    meta = {
        "episode": episode,
        "created": now.isoformat(timespec="seconds"),
        "start": start.isoformat(timespec="milliseconds"),
        "end": end.isoformat(timespec="milliseconds"),
        "consent": True,
        "delete_after": (now + timedelta(days=KEEP_DAYS)).date().isoformat(),
        "mics": mics,
        "notes": check(placed),
    }
    yaml = YAML()
    with (folder / "meta.yaml").open("w", encoding="utf-8") as f:
        f.write(
            "# Opptak til justering (P11). Personopplysninger: ikke i git, slettes etter dato.\n"
        )
        yaml.dump(meta, f)
    with gzip.open(folder / "measures.jsonl.gz", "wt", encoding="utf-8") as g:
        for r in records:
            t = datetime.fromisoformat(str(r["t"]))
            if start <= t <= end:
                g.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (folder / "decisions.jsonl").open("w", encoding="utf-8") as f:
        for d in decisions:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    return folder


def expired(out: Path, today: datetime) -> list[Path]:
    """Packages whose ``delete_after`` has passed."""
    gone = []
    yaml = YAML(typ="safe")
    for meta in sorted(out.glob("*/meta.yaml")):
        data = yaml.load(meta.read_text(encoding="utf-8")) or {}
        when = str(data.get("delete_after") or "")
        if when and when < today.date().isoformat():
            gone.append(meta.parent)
    return gone


def main_import(
    wavs: Sequence[str],
    episode: str,
    consent: bool,
    data: Path,
    out: Path,
) -> int:
    from cutcut.hwtest.acceptance import load_decisions

    if not consent:
        print(
            "Stopper: opptak av stemmer krever skriftlig samtykke fra alle som er med (D-072). "
            "Når det er på plass, kjør på nytt med --samtykke."
        )
        return 2
    try:
        files = [MicFile.parse(s) for s in wavs]
        if not files:
            raise RecordingError("Ingen filer. Bruk --wav M1=mic1.wav (én per mikrofon).")
        records = read(sorted((data / "debug").glob("*.jsonl.gz")))
        levels = load_levels(records)
        if levels is None:
            raise RecordingError(
                f"Fant ingen lydmålinger i {data / 'debug'}. Feilsøkingsmodus må være på "
                "under opptaket (Helse → Feilsøkingsmodus)."
            )
        placed = place(files, levels)
        start = min(p.start for p in placed)
        end = max(p.start + timedelta(seconds=p.seconds) for p in placed)
        db = data / "cutcut.db"
        decisions = load_decisions(db, start, end) if db.exists() else []
        folder = write_package(
            out, episode, placed, records, decisions, datetime.now().astimezone()
        )
    except RecordingError as exc:
        print(f"Stopper: {exc}")
        return 1
    for p in placed:
        print(f"{p.file.mic.value}: starter {p.start:%H:%M:%S.%f}"[:-3] + f", match {p.score:.2f}")
    for note in check(placed):
        print(f"OBS: {note}")
    print(f"Skrev {folder} ({len(decisions)} beslutninger). Slettes senest om 12 måneder.")
    return 0


def main_clean(out: Path, yes: bool) -> int:
    gone = expired(out, datetime.now().astimezone())
    if not gone:
        print("Ingen opptak har gått ut på tid.")
        return 0
    for folder in gone:
        if yes:
            shutil.rmtree(folder)
            print(f"Slettet {folder}")
        else:
            print(f"Skal slettes: {folder}")
    if not yes:
        print("Kjør med --ja for å slette.")
    return 0
