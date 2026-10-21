"""The OSC side of a fake OBSBOT over real UDP (CA-3): colour temperature, exposure and
AI-tracking land in the same :class:`FakeCamera` as the VISCA side."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from cutcut.devices.cameras import osc
from cutcut.sim.fake_camera import FakeCamera


@dataclass
class FakeOsc(asyncio.DatagramProtocol):
    cam: FakeCamera
    auto_wb: bool = True
    auto_exposure: bool = True
    shutter: int | None = None
    iso: int | None = None
    log: list[tuple[str, list[osc.Arg]]] = field(default_factory=list)
    transport: asyncio.BaseTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str | int, ...]) -> None:
        address, args = osc.decode(data)
        self.log.append((address, args))
        name = address.rsplit("/", 1)[-1]
        v = args[0] if args else None
        if name == "SetAutoWhiteBalance":
            self.auto_wb = v == 1
        elif name == "SetColorTemperature" and isinstance(v, int):
            self.cam.kelvin = v
            self.cam.received.append(f"wb {v} None None")
        elif name == "SetAutoExposure":
            self.auto_exposure = v == 1
        elif name == "SetShutterSpeed" and isinstance(v, int):
            self.shutter = v
        elif name == "SetISO" and isinstance(v, int):
            self.iso = v
        elif name == "SetAiEnable":
            self.cam.tracking = v == 1
            self.cam.received.append(f"tracking {v == 1}")


async def serve(cam: FakeCamera, host: str = "127.0.0.1") -> tuple[FakeOsc, int]:
    loop = asyncio.get_running_loop()
    transport, proto = await loop.create_datagram_endpoint(
        lambda: FakeOsc(cam), local_addr=(host, 0)
    )
    return proto, transport.get_extra_info("sockname")[1]
