"""Defence in depth for I8: card numbers must never reach logs, database or API.

The card reader code never passes the UID on. ``redact`` is a last line of defence applied
to every log line, in case a UID ends up in a message or an exception by mistake.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[fjernet]"

# MIFARE UIDs are 4, 7 or 10 bytes: 8, 14 or 20 hex digits,
# separated by ":" or " " or not at all, or the same number in decimal (10 digits).
# "-" is not a separator here, so dates like 2026-10-21 are never touched.
_HEX_UID = re.compile(
    r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[: ]?){3}[0-9A-Fa-f]{2}"
    r"(?:(?:[: ]?[0-9A-Fa-f]{2}){3}(?:(?:[: ]?[0-9A-Fa-f]{2}){3})?)?(?![0-9A-Fa-f])"
)
_DEC_UID = re.compile(r"(?<!\d)\d{10}(?!\d)")
_SENSITIVE_KEYS = re.compile(r"(uid|card|kort|mifare|serial)", re.IGNORECASE)


def _looks_like_hex_uid(match: re.Match[str]) -> bool:
    digits = re.sub(r"[: ]", "", match.group(0))
    # Words made only of the letters a–f (e.g. "deadbeef") are left alone; anything with a
    # digit and the right length is treated as a possible card number. Privacy wins.
    return any(c.isdigit() for c in digits) and len(digits) in (8, 14, 20)


def redact_text(text: str) -> str:
    text = _HEX_UID.sub(lambda m: REDACTED if _looks_like_hex_uid(m) else m.group(0), text)
    return _DEC_UID.sub(REDACTED, text)


def redact(value: Any) -> Any:
    """Return ``value`` with anything that looks like a card number removed."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {
            k: (REDACTED if _SENSITIVE_KEYS.search(str(k)) else redact(v)) for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return type(value)(redact(v) for v in value)
    return value
