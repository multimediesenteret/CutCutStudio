"""VISCA over IP (UDP 52381): the byte tables from spec 7.3 and a small async client (CA-2).

Every message is wrapped in the 8-byte VISCA-over-IP header (payload type, length, sequence
number). The camera answers a command with ACK (``90 4y FF``) and then completion
(``90 5y FF``), an inquiry with ``90 50 … FF``, and errors with ``90 6y ee FF``.

The encoders here are pure functions and tested byte for byte against the tables; the client
sends one message at a time (``GuardedCamera`` already queues) and waits at most ``timeout_s``.
"""

from __future__ import annotations

import asyncio
import contextlib
import struct
from dataclasses import dataclass
from typing import Final

from cutcut.devices.cameras.base import CameraError

PORT: Final = 52381

# payload types in the VISCA-over-IP header
COMMAND: Final = 0x0100
INQUIRY: Final = 0x0110
REPLY: Final = 0x0111
CONTROL: Final = 0x0200
CONTROL_REPLY: Final = 0x0201

ERRORS: Final = {
    0x01: "feil lengde på meldingen",
    0x02: "syntaksfeil",
    0x03: "kommandobufferet er fullt",
    0x04: "avbrutt",
    0x05: "ingen kommando å avbryte",
    0x41: "kan ikke utføres nå",
}


class ViscaError(CameraError):
    pass


# --- encoding ------------------------------------------------------------------------------


def nibbles(value: int, n: int) -> bytes:
    """``value`` as ``n`` bytes of one nibble each, most significant first (``0p 0p 0p 0p``).
    Negative values are two's complement over ``4 * n`` bits."""
    value &= (1 << (4 * n)) - 1
    return bytes((value >> (4 * (n - 1 - i))) & 0x0F for i in range(n))


def from_nibbles(data: bytes, signed: bool) -> int:
    v = 0
    for b in data:
        v = (v << 4) | (b & 0x0F)
    bits = 4 * len(data)
    if signed and v >= 1 << (bits - 1):
        v -= 1 << bits
    return v


def _check(name: str, v: int, lo: int, hi: int) -> int:
    if not lo <= v <= hi:
        raise ValueError(f"{name} {v} er utenfor {lo}–{hi}")
    return v


def recall_preset(n: int) -> bytes:
    return bytes([0x81, 0x01, 0x04, 0x3F, 0x02, _check("preset", n, 0, 0xFF), 0xFF])


def store_preset(n: int) -> bytes:
    return bytes([0x81, 0x01, 0x04, 0x3F, 0x01, _check("preset", n, 0, 0xFF), 0xFF])


def preset_speed(p: int) -> bytes:
    """``81 01 7E 04 1C 0p 0p FF``, 1–0x19 (spec 7.3: 01–19)."""
    p = _check("preset-fart", p, 1, 0x19)
    return bytes([0x81, 0x01, 0x7E, 0x04, 0x1C, p >> 4, p & 0x0F, 0xFF])


def pan_tilt_absolute(pan: int, tilt: int, pan_speed: int, tilt_speed: int) -> bytes:
    """``81 01 06 02 vv ww 0p 0p 0p 0p 0t 0t 0t 0t FF``. Positions in camera units, signed."""
    return (
        bytes(
            [
                0x81,
                0x01,
                0x06,
                0x02,
                _check("pan-fart", pan_speed, 1, 0x18),
                _check("tilt-fart", tilt_speed, 1, 0x14),
            ]
        )
        + nibbles(pan, 4)
        + nibbles(tilt, 4)
        + b"\xff"
    )


def pan_tilt_drive(pan: int, tilt: int, pan_speed: int, tilt_speed: int) -> bytes:
    """``81 01 06 01 vv ww xx yy FF``: start moving (``xx``: 01 left, 02 right, 03 stop;
    ``yy``: 01 up, 02 down, 03 stop). ``pan``/``tilt`` are −1, 0 or 1."""
    xx = {-1: 0x01, 1: 0x02, 0: 0x03}[pan]
    yy = {1: 0x01, -1: 0x02, 0: 0x03}[tilt]
    return bytes(
        [
            0x81,
            0x01,
            0x06,
            0x01,
            _check("pan-fart", pan_speed, 1, 0x18),
            _check("tilt-fart", tilt_speed, 1, 0x14),
            xx,
            yy,
            0xFF,
        ]
    )


def zoom_direct(z: int) -> bytes:
    """``81 01 04 47 0z 0z 0z 0z FF``, 0 (wide) to 0x4000 (tele)."""
    return bytes([0x81, 0x01, 0x04, 0x47]) + nibbles(_check("zoom", z, 0, 0x4000), 4) + b"\xff"


def zoom_drive(direction: int, speed: int) -> bytes:
    """``81 01 04 07 2p FF`` (tele) / ``3p`` (wide) / ``00`` (stop); ``p`` 0 (slow) to 7."""
    speed = _check("zoom-fart", speed, 0, 7)
    code = {1: 0x20 | speed, -1: 0x30 | speed, 0: 0x00}[direction]
    return bytes([0x81, 0x01, 0x04, 0x07, code, 0xFF])


def white_balance_mode(p: int) -> bytes:
    """``81 01 04 35 0p FF``; 5 = manual (spec 7.3)."""
    return bytes([0x81, 0x01, 0x04, 0x35, _check("hvitbalanse", p, 0, 0x0F), 0xFF])


def exposure_mode(p: int) -> bytes:
    """``81 01 04 39 0p FF``; 3 = manual (spec 7.3)."""
    return bytes([0x81, 0x01, 0x04, 0x39, _check("eksponering", p, 0, 0x0F), 0xFF])


INQ_PAN_TILT: Final = bytes([0x81, 0x09, 0x06, 0x12, 0xFF])
INQ_ZOOM: Final = bytes([0x81, 0x09, 0x04, 0x47, 0xFF])
INQ_WB_MODE: Final = bytes([0x81, 0x09, 0x04, 0x35, 0xFF])
INQ_AE_MODE: Final = bytes([0x81, 0x09, 0x04, 0x39, 0xFF])
INQ_R_GAIN: Final = bytes([0x81, 0x09, 0x04, 0x43, 0xFF])
INQ_B_GAIN: Final = bytes([0x81, 0x09, 0x04, 0x44, 0xFF])
INQ_POWER: Final = bytes([0x81, 0x09, 0x04, 0x00, 0xFF])


def parse_pan_tilt(reply: bytes) -> tuple[int, int]:
    """``90 50 0p 0p 0p 0p 0t 0t 0t 0t FF`` → (pan, tilt), signed camera units."""
    if len(reply) != 11 or reply[:2] != b"\x90\x50":
        raise ViscaError(f"uventet svar på posisjon: {reply.hex(' ')}")
    return from_nibbles(reply[2:6], True), from_nibbles(reply[6:10], True)


def parse_zoom(reply: bytes) -> int:
    """``90 50 0p 0q 0r 0s FF`` → zoom 0–0x4000."""
    if len(reply) != 7 or reply[:2] != b"\x90\x50":
        raise ViscaError(f"uventet svar på zoom: {reply.hex(' ')}")
    return from_nibbles(reply[2:6], False)


def parse_byte(reply: bytes) -> int:
    """``90 50 0p FF`` → p (modes, power)."""
    if len(reply) != 4 or reply[:2] != b"\x90\x50":
        raise ViscaError(f"uventet svar: {reply.hex(' ')}")
    return reply[2]


def parse_gain(reply: bytes) -> int:
    """``90 50 00 00 0p 0q FF`` → 0–0xFF."""
    if len(reply) != 7 or reply[:2] != b"\x90\x50":
        raise ViscaError(f"uventet svar på gain: {reply.hex(' ')}")
    return from_nibbles(reply[2:6], False)


# --- framing -------------------------------------------------------------------------------


def frame(payload_type: int, seq: int, payload: bytes) -> bytes:
    return struct.pack(">HHI", payload_type, len(payload), seq) + payload


def unframe(data: bytes) -> tuple[int, int, bytes]:
    if len(data) < 8:
        raise ViscaError("for kort VISCA-pakke")
    ptype, length, seq = struct.unpack(">HHI", data[:8])
    return ptype, seq, data[8 : 8 + length]


def error_of(reply: bytes) -> str | None:
    """The error text if ``reply`` is ``90 6y ee FF``, else ``None``."""
    if len(reply) >= 4 and reply[0] == 0x90 and reply[1] & 0xF0 == 0x60:
        return ERRORS.get(reply[2], f"feilkode {reply[2]:02x}")
    return None


# --- client --------------------------------------------------------------------------------


class _Proto(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.inbox: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data: bytes, addr: tuple[str | int, ...]) -> None:
        self.inbox.put_nowait(data)


@dataclass
class ViscaClient:
    """One camera. Not safe for parallel calls: ``GuardedCamera`` sends one at a time."""

    host: str
    port: int = PORT
    timeout_s: float = 0.2
    _transport: asyncio.DatagramTransport | None = None
    _proto: _Proto | None = None
    _seq: int = 0

    async def open(self) -> None:
        if self._transport is not None:
            return
        loop = asyncio.get_running_loop()
        transport, proto = await loop.create_datagram_endpoint(
            _Proto, remote_addr=(self.host, self.port)
        )
        self._transport, self._proto = transport, proto
        await self._send(CONTROL, b"\x01")  # reset the camera's sequence number
        with contextlib.suppress(TimeoutError):
            await self._reply(CONTROL_REPLY)

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
        self._transport = self._proto = None

    async def _send(self, ptype: int, payload: bytes) -> int:
        await self.open()
        if self._transport is None:
            raise ViscaError("ikke koblet til")
        self._seq = (self._seq + 1) & 0xFFFFFFFF
        self._transport.sendto(frame(ptype, self._seq, payload))
        return self._seq

    async def _reply(self, want: int, seq: int | None = None) -> bytes:
        if self._proto is None:
            raise ViscaError("ikke koblet til")
        async with asyncio.timeout(self.timeout_s):
            while True:
                ptype, s, payload = unframe(await self._proto.inbox.get())
                if ptype == want and (seq is None or s == seq):
                    return payload

    async def command(self, payload: bytes) -> None:
        """Send and wait for ACK (``90 4y FF``). Completion arrives later; movement keeps going
        on the camera, so CutCut does not wait for it."""
        self._drain()
        seq = await self._send(COMMAND, payload)
        while True:
            reply = await self._reply(REPLY, seq)
            if (err := error_of(reply)) is not None:
                raise ViscaError(err)
            if len(reply) >= 3 and reply[1] & 0xF0 in (0x40, 0x50):
                return

    async def inquiry(self, payload: bytes) -> bytes:
        self._drain()
        seq = await self._send(INQUIRY, payload)
        while True:
            reply = await self._reply(REPLY, seq)
            if (err := error_of(reply)) is not None:
                raise ViscaError(err)
            if reply[:2] == b"\x90\x50":
                return reply

    def _drain(self) -> None:
        """Late completions from earlier commands are not answers to this one."""
        if self._proto is not None:
            while not self._proto.inbox.empty():
                self._proto.inbox.get_nowait()
