"""ZeroMQ transport for the internal bus.

Topology (one hub, no broker process to keep alive):

* ``core`` binds a SUB socket on ``EVENTS_IN`` – every other process connects a PUB to it
  (audio frames, vision tiles, ATEM state, heartbeats, command acks).
* ``core`` binds a PUB socket on ``EVENTS_OUT`` – every other process connects a SUB to it
  (commands to the ATEM bridge, config changes).

Only localhost TCP is used (works the same on Windows and Linux). ZeroMQ reconnects by itself,
so any process can restart in any order. Frames are ``[topic, json]``.

Commands that must not be lost use ``request()``: publish with an ``id``, wait for an ack
event with the same ``id``, retry on timeout. Device commands are idempotent (ADR-0005), so
a retry is always safe.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import uuid
from collections.abc import Callable, Sequence
from typing import Any, Final

import zmq
import zmq.asyncio

from cutcut.common.clock import Clock
from cutcut.common.models.bus import BusMessage

log = logging.getLogger(__name__)

HOST: Final = "127.0.0.1"
EVENTS_IN_PORT: Final = 5560
EVENTS_OUT_PORT: Final = 5561


def endpoint(port: int) -> str:
    return f"tcp://{HOST}:{port}"


def encode(msg: BusMessage) -> list[bytes]:
    return [msg.topic.encode(), msg.model_dump_json().encode()]


def decode(frames: Sequence[bytes]) -> BusMessage:
    if len(frames) != 2:
        raise ValueError(f"expected 2 frames, got {len(frames)}")
    return BusMessage.model_validate_json(frames[1])


class Publisher:
    """Publishes messages with a per-topic sequence number."""

    def __init__(
        self,
        ctx: zmq.asyncio.Context,
        source: str,
        clock: Clock,
        *,
        bind: str | None = None,
        connect: str | None = None,
    ) -> None:
        if (bind is None) == (connect is None):
            raise ValueError("give exactly one of bind or connect")
        self.source = source
        self.clock = clock
        self.sock = ctx.socket(zmq.PUB)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.setsockopt(zmq.SNDHWM, 10_000)  # drop rather than block when a reader stalls
        if bind is not None:
            self.sock.bind(bind)
        elif connect is not None:
            self.sock.connect(connect)
        self._seq: dict[str, itertools.count[int]] = {}

    async def publish(self, topic: str, payload: dict[str, Any]) -> BusMessage:
        counter = self._seq.setdefault(topic, itertools.count())
        msg = BusMessage(
            topic=topic,
            source=self.source,
            ts=self.clock.now(),
            mono_ms=self.clock.mono_ms(),
            seq=next(counter),
            payload=payload,
        )
        await self.sock.send_multipart(encode(msg))
        return msg

    def close(self) -> None:
        self.sock.close(0)


class Subscriber:
    def __init__(
        self,
        ctx: zmq.asyncio.Context,
        topics: Sequence[str] = ("",),
        *,
        bind: str | None = None,
        connect: str | None = None,
    ) -> None:
        if (bind is None) == (connect is None):
            raise ValueError("give exactly one of bind or connect")
        self.sock = ctx.socket(zmq.SUB)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.setsockopt(zmq.RCVHWM, 10_000)
        for t in topics:
            self.sock.setsockopt(zmq.SUBSCRIBE, t.encode())
        if bind is not None:
            self.sock.bind(bind)
        elif connect is not None:
            self.sock.connect(connect)
        self.invalid = 0

    async def recv(self, timeout_ms: int | None = None) -> BusMessage | None:
        """Next valid message, or None on timeout. Invalid messages are counted and skipped."""
        while True:
            if timeout_ms is not None and not await self.sock.poll(timeout_ms):
                return None
            frames = await self.sock.recv_multipart()
            try:
                return decode(frames)
            except (ValueError, json.JSONDecodeError) as exc:
                self.invalid += 1
                log.warning("dropped invalid bus message: %s", exc)

    def close(self) -> None:
        self.sock.close(0)


class CommandTimeoutError(Exception):
    """No acknowledgement arrived for a bus command."""


async def request(
    pub: Publisher,
    sub: Subscriber,
    topic: str,
    payload: dict[str, Any],
    *,
    ack_topic: str,
    timeout_ms: int = 300,
    retries: int = 2,
    on_other: Callable[[BusMessage], None] | None = None,
) -> BusMessage:
    """Publish a command and wait for ``{ack_topic}`` with the same ``id``.

    Messages that are not the ack are passed to ``on_other`` so nothing is lost while waiting.
    """
    cmd_id = payload.get("id") or uuid.uuid4().hex[:12]
    payload = {**payload, "id": cmd_id}
    for _attempt in range(retries + 1):
        await pub.publish(topic, payload)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_ms / 1000
        while (remaining := deadline - loop.time()) > 0:
            msg = await sub.recv(timeout_ms=max(1, int(remaining * 1000)))
            if msg is None:
                break
            if msg.topic == ack_topic and msg.payload.get("id") == cmd_id:
                return msg
            if on_other is not None:
                on_other(msg)
    raise CommandTimeoutError(f"{topic} {cmd_id}: no {ack_topic} after {retries + 1} attempts")
