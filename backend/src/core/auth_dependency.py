"""FastAPI dependencies that resolve "who is this request from".

Three variants share one underlying check (resolve_user_from_token):
- get_current_user: standard `Authorization: Bearer` header, for REST routes.
- get_current_user_or_internal: also accepts a shared-secret service header,
  for the one route the MCP server's document_metadata tool calls back into
  (see routes/document_routes.py) — MCP tool calls don't carry the
  original end-user's identity through, so that lookup authenticates as a
  trusted service instead of impersonating a specific user.
- resolve_user_from_token: the plain function /ws/chat calls manually,
  because WebSocket auth failures need a controlled close *before* accept()
  rather than an HTTPException, which a raising Depends can't give us (see
  chat_websocket.py).
"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.exceptions import AuthenticationError
from src.db.database import get_db_session
from src.db.sql_models import UserRecord
from src.services.security import decode_token

INTERNAL_API_KEY_HEADER = "x-internal-api-key"

_bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    user_id: str
    email: str


def resolve_user_from_token(token: str, db: Session) -> CurrentUser:
    payload = decode_token(token, expected_type="access")
    user = db.get(UserRecord, payload["sub"])
    if user is None:
        raise AuthenticationError("Invalid or expired token.")
    return CurrentUser(user_id=user.user_id, email=user.email)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db_session),
) -> CurrentUser:
    if credentials is None:
        raise AuthenticationError("Missing bearer token.")
    return resolve_user_from_token(credentials.credentials, db)


async def get_current_user_or_internal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db_session),
) -> CurrentUser | None:
    """None means "trusted internal service, not a specific user" — the
    caller is responsible for treating that as unrestricted access rather
    than as an anonymous/unauthenticated user."""
    settings = get_settings()
    internal_key = request.headers.get(INTERNAL_API_KEY_HEADER)
    if settings.internal_api_key and internal_key == settings.internal_api_key:
        return None
    return await get_current_user(credentials=credentials, db=db)
