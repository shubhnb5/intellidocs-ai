"""WebSocket chat endpoint — the streaming counterpart to POST /api/chat/ask.
Same agent pipeline (services/agent_graph.py + services/summarizer_agent.py),
but the client sees each agent's activity the moment it happens, and the
answer as Claude generates it, instead of waiting for one complete response.
This is what powers the frontend's agent activity panel and the live-typing
answer.

Wire protocol (all messages are JSON):

Client connects to: /ws/chat?token=<access_token>
    Auth happens once, at connect time, from a query param -- browsers'
    native WebSocket API can't set an Authorization header on the handshake.
    The handshake is always accepted first, then immediately closed with
    code 4401 (see AUTH_FAILURE_CLOSE_CODE below) if the token is missing or
    invalid: closing *before* accept would only be visible to the browser as
    a generic connection error (no code, no reason), whereas an application
    close code sent after accept is exactly what the browser's WebSocket
    onclose handler receives as event.code -- the only way to hand the
    frontend a machine-readable "this failed because you're unauthenticated"
    signal instead of an opaque failure. Note the token isn't re-checked per
    message -- a session that outlives the access token's expiry stays
    connected until it disconnects/reconnects, a known simplification.

Client -> server, one per question:
    {"type": "ask", "question": "...", "top_k": 5}

Server -> client, in order, per question:
    {"type": "agent_activity", "agent": "router", "message": "...", "timestamp": "..."}
    ... one per agent that ran ...
    {"type": "answer_chunk", "text": "..."}
    ... one per token/text delta as Claude generates the answer ...
    {"type": "done", "route": "rag", "sources": [...]}
or, if anything failed:
    {"type": "error", "message": "..."}

The connection stays open across multiple questions — the frontend sends
another "ask" on the same socket rather than reconnecting per message.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.core.auth_dependency import CurrentUser, resolve_user_from_token
from src.core.config import get_settings
from src.core.exceptions import AppError, AuthenticationError
from src.core.rate_limit import check_rate_limit
from src.db.database import get_db_session
from src.routes.chat_routes import AskRequest
from src.services.agent_graph import agent_graph
from src.services.agent_state import AgentState
from src.services.summarizer_agent import stream_summary

router = APIRouter()

AUTH_FAILURE_CLOSE_CODE = 4401

# The subset of AgentState that has exactly one writer node -- safe to
# overwrite as updates arrive. "events" is handled separately below (sent
# immediately, never accumulated locally) specifically because it's the one
# field with a reducer (operator.add, see agent_state.py); merging it here
# with a plain overwrite would silently drop every event but the last node's.
_CONTEXT_KEYS = ("route", "route_reasoning", "retrieved_chunks", "tool_results")


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> None:
    await websocket.accept()

    if token is None:
        await websocket.close(code=AUTH_FAILURE_CLOSE_CODE, reason="Missing token.")
        return
    try:
        current_user = resolve_user_from_token(token, db)
    except AuthenticationError as exc:
        await websocket.close(code=AUTH_FAILURE_CLOSE_CODE, reason=exc.message)
        return

    client_ip = websocket.client.host if websocket.client else "unknown"

    while True:
        try:
            raw_message = await websocket.receive_json()
        except WebSocketDisconnect:
            return

        try:
            request = AskRequest.model_validate(raw_message)
        except ValidationError as exc:
            await websocket.send_json({"type": "error", "message": str(exc)})
            continue

        try:
            settings = get_settings()
            await check_rate_limit(
                scope="chat_ws",
                identifier=client_ip,
                limit=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window_seconds,
            )
            await _answer_question(websocket, request, current_user)
        except WebSocketDisconnect:
            return
        except AppError as exc:
            await websocket.send_json({"type": "error", "message": exc.message})
        except Exception as exc:  # keep the socket alive for the next question
            logger.exception("unhandled error in /ws/chat: {}", exc)
            await websocket.send_json(
                {"type": "error", "message": "Something went wrong. Please try again."}
            )


async def _answer_question(
    websocket: WebSocket, request: AskRequest, current_user: CurrentUser
) -> None:
    initial_state: AgentState = {
        "question": request.question,
        "top_k": request.top_k,
        "user_id": current_user.user_id,
        "route": "",
        "route_reasoning": "",
        "retrieved_chunks": [],
        "tool_results": [],
        "events": [],
    }

    context = {key: initial_state[key] for key in _CONTEXT_KEYS}

    async for update in agent_graph.astream(initial_state, stream_mode="updates"):
        for node_output in update.values():
            for event in node_output.get("events", []):
                await websocket.send_json(
                    {
                        "type": "agent_activity",
                        "agent": event.agent,
                        "message": event.message,
                        "timestamp": event.timestamp.isoformat(),
                    }
                )
            for key in _CONTEXT_KEYS:
                if key in node_output:
                    context[key] = node_output[key]

    # The Summarizer isn't a graph node (see summarizer_agent.py's docstring
    # for why), so it never appears in the loop above -- send its activity
    # event by hand here, right before it actually starts, so the panel
    # still shows all four agents instead of silently dropping this one.
    await websocket.send_json(
        {
            "type": "agent_activity",
            "agent": "summarizer",
            "message": "Composing the final answer.",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    async for text_delta in stream_summary(
        request.question, context["retrieved_chunks"], context["tool_results"]
    ):
        await websocket.send_json({"type": "answer_chunk", "text": text_delta})

    await websocket.send_json(
        {
            "type": "done",
            "route": context["route"],
            "sources": [
                {
                    "filename": chunk.filename,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "score": chunk.score,
                }
                for chunk in context["retrieved_chunks"]
            ],
        }
    )
