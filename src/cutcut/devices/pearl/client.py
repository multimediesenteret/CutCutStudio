"""HTTP client for the Epiphan Pearl REST API v2.0 (spec 7.4, teknisk referanse).

Endpoints and answers follow Epiphan's OpenAPI description (``pearl_api_swagger_ui``,
``api/v2.0/openapi.yml``): every answer is ``{"status": "ok", "result": ...}`` or
``{"status": "error", "message": ...}``; Basic authentication; firmware 4.24.1 or newer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import httpx

from cutcut.common.models.session import RecordingStatus

TIMEOUT_S: Final = 2.0

_STATES = {s.value: s for s in RecordingStatus}


class PearlError(Exception):
    """Pearl did not answer, refused the login, or answered with an error."""


@dataclass(frozen=True)
class RecorderInfo:
    state: RecordingStatus
    duration_s: int = 0
    description: str | None = None  # Pearl's error text when state is error


@dataclass(frozen=True)
class StorageInfo:
    id: str
    state: str
    total_bytes: int
    free_bytes: int

    @property
    def free_share(self) -> float:
        return self.free_bytes / self.total_bytes if self.total_bytes else 0.0


class PearlHttp:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        verify_tls: bool = False,
        timeout_s: float = TIMEOUT_S,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/api/v2.0",
            auth=(username, password),
            verify=verify_tls,
            timeout=timeout_s,
            trust_env=False,  # studio equipment is on the local network, never via a proxy
        )

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str) -> Any:
        try:
            res = self._http.request(method, path)
        except httpx.HTTPError as exc:
            raise PearlError(f"Pearl svarer ikke ({type(exc).__name__})") from exc
        if res.status_code == 401:
            raise PearlError("Pearl avviste innloggingen (sjekk brukernavn og passord)")
        try:
            body = res.json()
        except ValueError as exc:
            raise PearlError(f"Pearl svarte {res.status_code} uten JSON på {path}") from exc
        if res.status_code >= 400 or body.get("status") != "ok":
            raise PearlError(str(body.get("message") or f"Pearl svarte {res.status_code}"))
        return body.get("result")

    def recorder_status(self, rid: str) -> RecorderInfo:
        result = self._call("GET", f"/recorders/{rid}/status") or {}
        state = _STATES.get(str(result.get("state")), RecordingStatus.ERROR)
        return RecorderInfo(
            state=state,
            duration_s=int(result.get("duration") or 0),
            description=result.get("description"),
        )

    def start(self, rid: str) -> None:
        self._call("POST", f"/recorders/{rid}/control/start")

    def stop(self, rid: str) -> None:
        self._call("POST", f"/recorders/{rid}/control/stop")

    def storages(self) -> list[StorageInfo]:
        out = []
        for item in self._call("GET", "/system/storages") or []:
            sid = str(item.get("id"))
            if sid == "maintenance":
                continue
            try:
                st = self._call("GET", f"/system/storages/{sid}/status") or {}
            except PearlError:
                continue  # e.g. no external drive plugged in
            out.append(
                StorageInfo(
                    id=sid,
                    state=str(st.get("state", "")),
                    total_bytes=int(st.get("total") or 0),
                    free_bytes=int(st.get("free") or 0),
                )
            )
        return out

    def firmware(self) -> str:
        return str(self._call("GET", "/system/firmware/version"))
