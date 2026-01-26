"""
Type definitions for the GeminiSDK

Based on:
- GitHub Copilot SDK types
- Google Gemini CLI implementation
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

# =============================================================================
# Connection and Session Types
# =============================================================================

ConnectionState = Literal["disconnected", "connecting", "connected", "error"]
LogLevel = Literal["none", "error", "warning", "info", "debug", "all"]


class Role(str, Enum):
    """Message role in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# =============================================================================
# OAuth and Authentication Types
# =============================================================================


@dataclass
class GeminiOAuthCredentials:
    """OAuth credentials for Gemini CLI."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expiry_date: int = 0  # Timestamp in milliseconds


# =============================================================================
# Model Types
# =============================================================================


@dataclass
class GeminiModelInfo:
    """Model information for Gemini CLI models."""

    id: str
    name: str
    context_window: int = 1_048_576  # 1M tokens for gemini-2.x
    max_output: int = 32_768  # 32K output tokens
    input_price: float = 0.0  # Free tier
    output_price: float = 0.0  # Free tier
    supports_native_tools: bool = True
    supports_thinking: bool = True


class ModelVisionLimits(TypedDict, total=False):
    """Vision-specific limits for a model."""

    supported_media_types: list[str]
    max_prompt_images: int
    max_prompt_image_size: int


class ModelLimits(TypedDict, total=False):
    """Model limits."""

    max_prompt_tokens: int
    max_context_window_tokens: int
    vision: ModelVisionLimits


class ModelSupports(TypedDict):
    """Model support flags."""

    vision: bool
    tools: bool
    thinking: bool


class ModelCapabilities(TypedDict):
    """Model capabilities and limits."""

    supports: ModelSupports
    limits: ModelLimits


class ModelInfo(TypedDict):
    """Information about an available model."""

    id: str
    name: str
    capabilities: ModelCapabilities


# =============================================================================
# Message and Content Types
# =============================================================================


@dataclass
class ContentPart:
    """A part of message content."""

    text: str | None = None
    image_url: str | None = None
    image_data: bytes | None = None
    image_mime_type: str | None = None


@dataclass
class Message:
    """A message in a conversation."""

    role: Role
    content: str | list[ContentPart]
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class Attachment(TypedDict, total=False):
    """File attachment for a message."""

    type: Literal["file", "image"]
    path: str
    url: str
    data: str  # base64 encoded
    mime_type: str


# =============================================================================
# Tool Types
# =============================================================================


@dataclass
class FunctionCall:
    """A function call from the model."""

    name: str
    arguments: dict[str, Any] | str


@dataclass
class ToolCall:
    """A tool call from the model."""

    id: str
    type: Literal["function"] = "function"
    function: FunctionCall = field(default_factory=lambda: FunctionCall(name="", arguments={}))


class ToolInvocation(TypedDict):
    """A tool invocation request."""

    name: str
    arguments: dict[str, Any]
    call_id: str


ToolResultType = Literal["success", "failure", "rejected", "denied"]


class ToolResult(TypedDict, total=False):
    """Result of a tool invocation."""

    result_type: ToolResultType
    text_result_for_llm: str
    binary_result: bytes
    session_log: str


ToolHandler = Callable[[ToolInvocation], ToolResult | Awaitable[ToolResult]]


@dataclass
class Tool:
    """Definition of a tool that can be used by the model."""

    name: str
    description: str
    parameters: dict[str, Any] | None = None
    handler: ToolHandler | None = None


# =============================================================================
# Generation Config Types
# =============================================================================


@dataclass
class GenerationConfig:
    """Configuration for text generation."""

    temperature: float = 0.7
    max_output_tokens: int | None = None
    top_p: float | None = None
    top_k: int | None = None
    stop_sequences: list[str] | None = None


@dataclass
class ThinkingConfig:
    """Configuration for model thinking/reasoning."""

    include_thoughts: bool = True
    thinking_budget: int | None = None


# =============================================================================
# Request/Response Types
# =============================================================================


class MessageOptions(TypedDict, total=False):
    """Options for sending a message."""

    prompt: str
    attachments: list[Attachment]
    context: str


@dataclass
class LLMUsage:
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMChunk:
    """A chunk of LLM response."""

    content: str = ""
    reasoning_content: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: LLMUsage | None = None
    finish_reason: str | None = None


# =============================================================================
# Session Types
# =============================================================================


class SessionConfig(TypedDict, total=False):
    """Configuration for creating a session."""

    session_id: str
    model: str
    tools: list[Tool]
    system_message: str
    generation_config: GenerationConfig
    thinking_config: ThinkingConfig
    streaming: bool


class SessionMetadata(TypedDict):
    """Metadata about a session."""

    session_id: str
    start_time: str
    modified_time: str
    summary: NotRequired[str]
    model: str


# =============================================================================
# Client Options Types
# =============================================================================


class GeminiClientOptions(TypedDict, total=False):
    """Options for creating a GeminiClient."""

    oauth_path: str  # Custom path to OAuth credentials
    client_id: str  # Custom OAuth client ID
    client_secret: str  # Custom OAuth client secret
    base_url: str  # Custom API base URL
    timeout: float  # Request timeout in seconds
    log_level: LogLevel
    auto_refresh: bool  # Auto-refresh tokens


# =============================================================================
# Event Types
# =============================================================================


class EventType(str, Enum):
    """Types of session events."""

    SESSION_CREATED = "session.created"
    SESSION_IDLE = "session.idle"
    SESSION_ERROR = "session.error"
    ASSISTANT_MESSAGE = "assistant.message"
    ASSISTANT_MESSAGE_DELTA = "assistant.message_delta"
    ASSISTANT_REASONING = "assistant.reasoning"
    ASSISTANT_REASONING_DELTA = "assistant.reasoning_delta"
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"


@dataclass
class SessionEvent:
    """An event from a session."""

    type: EventType
    data: Any
    session_id: str


SessionEventHandler = Callable[[SessionEvent], None]


# =============================================================================
# Constants
# =============================================================================

# OAuth2 Configuration (from official Gemini CLI)
GEMINI_OAUTH_REDIRECT_URI = "http://localhost:45289"
GEMINI_OAUTH_BASE_URL = "https://accounts.google.com"
GEMINI_OAUTH_TOKEN_ENDPOINT = f"{GEMINI_OAUTH_BASE_URL}/o/oauth2/token"
GEMINI_OAUTH_AUTH_ENDPOINT = f"{GEMINI_OAUTH_BASE_URL}/o/oauth2/v2/auth"

# Official Google OAuth client credentials for Gemini CLI
# See: https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/code_assist/oauth2.ts
GEMINI_OAUTH_CLIENT_ID = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
GEMINI_OAUTH_CLIENT_SECRET = "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"

# OAuth scopes required for Cloud Code API access
GEMINI_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# Code Assist API Configuration
GEMINI_CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"
GEMINI_CODE_ASSIST_API_VERSION = "v1internal"

# Credential storage
GEMINI_DIR = ".gemini"
GEMINI_CREDENTIAL_FILENAME = "oauth_creds.json"
GEMINI_ENV_FILENAME = ".env"

# Token refresh buffer (5 minutes before expiry)
TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000

# HTTP Status codes
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403

# Available Gemini CLI models
GEMINI_CLI_MODELS: dict[str, GeminiModelInfo] = {
    # Gemini 3 series (Preview)
    "gemini-3-pro-preview": GeminiModelInfo(
        id="gemini-3-pro-preview",
        name="Gemini 3 Pro Preview",
        context_window=1_000_000,  # Estimated
        max_output=65_536,  # Estimated
        supports_thinking=True,
    ),
    "gemini-3-flash-preview": GeminiModelInfo(
        id="gemini-3-flash-preview",
        name="Gemini 3 Flash Preview",
        context_window=1_000_000,  # Estimated
        max_output=65_536,  # Estimated
        supports_thinking=True,
    ),
    # Gemini 2.5 series
    "gemini-2.5-pro": GeminiModelInfo(
        id="gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        context_window=1_048_576,
        max_output=65_536,
        supports_thinking=True,
    ),
    "gemini-2.5-flash": GeminiModelInfo(
        id="gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        context_window=1_048_576,
        max_output=65_536,
        supports_thinking=True,
    ),
    "gemini-2.5-flash-lite": GeminiModelInfo(
        id="gemini-2.5-flash-lite",
        name="Gemini 2.5 Flash Lite",
        context_window=1_000_000,  # Estimated
        max_output=32_768,  # Estimated
        supports_thinking=False,
    ),
    # Auto-selection models
    "auto-gemini-3": GeminiModelInfo(
        id="auto-gemini-3",
        name="Auto (Gemini 3)",
        context_window=1_000_000,  # Estimated
        max_output=65_536,  # Estimated
        supports_thinking=True,
    ),
    "auto-gemini-2.5": GeminiModelInfo(
        id="auto-gemini-2.5",
        name="Auto (Gemini 2.5)",
        context_window=1_048_576,
        max_output=65_536,
        supports_thinking=True,
    ),
    "auto": GeminiModelInfo(
        id="auto",
        name="Auto (Default)",
        context_window=1_048_576,
        max_output=65_536,
        supports_thinking=True,
    ),
}


def get_geminicli_credential_path(custom_path: str | None = None) -> str:
    """Get the path to Gemini CLI OAuth credentials file.

    Args:
        custom_path: Optional custom path to the credentials file.

    Returns:
        Path to the credentials file.
    """
    if custom_path:
        return custom_path

    import os

    home = os.path.expanduser("~")
    return os.path.join(home, GEMINI_DIR, GEMINI_CREDENTIAL_FILENAME)


def get_geminicli_env_path(custom_path: str | None = None) -> str:
    """Get the path to Gemini CLI environment file.

    Args:
        custom_path: Optional custom path to the env file.

    Returns:
        Path to the env file.
    """
    if custom_path:
        return custom_path

    import os

    home = os.path.expanduser("~")
    return os.path.join(home, GEMINI_DIR, GEMINI_ENV_FILENAME)
