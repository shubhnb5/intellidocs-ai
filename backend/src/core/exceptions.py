"""Base class for expected, user-facing errors.

Raise AppError (or a subclass) from route/service code instead of returning
ad-hoc HTTPExceptions. Every subclass gets the same {"error": {...}} envelope
as validation errors (see core/errors.py) without each route having to build
that response by hand.
"""


class AppError(Exception):
    status_code: int = 400
    error_type: str = "app_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class UnsupportedFileTypeError(AppError):
    status_code = 415
    error_type = "unsupported_file_type"


class FileTooLargeError(AppError):
    status_code = 413
    error_type = "file_too_large"


class DocumentNotFoundError(AppError):
    status_code = 404
    error_type = "document_not_found"


class LLMNotConfiguredError(AppError):
    status_code = 503
    error_type = "llm_not_configured"


class LLMServiceError(AppError):
    status_code = 502
    error_type = "llm_service_error"


class MCPServiceError(AppError):
    status_code = 502
    error_type = "mcp_service_error"


class EmailAlreadyRegisteredError(AppError):
    status_code = 409
    error_type = "email_already_registered"


class AuthenticationError(AppError):
    """Covers every way a request fails to prove who it's from: missing
    token, malformed token, expired token, wrong credentials, deleted user.
    One error type is deliberate — the client only ever needs to react by
    sending the user back to login, not branch on which specific reason."""

    status_code = 401
    error_type = "authentication_error"


class RateLimitExceededError(AppError):
    status_code = 429
    error_type = "rate_limit_exceeded"
