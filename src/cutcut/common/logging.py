"""Structured logging as JSON lines (spec 12.1; ADR-0006).

Every line has time, level, process, module, message, and – when known – a rule or check
ID and a ``correlation_id`` that follows one decision from audio in to command out.
Files rotate at midnight and are kept 30 days. Everything passes through ``redact`` (I8).
"""

from __future__ import annotations

import contextvars
import itertools
import json
import logging
import logging.handlers
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from cutcut.common.privacy import redact

LOG_RETENTION_DAYS: Final = 30

_correlation: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "cutcut_correlation_id", default=None
)
_counter = itertools.count(1)
_RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message"}


def new_correlation_id(prefix: str = "d") -> str:
    """Short, readable, non-hex ID (so it can never be mistaken for a card number)."""
    return f"{prefix}-{datetime.now(UTC):%H%M%S}-{next(_counter)}"


def current_correlation_id() -> str | None:
    return _correlation.get()


@contextmanager
def correlation(cid: str | None = None) -> Iterator[str]:
    cid = cid or new_correlation_id()
    token = _correlation.set(cid)
    try:
        yield cid
    finally:
        _correlation.reset(token)


class JsonFormatter(logging.Formatter):
    def __init__(self, process_name: str) -> None:
        super().__init__()
        self.process_name = process_name

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC)
            .astimezone()
            .isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "process": self.process_name,
            "module": record.name,
            "msg": record.getMessage(),
        }
        cid = getattr(record, "correlation_id", None) or _correlation.get()
        if cid:
            line["correlation_id"] = cid
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in line and not key.startswith("_"):
                line[key] = value
        if record.exc_info:
            line["exc"] = self.formatException(record.exc_info)
        ts = line.pop("ts")
        return json.dumps({"ts": ts, **redact(line)}, ensure_ascii=False, default=str)


def setup_logging(
    process_name: str,
    log_dir: Path | None = None,
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """Configure the root logger for one CutCut process. Safe to call more than once."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_cutcut", False):
            root.removeHandler(handler)
            handler.close()
    formatter = JsonFormatter(process_name)
    handlers: list[logging.Handler] = []
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_dir / f"{process_name}.jsonl",
            when="midnight",
            backupCount=LOG_RETENTION_DAYS,
            encoding="utf-8",
            delay=True,
        )
        handlers.append(file_handler)
    if console:
        handlers.append(logging.StreamHandler(sys.stderr))
    for handler in handlers:
        handler.setFormatter(formatter)
        handler._cutcut = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(level)
    return logging.getLogger("cutcut")
