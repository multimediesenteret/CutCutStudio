"""Fan-out of live messages to the screens (spec 10.2, 12.5).

Each client has a small bounded queue. A slow client never slows the studio down: when its
queue is full, the oldest message is dropped and the client is told to fetch a full state.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
from dataclasses import dataclass, field
from typing import Any, Final

TOPICS: Final = frozenset(
    {"state", "meters", "decision", "vision", "health", "alert", "session", "touch"}
)
QUEUE_SIZE: Final = 200


@dataclass(eq=False)
class Client:
    topics: frozenset[str]
    queue: asyncio.Queue[dict[str, Any]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=QUEUE_SIZE)
    )
    dropped: int = 0
    resync: bool = False


class Hub:
    def __init__(self) -> None:
        self.clients: set[Client] = set()
        self._seq = itertools.count(1)

    def connect(self, topics: frozenset[str] = TOPICS) -> Client:
        client = Client(topics=topics & TOPICS)
        self.clients.add(client)
        return client

    def disconnect(self, client: Client) -> None:
        self.clients.discard(client)

    def publish(self, msg_type: str, data: Any) -> None:
        msg = {"type": msg_type, "seq": next(self._seq), "data": data}
        for client in list(self.clients):
            if msg_type not in client.topics:
                continue
            if client.queue.full():
                client.dropped += 1
                client.resync = True
                with contextlib.suppress(asyncio.QueueEmpty):
                    client.queue.get_nowait()
            client.queue.put_nowait(msg)
