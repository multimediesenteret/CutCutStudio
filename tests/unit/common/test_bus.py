from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import textwrap
from collections.abc import AsyncIterator

import pytest
import zmq.asyncio

from cutcut.common.bus import (
    CommandTimeoutError,
    Publisher,
    SeqTracker,
    StaleWatcher,
    Subscriber,
    decode,
    encode,
    endpoint,
    request,
)
from cutcut.common.clock import FakeClock, SystemClock
from cutcut.common.models import BusMessage


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# --- pure helpers ------------------------------------------------------------------------


def test_seq_tracker_counts_gaps_and_restarts() -> None:
    t = SeqTracker()
    assert t.observe("audio-capture", "audio.frame", 0) == 0
    assert t.observe("audio-capture", "audio.frame", 1) == 0
    assert t.observe("audio-capture", "audio.frame", 5) == 3
    assert t.observe("audio-capture", "audio.frame", 0) == 0  # restarted
    assert (t.gaps, t.restarts) == (3, 1)
    assert t.observe("vision", "audio.frame", 7) == 0  # separate per source


def test_stale_watcher_reports_once_and_recovers() -> None:
    w = StaleWatcher(timeout_ms=1000)
    w.seen("vision.tile", 0)
    assert w.check(900) == []
    assert w.check(1001) == ["vision.tile"]
    assert w.check(5000) == []  # reported once only
    assert w.is_stale("vision.tile", 5000)
    assert w.seen("vision.tile", 5100) is True  # back
    assert not w.is_stale("vision.tile", 5200)
    assert w.is_stale("never.heard", 0)


def test_encode_decode_round_trip() -> None:
    clock = FakeClock()
    msg = BusMessage(
        topic="audio.frame",
        source="audio-capture",
        ts=clock.now(),
        mono_ms=5,
        seq=1,
        payload={"M1": {"vad": 0.9}},
    )
    assert decode(encode(msg)) == msg
    with pytest.raises(ValueError, match="2 frames"):
        decode([b"x"])


# --- sockets -----------------------------------------------------------------------------


@pytest.fixture
async def ctx() -> AsyncIterator[zmq.asyncio.Context]:
    c = zmq.asyncio.Context()
    yield c
    c.destroy(linger=0)


async def wait_until_connected(pub: Publisher, sub: Subscriber, topic: str) -> None:
    """PUB/SUB drops messages until the connection is up ("slow joiner"); probe until one lands."""
    for _ in range(100):
        await pub.publish(topic, {"probe": True})
        if await sub.recv(timeout_ms=20) is not None:
            return
    raise AssertionError("bus never connected")


async def test_publish_subscribe_with_topic_filter(ctx: zmq.asyncio.Context) -> None:
    port = free_port()
    sub = Subscriber(ctx, ["audio."], bind=endpoint(port))
    pub = Publisher(ctx, "audio-capture", SystemClock(), connect=endpoint(port))
    await wait_until_connected(pub, sub, "audio.probe")
    await pub.publish("vision.tile", {"tile": 1})  # filtered away
    sent = await pub.publish("audio.frame", {"M1": {"vad": 0.8}})
    got = await sub.recv(timeout_ms=1000)
    assert got is not None
    assert got.topic == "audio.frame"
    assert got.payload == {"M1": {"vad": 0.8}}
    assert got.seq == sent.seq
    pub.close()
    sub.close()


async def test_invalid_messages_are_skipped(ctx: zmq.asyncio.Context) -> None:
    port = free_port()
    sub = Subscriber(ctx, bind=endpoint(port))
    raw = ctx.socket(zmq.PUB)
    raw.connect(endpoint(port))
    clock = SystemClock()

    def frames(topic: str) -> list[bytes]:
        msg = BusMessage(topic=topic, source="test", ts=clock.now(), mono_ms=0, seq=0)
        return encode(msg)

    for _ in range(100):  # wait until this very socket is connected (slow joiner)
        await raw.send_multipart(frames("probe"))
        if await sub.recv(timeout_ms=20) is not None:
            break
    await raw.send_multipart([b"bad", b"{not json"])
    await raw.send_multipart(frames("good"))
    got = await sub.recv(timeout_ms=1000)
    while got is not None and got.topic == "probe":
        got = await sub.recv(timeout_ms=1000)
    assert got is not None
    assert got.topic == "good"
    assert sub.invalid == 1
    raw.close(0)


async def test_request_gets_ack_and_times_out(ctx: zmq.asyncio.Context) -> None:
    in_port, out_port = free_port(), free_port()
    # core side
    core_in = Subscriber(ctx, bind=endpoint(in_port))
    core_out = Publisher(ctx, "core", SystemClock(), bind=endpoint(out_port))
    # bridge side
    bridge_in = Subscriber(ctx, ["atem.cmd"], connect=endpoint(out_port))
    bridge_out = Publisher(ctx, "atem-bridge", SystemClock(), connect=endpoint(in_port))
    await wait_until_connected(bridge_out, core_in, "probe")
    await wait_until_connected(core_out, bridge_in, "atem.cmd")

    async def bridge() -> None:
        while True:
            cmd = await bridge_in.recv()
            if cmd is not None and cmd.payload.get("op") == "cut":
                await bridge_out.publish("atem.ack", {"id": cmd.payload["id"], "ok": True})

    task = asyncio.create_task(bridge())
    try:
        ack = await request(
            core_out,
            core_in,
            "atem.cmd",
            {"op": "cut", "shot": "BIRD"},
            ack_topic="atem.ack",
            timeout_ms=500,
        )
        assert ack.payload["ok"] is True
        with pytest.raises(CommandTimeoutError):
            await request(
                core_out,
                core_in,
                "atem.cmd",
                {"op": "ignored"},
                ack_topic="atem.ack",
                timeout_ms=50,
                retries=1,
            )
    finally:
        task.cancel()


def test_two_processes_talk_over_the_bus() -> None:
    """A separate process publishes and this process receives (processes run independently)."""
    port = free_port()
    script = textwrap.dedent(
        f"""
        import asyncio, zmq.asyncio
        from cutcut.common.bus import Publisher, endpoint
        from cutcut.common.clock import SystemClock
        async def main():
            ctx = zmq.asyncio.Context()
            pub = Publisher(ctx, "audio-capture", SystemClock(), connect=endpoint({port}))
            for i in range(200):
                await pub.publish("audio.frame", {{"i": i}})
                await asyncio.sleep(0.01)
            ctx.destroy(linger=0)
        asyncio.run(main())
        """
    )

    async def receive() -> list[int]:
        c = zmq.asyncio.Context()
        sub = Subscriber(c, ["audio."], bind=endpoint(port))
        proc = subprocess.Popen([sys.executable, "-c", script])  # noqa: S603, ASYNC220 - test helper
        got: list[int] = []
        try:
            while len(got) < 20:
                msg = await sub.recv(timeout_ms=5000)
                assert msg is not None, "no message from the other process"
                assert msg.source == "audio-capture"
                got.append(int(msg.payload["i"]))
        finally:
            proc.wait(timeout=10)
            c.destroy(linger=0)
        return got

    got = asyncio.run(receive())
    assert got == sorted(got)
