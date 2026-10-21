"""Open Sound Control 1.0 over UDP, the part OBSBOT uses (CA-3): messages with int32, float32
and string arguments. Small enough to keep here instead of a dependency, and tested byte for
byte against the OSC 1.0 rules (4-byte padding, type tag string, big-endian numbers)."""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass, field

Arg = int | float | str


def _pad(b: bytes) -> bytes:
    """Null-terminate and pad to a multiple of 4 bytes."""
    b += b"\x00"
    return b + b"\x00" * (-len(b) % 4)


def encode(address: str, *args: Arg) -> bytes:
    if not address.startswith("/"):
        raise ValueError(f"OSC-adresse må starte med /: {address!r}")
    tags = ","
    body = b""
    for a in args:
        if isinstance(a, bool):
            raise TypeError("OSC-meldinger her bruker 0/1, ikke True/False")
        if isinstance(a, int):
            tags += "i"
            body += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"
            body += struct.pack(">f", a)
        else:
            tags += "s"
            body += _pad(a.encode())
    return _pad(address.encode()) + _pad(tags.encode()) + body


def _string(data: bytes, at: int) -> tuple[str, int]:
    end = data.index(b"\x00", at)
    return data[at:end].decode(), end + 1 + (-(end + 1) % 4)


def decode(data: bytes) -> tuple[str, list[Arg]]:
    address, at = _string(data, 0)
    tags, at = _string(data, at)
    if not tags.startswith(","):
        raise ValueError("mangler typestreng")
    args: list[Arg] = []
    for t in tags[1:]:
        if t == "i":
            args.append(struct.unpack(">i", data[at : at + 4])[0])
            at += 4
        elif t == "f":
            args.append(struct.unpack(">f", data[at : at + 4])[0])
            at += 4
        elif t == "s":
            s, at = _string(data, at)
            args.append(s)
        else:
            raise ValueError(f"ukjent OSC-type {t!r}")
    return address, args


@dataclass
class OscSender:
    """Fire-and-forget: OBSBOT does not acknowledge settings, so position and modes are read
    back over VISCA instead."""

    host: str
    port: int = 57110
    _transport: asyncio.DatagramTransport | None = field(default=None, init=False)

    async def send(self, address: str, *args: Arg) -> None:
        if self._transport is None:
            loop = asyncio.get_running_loop()
            self._transport, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol, remote_addr=(self.host, self.port)
            )
        self._transport.sendto(encode(address, *args))

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
        self._transport = None
