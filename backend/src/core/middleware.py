"""HTTP middleware. Currently just request-id stamping; rate limiting joins
here in Phase 8."""

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from src.core.logging import request_id_ctx_var


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Stamp every request with an ID so a single question can be traced
    through router -> agents -> response in the logs (see core/logging.py)."""
    incoming_id = request.headers.get("x-request-id")
    request_id = incoming_id or str(uuid.uuid4())
    token = request_id_ctx_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_ctx_var.reset(token)
    response.headers["x-request-id"] = request_id
    response.headers["x-process-time-ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    return response
