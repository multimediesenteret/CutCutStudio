"""A fake Bitfocus Companion over real HTTP (SIM-3), for integration tests and ``cutcut sim``.

It speaks the same endpoints as Companion (``/api/location/.../press``, custom variables,
``/api/connections``) and records what it was asked to do. It can be slowed down or made to
fail, so the circuit breaker and the S5 reserve cut can be tested end to end.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse


@dataclass
class FakeCompanionState:
    presses: list[tuple[int, int, int]] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    connections: list[dict[str, object]] = field(
        default_factory=lambda: [
            {
                "id": "atem1",
                "label": "atem",
                "moduleId": "bmd-atem",
                "enabled": True,
                "sortOrder": 0,
                "status": {"category": "good", "level": "ok"},
            }
        ]
    )
    delay_s: float = 0.0
    fail: bool = False  # answer 500 to everything
    lock: threading.Lock = field(default_factory=threading.Lock)


def _handler(state: FakeCompanionState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:  # quiet
            return

        def _reply(self, code: int, body: str = "", ctype: str = "text/plain") -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _gate(self) -> bool:
            if state.delay_s:
                time.sleep(state.delay_s)
            if state.fail:
                self._reply(500, "fail")
                return False
            return True

        def do_POST(self) -> None:
            if not self._gate():
                return
            url = urlparse(self.path)
            parts = url.path.strip("/").split("/")
            if len(parts) == 6 and parts[:2] == ["api", "location"] and parts[5] == "press":
                with state.lock:
                    state.presses.append((int(parts[2]), int(parts[3]), int(parts[4])))
                self._reply(200, "ok")
                return
            if len(parts) == 4 and parts[:2] == ["api", "custom-variable"] and parts[3] == "value":
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode("utf-8") if length else ""
                value = parse_qs(url.query).get("value", [body])[0]
                with state.lock:
                    state.variables[unquote(parts[2])] = value
                self._reply(200, "ok")
                return
            self._reply(404, "not found")

        def do_GET(self) -> None:
            if not self._gate():
                return
            parts = urlparse(self.path).path.strip("/").split("/")
            if parts == ["api", "connections"]:
                self._reply(200, json.dumps(state.connections), "application/json")
                return
            if len(parts) == 4 and parts[:2] == ["api", "custom-variable"] and parts[3] == "value":
                name = unquote(parts[2])
                with state.lock:
                    value = state.variables.get(name)
                if value is None:
                    self._reply(404, "not found")
                else:
                    self._reply(200, value)
                return
            self._reply(404, "not found")

    return Handler


@contextmanager
def fake_companion(
    state: FakeCompanionState | None = None,
) -> Iterator[tuple[str, FakeCompanionState]]:
    """Run a fake Companion on a free local port; yields ``(base_url, state)``."""
    state = state or FakeCompanionState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", state
    finally:
        server.shutdown()
        server.server_close()
