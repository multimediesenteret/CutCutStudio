"""A fake Epiphan Pearl over real HTTP (SIM-3), speaking REST API v2.0 like the real one.

Recorders start after a delay (``starting`` → ``started``), can be made to stop by themselves
(disk full, lost signal), the login can be wrong, and the whole box can stop answering. Used
by the integration tests and the machine-test script's dry run.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


@dataclass
class FakePearlState:
    username: str = "cutcut"
    password: str = "test-only"  # noqa: S105 - fake device, never a real password
    firmware: str = "4.24.1"
    recorders: dict[str, str] = field(default_factory=lambda: {"1": "stopped"})
    started_at: dict[str, float] = field(default_factory=dict)
    start_delay_s: float = 0.3
    total_bytes: int = 1_000_000_000_000
    free_bytes: int = 700_000_000_000
    fail: bool = False  # answer 503 to everything
    commands: list[tuple[str, str]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def state_of(self, rid: str) -> str:
        with self.lock:
            state = self.recorders.get(rid, "error")
            if (
                state == "starting"
                and time.monotonic() - self.started_at[rid] >= self.start_delay_s
            ):
                self.recorders[rid] = state = "started"
                self.started_at[rid] = time.monotonic()
            return state

    def stop_by_itself(self, rid: str = "1", error: bool = False) -> None:
        with self.lock:
            self.recorders[rid] = "error" if error else "stopped"


def _handler(state: FakePearlState) -> type[BaseHTTPRequestHandler]:
    expected = "Basic " + base64.b64encode(f"{state.username}:{state.password}".encode()).decode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            return

        def _json(self, code: int, body: object) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _ok(self, result: object = None) -> None:
            self._json(
                200, {"status": "ok"} if result is None else {"status": "ok", "result": result}
            )

        def _gate(self) -> list[str] | None:
            if state.fail:
                self._json(503, {"status": "error", "message": "unavailable"})
                return None
            if self.headers.get("Authorization") != expected:
                self._json(401, {"status": "error", "message": "Unauthorized"})
                return None
            path = urlparse(self.path).path
            if not path.startswith("/api/v2.0/"):
                self._json(404, {"status": "error", "message": "not found"})
                return None
            return path[len("/api/v2.0/") :].strip("/").split("/")

        def do_GET(self) -> None:
            parts = self._gate()
            if parts is None:
                return
            if len(parts) == 3 and parts[0] == "recorders" and parts[2] == "status":
                rid = parts[1]
                if rid not in state.recorders:
                    self._json(404, {"status": "error", "message": "no such recorder"})
                    return
                st = state.state_of(rid)
                result: dict[str, object] = {"state": st}
                if st == "started":
                    result["duration"] = int(time.monotonic() - state.started_at[rid])
                if st == "error":
                    result["description"] = "No space left on device"
                self._ok(result)
            elif parts == ["system", "storages"]:
                self._ok([{"id": "main"}, {"id": "external"}, {"id": "maintenance"}])
            elif parts == ["system", "storages", "main", "status"]:
                self._ok({"state": "ready", "total": state.total_bytes, "free": state.free_bytes})
            elif parts[:2] == ["system", "storages"]:
                self._json(404, {"status": "error", "message": "not mounted"})
            elif parts == ["system", "firmware", "version"]:
                self._ok(state.firmware)
            else:
                self._json(404, {"status": "error", "message": "not found"})

        def do_POST(self) -> None:
            parts = self._gate()
            if parts is None:
                return
            if len(parts) == 4 and parts[0] == "recorders" and parts[2] == "control":
                rid, command = parts[1], parts[3]
                with state.lock:
                    state.commands.append((rid, command))
                    if command == "start" and state.recorders.get(rid) != "started":
                        state.recorders[rid] = "starting"
                        state.started_at[rid] = time.monotonic()
                    elif command == "stop":
                        state.recorders[rid] = "stopped"
                self._ok()
            else:
                self._json(404, {"status": "error", "message": "not found"})

    return Handler


@contextmanager
def fake_pearl(state: FakePearlState | None = None) -> Iterator[tuple[str, FakePearlState]]:
    """Run a fake Pearl on a free local port (plain HTTP); yields ``(base_url, state)``."""
    state = state or FakePearlState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", state
    finally:
        server.shutdown()
        server.server_close()
