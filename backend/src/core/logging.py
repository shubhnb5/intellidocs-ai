"""Structured (JSON) logging via loguru, with request-id propagation.

Why not print()? Because from Phase 6 onward a single user question moves
through router -> retrieval/tool agents -> summarizer, each emitting log
lines. A shared request_id on every line (see middleware.py) lets you filter
for every event belonging to one request instead of untangling interleaved
output from concurrent requests.

Elsewhere in the codebase, just `from loguru import logger` and log directly —
loguru is a configured global, not a per-module logger you have to construct.
"""

import sys
from contextvars import ContextVar

from loguru import logger

# Holds the current request's ID so any log call anywhere in the call stack
# picks it up automatically, without threading it through every function
# signature.
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")


def _inject_request_id(record: dict) -> None:
    record["extra"]["request_id"] = request_id_ctx_var.get()


def configure_logging(*, debug: bool = False) -> None:
    logger.remove()  # drop loguru's default stderr handler so we control format
    logger.configure(patcher=_inject_request_id)
    # Windows' default console codepage can't encode the emoji in loguru's
    # serialized log-level icons -- force UTF-8 so logging itself doesn't
    # crash on every request.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logger.add(
        sys.stdout,
        serialize=True,  # emit one JSON object per line
        level="DEBUG" if debug else "INFO",
        backtrace=False,
        diagnose=False,  # never dump local variable values in prod logs
    )
