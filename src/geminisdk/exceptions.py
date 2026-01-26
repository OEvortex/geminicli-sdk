"""
Custom exceptions for the GeminiSDK

Based on patterns from GitHub Copilot SDK and Revibe implementations.
"""

from __future__ import annotations

from typing import Any


class GeminiSDKError(Exception):
    """Base exception for all GeminiSDK errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthenticationError(GeminiSDKError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)


class CredentialsNotFoundError(AuthenticationError):
    """Raised when OAuth credentials are not found."""

    def __init__(
        self,
        credential_path: str,
        message: str | None = None,
    ):
        msg = message or (
            f"Gemini OAuth credentials not found at {credential_path}. "
            "Please login using the Gemini CLI first: gemini auth login"
        )
        super().__init__(msg, {"credential_path": credential_path})
        self.credential_path = credential_path


class TokenRefreshError(AuthenticationError):
    """Raised when token refresh fails."""

    def __init__(
        self,
        message: str = "Failed to refresh access token",
        status_code: int | None = None,
        response_body: str | None = None,
    ):
        details = {}
        if status_code:
            details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body
        super().__init__(message, details)
        self.status_code = status_code
        self.response_body = response_body


class TokenExpiredError(AuthenticationError):
    """Raised when the access token has expired and cannot be refreshed."""

    def __init__(self, message: str = "Access token has expired"):
        super().__init__(message)


class ConnectionError(GeminiSDKError):
    """Raised when connection to the API fails."""

    def __init__(
        self,
        message: str = "Failed to connect to Gemini API",
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if endpoint:
            details["endpoint"] = endpoint
        super().__init__(message, details)
        self.endpoint = endpoint


class APIError(GeminiSDKError):
    """Raised when the API returns an error."""

    def __init__(
        self,
        message: str,
        status_code: int,
        response_body: str | None = None,
        endpoint: str | None = None,
    ):
        details = {
            "status_code": status_code,
        }
        if response_body:
            details["response_body"] = response_body
        if endpoint:
            details["endpoint"] = endpoint
        super().__init__(message, details)
        self.status_code = status_code
        self.response_body = response_body
        self.endpoint = endpoint


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        status_code: int = 429,
        retry_after: int | None = None,
        response_body: str | None = None,
    ):
        super().__init__(message, status_code, response_body)
        self.retry_after = retry_after
        if retry_after:
            self.details["retry_after"] = retry_after


class QuotaExceededError(APIError):
    """Raised when API quota is exceeded."""

    def __init__(
        self,
        message: str = "Quota exceeded",
        status_code: int = 429,
        reset_time: str | None = None,
        response_body: str | None = None,
    ):
        super().__init__(message, status_code, response_body)
        self.reset_time = reset_time
        if reset_time:
            self.details["reset_time"] = reset_time


class PermissionDeniedError(APIError):
    """Raised when permission is denied."""

    def __init__(
        self,
        message: str = "Permission denied",
        status_code: int = 403,
        response_body: str | None = None,
    ):
        super().__init__(message, status_code, response_body)


class NotFoundError(APIError):
    """Raised when a resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        status_code: int = 404,
        resource: str | None = None,
        response_body: str | None = None,
    ):
        super().__init__(message, status_code, response_body)
        self.resource = resource
        if resource:
            self.details["resource"] = resource


class SessionError(GeminiSDKError):
    """Raised when there's an error with a session."""

    def __init__(
        self,
        message: str,
        session_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if session_id:
            details["session_id"] = session_id
        super().__init__(message, details)
        self.session_id = session_id


class SessionNotFoundError(SessionError):
    """Raised when a session is not found."""

    def __init__(self, session_id: str):
        super().__init__(f"Session not found: {session_id}", session_id)


class SessionClosedError(SessionError):
    """Raised when trying to use a closed session."""

    def __init__(self, session_id: str | None = None):
        super().__init__("Session is closed", session_id)


class ToolError(GeminiSDKError):
    """Raised when there's an error with a tool."""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if tool_name:
            details["tool_name"] = tool_name
        super().__init__(message, details)
        self.tool_name = tool_name


class ToolNotFoundError(ToolError):
    """Raised when a tool is not found."""

    def __init__(self, tool_name: str):
        super().__init__(f"Tool not found: {tool_name}", tool_name)


class ToolExecutionError(ToolError):
    """Raised when tool execution fails."""

    def __init__(
        self,
        message: str,
        tool_name: str,
        original_error: Exception | None = None,
    ):
        details = {}
        if original_error:
            details["original_error"] = str(original_error)
        super().__init__(message, tool_name, details)
        self.original_error = original_error


class ValidationError(GeminiSDKError):
    """Raised when validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, details)
        self.field = field
        self.value = value


class ConfigurationError(GeminiSDKError):
    """Raised when there's a configuration error."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
    ):
        details = {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, details)
        self.config_key = config_key


class ProjectError(GeminiSDKError):
    """Raised when there's an error with project configuration."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
    ):
        details = {}
        if project_id:
            details["project_id"] = project_id
        super().__init__(message, details)
        self.project_id = project_id


class OnboardingError(ProjectError):
    """Raised when Gemini Code Assist onboarding fails."""

    def __init__(
        self,
        message: str = "Failed to complete Gemini Code Assist onboarding",
        tier_id: str | None = None,
    ):
        super().__init__(message)
        self.tier_id = tier_id
        if tier_id:
            self.details["tier_id"] = tier_id


class StreamError(GeminiSDKError):
    """Raised when there's an error during streaming."""

    def __init__(
        self,
        message: str,
        partial_content: str | None = None,
    ):
        details = {}
        if partial_content:
            details["partial_content"] = partial_content[:500]  # Truncate
        super().__init__(message, details)
        self.partial_content = partial_content


class CancellationError(GeminiSDKError):
    """Raised when an operation is cancelled."""

    def __init__(self, message: str = "Operation was cancelled"):
        super().__init__(message)


class TimeoutError(GeminiSDKError):
    """Raised when an operation times out."""

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout: float | None = None,
    ):
        details = {}
        if timeout:
            details["timeout"] = timeout
        super().__init__(message, details)
        self.timeout = timeout
