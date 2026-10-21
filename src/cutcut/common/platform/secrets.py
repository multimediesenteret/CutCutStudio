"""Secrets (NTNU API key, Pearl and camera passwords) – never in git or logs (spec 12.4).

On the studio PC they live in Windows Credential Manager via ``keyring``.
"""

from __future__ import annotations

from typing import Final, Protocol

SERVICE: Final = "CutCut Studio"

KNOWN_SECRETS: Final = (
    "ntnu_api_key",
    "pearl_password",
    "canon_password",
    "operator_pin",
    "admin_pin",
)


class SecretMissingError(Exception):
    """A secret is not stored. The message names it but never contains a value."""


class SecretStore(Protocol):
    def get(self, name: str) -> str: ...
    def set(self, name: str, value: str) -> None: ...
    def has(self, name: str) -> bool: ...


def _check_name(name: str) -> None:
    if name not in KNOWN_SECRETS:
        raise KeyError(f"unknown secret {name!r}; add it to KNOWN_SECRETS")


class KeyringSecretStore:
    def get(self, name: str) -> str:
        import keyring  # imported lazily: the backend probes the OS on import

        _check_name(name)
        value = keyring.get_password(SERVICE, name)
        if value is None:
            raise SecretMissingError(f"hemmeligheten {name!r} er ikke lagret på denne PC-en")
        return value

    def set(self, name: str, value: str) -> None:
        import keyring

        _check_name(name)
        keyring.set_password(SERVICE, name, value)

    def has(self, name: str) -> bool:
        try:
            self.get(name)
        except SecretMissingError:
            return False
        return True


class FakeSecretStore:
    """In-memory store for tests and the simulator. Holds only fake values."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = dict(values or {})

    def get(self, name: str) -> str:
        _check_name(name)
        if name not in self._values:
            raise SecretMissingError(f"hemmeligheten {name!r} er ikke lagret (falsk lager)")
        return self._values[name]

    def set(self, name: str, value: str) -> None:
        _check_name(name)
        self._values[name] = value

    def has(self, name: str) -> bool:
        return name in self._values
