"""Registration, login, refresh, logout, and "who am I" — see
services/auth.py for the actual token/allowlist logic, which this route
layer just adapts to request/response schemas.

Login and register are rate-limited (see core/rate_limit.py) since they're
the classic brute-force / signup-spam targets and, unlike the other
rate-limited routes, have no auth of their own to fall back on.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.core.auth_dependency import CurrentUser, get_current_user
from src.core.config import get_settings
from src.core.rate_limit import RateLimiter
from src.db.database import get_db_session
from src.services.auth import (
    authenticate_user,
    issue_token_pair,
    refresh_token_pair,
    register_user,
    revoke_refresh_token,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

_settings = get_settings()
_auth_rate_limiter = RateLimiter(
    limit=_settings.rate_limit_requests,
    window_seconds=_settings.rate_limit_window_seconds,
    scope="auth",
)


# --- request/response schemas -----------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    user_id: str
    email: str


# --- routes --------------------------------------------------------------


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Create an account and receive a token pair",
    dependencies=[Depends(_auth_rate_limiter)],
)
async def register(
    request: RegisterRequest, db: Session = Depends(get_db_session)
) -> TokenResponse:
    user = await register_user(db, email=request.email, password=request.password)
    pair = await issue_token_pair(user_id=user.user_id, email=user.email)
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange email/password for a token pair",
    dependencies=[Depends(_auth_rate_limiter)],
)
async def login(request: LoginRequest, db: Session = Depends(get_db_session)) -> TokenResponse:
    user = await authenticate_user(db, email=request.email, password=request.password)
    pair = await issue_token_pair(user_id=user.user_id, email=user.email)
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new token pair (rotates the refresh token)",
)
async def refresh(request: RefreshRequest, db: Session = Depends(get_db_session)) -> TokenResponse:
    pair = await refresh_token_pair(db, refresh_token=request.refresh_token)
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/logout", status_code=204, summary="Revoke a refresh token")
async def logout(request: LogoutRequest) -> None:
    await revoke_refresh_token(refresh_token=request.refresh_token)


@router.get("/me", response_model=UserResponse, summary="The currently authenticated user")
async def me(current_user: CurrentUser = Depends(get_current_user)) -> UserResponse:
    return UserResponse(user_id=current_user.user_id, email=current_user.email)
