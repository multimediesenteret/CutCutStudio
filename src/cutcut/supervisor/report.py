"""Sends the supervisor's status to core over the bus (``supervisor.status``, every 2 s).

A plain blocking ZeroMQ PUB socket: the supervisor has no event loop and must never wait for
core. When core is down the messages are simply dropped; ZeroMQ reconnects by itself.
"""

from __future__ import annotations

import itertools
import time
from datetime import UTC, datetime
from typing import Final

import zmq

from cutcut.common.bus.zmq_bus import EVENTS_IN_PORT, encode, endpoint
from cutcut.common.models.bus import BusMessage

TOPIC: Final = "supervisor.status"


class StatusReporter:
    def __init__(self, port: int = EVENTS_IN_PORT) -> None:
        self._ctx = zmq.Context()
        self._sock = self._ctx.socket(zmq.PUB)
        self._sock.setsockopt(zmq.LINGER, 0)
        self._sock.setsockopt(zmq.SNDHWM, 10)
        self._sock.connect(endpoint(port))
        self._seq = itertools.count()
        self._t0 = time.monotonic()

    def __call__(self, processes: list[dict[str, object]]) -> None:
        msg = BusMessage(
            topic=TOPIC,
            source="supervisor",
            ts=datetime.now(UTC),
            mono_ms=int((time.monotonic() - self._t0) * 1000),
            seq=next(self._seq),
            payload={"processes": processes},
        )
        self._sock.send_multipart(encode(msg), flags=zmq.NOBLOCK)

    def close(self) -> None:
        self._sock.close()
        self._ctx.term()
