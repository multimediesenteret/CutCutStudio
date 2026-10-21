"""A fake OBSBOT over real UDP that speaks VISCA over IP (CA-2): presets, position, zoom and
modes, with the same ACK/completion/error replies as a camera. Used by the tests and by
``cutcut fake-camera`` later; state lives in a :class:`FakeCamera` so tests can read it."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from cutcut.devices.cameras import visca
from cutcut.devices.cameras.base import PTZPosition
from cutcut.devices.cameras.obsbot import Calibration
from cutcut.sim.fake_camera import FakeCamera


@dataclass
class FakeVisca(asyncio.DatagramProtocol):
    cam: FakeCamera
    cal: Calibration = field(default_factory=Calibration)
    wb_mode: int = 0x05
    ae_mode: int = 0x03
    silent: bool = False  # drop everything (a camera that is off the network)
    ack_only: bool = False
    _transport: asyncio.DatagramTransport | None = None
    _speed: int = 0x0C
    log: list[str] = field(default_factory=list)

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        if isinstance(transport, asyncio.DatagramTransport):
            self._transport = transport

    def _send(self, addr: tuple[str | int, ...], ptype: int, seq: int, payload: bytes) -> None:
        if self._transport is not None:
            self._transport.sendto(visca.frame(ptype, seq, payload), addr)

    def datagram_received(self, data: bytes, addr: tuple[str | int, ...]) -> None:
        if self.silent:
            return
        ptype, seq, msg = visca.unframe(data)
        self.log.append(msg.hex(" "))
        if ptype == visca.CONTROL:
            self._send(addr, visca.CONTROL_REPLY, seq, b"\x01")
        elif ptype == visca.INQUIRY:
            self._send(addr, visca.REPLY, seq, self._inquiry(msg))
        elif ptype == visca.COMMAND:
            ok = self._command(msg)
            if not ok:
                self._send(addr, visca.REPLY, seq, b"\x90\x60\x02\xff")  # syntax error
                return
            self._send(addr, visca.REPLY, seq, b"\x90\x41\xff")
            if not self.ack_only:
                self._send(addr, visca.REPLY, seq, b"\x90\x51\xff")

    def _inquiry(self, msg: bytes) -> bytes:
        c = self.cam
        pan, tilt, zoom = self.cal.to_units(PTZPosition(c.pan, c.tilt, c.zoom))
        if msg == visca.INQ_PAN_TILT:
            return b"\x90\x50" + visca.nibbles(pan, 4) + visca.nibbles(tilt, 4) + b"\xff"
        if msg == visca.INQ_ZOOM:
            return b"\x90\x50" + visca.nibbles(zoom, 4) + b"\xff"
        if msg == visca.INQ_POWER:
            return b"\x90\x50\x02\xff"
        if msg == visca.INQ_WB_MODE:
            return bytes([0x90, 0x50, self.wb_mode, 0xFF])
        if msg == visca.INQ_AE_MODE:
            return bytes([0x90, 0x50, self.ae_mode, 0xFF])
        return b"\x90\x60\x02\xff"

    def _command(self, msg: bytes) -> bool:
        c = self.cam
        head = msg[:4]
        if head == b"\x81\x01\x04\x3f" and len(msg) == 7:
            n = msg[5]
            if msg[4] == 0x02:
                c.received.append(f"recall {n} {self._speed / 0x19:.2g}")
                if n in c.presets:
                    p = c.presets[n]
                    c.pan, c.tilt, c.zoom = p.pan, p.tilt, p.zoom
                return True
            if msg[4] == 0x01:
                c.received.append(f"store {n}")
                c.presets[n] = PTZPosition(c.pan, c.tilt, c.zoom)
                return True
        if msg[:5] == b"\x81\x01\x7e\x04\x1c" and len(msg) == 8:
            self._speed = (msg[5] << 4) | msg[6]
            return True
        if head == b"\x81\x01\x06\x02" and len(msg) == 15:
            pan = visca.from_nibbles(msg[6:10], True)
            tilt = visca.from_nibbles(msg[10:14], True)
            p = self.cal.from_units(pan, tilt, 0)
            c.pan, c.tilt = p.pan, p.tilt
            c.received.append(f"move {p.pan:g} {p.tilt:g}")
            return True
        if head == b"\x81\x01\x04\x47" and len(msg) == 9:
            z = self.cal.from_units(0, 0, visca.from_nibbles(msg[4:8], False)).zoom
            c.zoom = z
            c.received.append(f"zoom {z:g}")
            return True
        if head == b"\x81\x01\x04\x35" and len(msg) == 6:
            self.wb_mode = msg[4]
            return True
        if head == b"\x81\x01\x04\x39" and len(msg) == 6:
            self.ae_mode = msg[4]
            return True
        return False


async def serve(cam: FakeCamera, host: str = "127.0.0.1", port: int = 0) -> tuple[FakeVisca, int]:
    """Start a fake camera; returns it and the port it listens on."""
    loop = asyncio.get_running_loop()
    transport, proto = await loop.create_datagram_endpoint(
        lambda: FakeVisca(cam), local_addr=(host, port)
    )
    return proto, transport.get_extra_info("sockname")[1]
