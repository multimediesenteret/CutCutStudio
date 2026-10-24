"""Read WAV files from the RØDECaster's own multitrack recording (P11), with numpy only.

PCM 16, 24 and 32 bit and 32-bit float, also as WAVE_FORMAT_EXTENSIBLE, mono or with several
channels in one file. Everything comes back as float32 in -1..1.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cutcut.audio.dsp import SILENCE_DB, Array

PCM, FLOAT, EXTENSIBLE = 1, 3, 0xFFFE
FRAME_MS = 10  # the same 10 ms as audio-capture's level_db


class WavError(ValueError):
    """A file that is not a WAV this reader understands. The message is for the screen."""


@dataclass(frozen=True)
class Wav:
    rate: int
    channels: int
    data: np.ndarray  # (samples, channels), float32

    @property
    def seconds(self) -> float:
        return float(self.data.shape[0]) / self.rate

    def channel(self, index: int) -> Array:
        if not 0 <= index < self.channels:
            raise WavError(f"filen har {self.channels} kanaler, ikke kanal {index + 1}")
        out: Array = np.ascontiguousarray(self.data[:, index], dtype=np.float32)
        return out


@dataclass(frozen=True)
class Header:
    rate: int
    channels: int
    bits: int
    tag: int  # PCM or FLOAT
    offset: int  # where the samples start
    frames: int


def header(path: Path) -> Header:
    """Read only the chunk headers, so an hour-long file is never read whole (P11)."""
    with path.open("rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] not in (b"RIFF", b"RF64") or head[8:12] != b"WAVE":
            raise WavError(f"{path.name} er ikke en WAV-fil")
        fmt: bytes | None = None
        size_total = path.stat().st_size
        while True:
            ch = f.read(8)
            if len(ch) < 8:
                raise WavError(f"{path.name} mangler fmt- eller data-del")
            cid, size = ch[:4], struct.unpack("<I", ch[4:8])[0]
            if cid == b"fmt ":
                fmt = f.read(size)
                f.seek(size & 1, 1)
            elif cid == b"data":
                if fmt is None:
                    raise WavError(f"{path.name}: data før fmt")
                offset = f.tell()
                if size == 0xFFFFFFFF or offset + size > size_total:  # RF64 or cut short
                    size = size_total - offset
                tag, channels, rate = struct.unpack("<HHI", fmt[:8])
                bits = struct.unpack("<H", fmt[14:16])[0]
                if tag == EXTENSIBLE and len(fmt) >= 26:
                    tag = struct.unpack("<H", fmt[24:26])[0]
                if (tag, bits) not in ((PCM, 16), (PCM, 24), (PCM, 32), (FLOAT, 32)):
                    raise WavError(f"{path.name}: {bits} bit format {tag} støttes ikke")
                frames = size // (bits // 8 * channels)
                return Header(rate, channels, bits, tag, offset, frames)
            else:
                f.seek(size + (size & 1), 1)


def _decode(data: bytes, tag: int, bits: int) -> Array:
    if tag == FLOAT:
        x: Array = np.frombuffer(data, dtype="<f4").astype(np.float32)
        return x
    if bits == 16:
        return (np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0).astype(np.float32)
    if bits == 32:
        v32 = np.frombuffer(data, dtype="<i4").astype(np.float64)
        return (v32 / 2147483648.0).astype(np.float32)
    b = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
    v = np.where(v & 0x800000, v - 0x1000000, v)
    return (v / 8388608.0).astype(np.float32)


def read_wav(path: Path) -> Wav:
    """The whole file (tests and short files; use :func:`file_envelope` for recordings)."""
    h = header(path)
    with path.open("rb") as f:
        f.seek(h.offset)
        data = f.read(h.frames * h.bits // 8 * h.channels)
    x = _decode(data, h.tag, h.bits)
    return Wav(rate=h.rate, channels=h.channels, data=x.reshape(-1, h.channels))


def file_envelope(path: Path, channel: int = 0, chunk_s: int = 30) -> tuple[Array, Header]:
    """``level_db`` per 10 ms of one channel, read 30 s at a time."""
    h = header(path)
    if not 0 <= channel < h.channels:
        raise WavError(f"{path.name} har {h.channels} kanaler, ikke kanal {channel + 1}")
    step = h.rate * FRAME_MS // 1000
    per = chunk_s * 1000 // FRAME_MS * step  # whole 10 ms frames per chunk
    width = h.bits // 8 * h.channels
    parts: list[Array] = []
    with path.open("rb") as f:
        f.seek(h.offset)
        left = h.frames
        while left > 0:
            n = min(per, left)
            data = f.read(n * width)
            if not data:
                break
            x = _decode(data, h.tag, h.bits).reshape(-1, h.channels)[:, channel]
            parts.append(envelope(np.ascontiguousarray(x), h.rate))
            left -= n
    env: Array = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
    return env, h


def envelope(x: Array, rate: int) -> Array:
    """RMS level in dB per 10 ms, as audio-capture's ``level_db`` (``rms_db``)."""
    n = rate * FRAME_MS // 1000
    frames = x.size // n
    if frames == 0:
        return np.zeros(0, dtype=np.float32)
    sq = np.square(x[: frames * n].astype(np.float64)).reshape(frames, n).mean(axis=1)
    with np.errstate(divide="ignore"):
        db = 10.0 * np.log10(sq)
    out: Array = np.maximum(np.nan_to_num(db, neginf=SILENCE_DB), SILENCE_DB).astype(np.float32)
    return out


def write_wav(path: Path, x: Array, rate: int) -> None:
    """Mono 24-bit PCM (tests, and the synthetic recordings)."""
    v = np.clip(np.round(x.astype(np.float64) * 8388607.0), -8388608, 8388607).astype(np.int32)
    b = np.empty((v.size, 3), dtype=np.uint8)
    b[:, 0], b[:, 1], b[:, 2] = v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF
    body = b.tobytes()
    fmt = struct.pack("<HHIIHH", PCM, 1, rate, rate * 3, 3, 24)
    path.write_bytes(
        b"RIFF"
        + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(body))
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", len(body))
        + body
    )
