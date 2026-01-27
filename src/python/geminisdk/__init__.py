"""
GeminiCLI SDK - A Python SDK for Google Gemini Code Assist API.

This SDK provides a high-level interface for interacting with the Gemini
Code Assist API, supporting OAuth authentication, streaming responses,
tool calling, and session management.

The SDK is modeled after the GitHub Copilot SDK, providing a familiar
interface for developers.

Example:
    >>> from geminisdk import GeminiClient
    >>>
    >>> async def main():
    ...     async with GeminiClient() as client:
    ...         session = await client.create_session({
    ...             "model": "gemini-2.5-pro",
    ...             "streaming": True,
    ...         })
    ...
    ...         response = await session.send_and_wait({
    ...             "prompt": "What is Python?",
    ...         })
    ...
    ...         print(response.data["content"])
    ...
    >>> import asyncio
    >>> asyncio.run(main())

For more information, see:
- Documentation: https://github.com/OEvortex/geminicli-sdk
- Gemini CLI: https://github.com/google-gemini/gemini-cli
"""

__version__ = "0.1.1"
__author__ = "OEvortex"

# Client
# Authentication
from .auth import GeminiOAuthManager

# Backend
from .backend import GeminiBackend
from .client import GeminiClient

# Exceptions
from .exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    GeminiSDKError,
    OnboardingError,
    PermissionDeniedError,
    QuotaExceededError,
    RateLimitError,
    SessionClosedError,
    SessionError,
    SessionNotFoundError,
    StreamError,
    TokenRefreshError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
)

# Session
from .session import GeminiSession

# Tools
from .tools import (
    Tool,
    ToolRegistry,
    create_tool,
    define_tool,
    get_default_registry,
    register_tool,
)

# Types
from .types import (
    GEMINI_CLI_MODELS,
    GEMINI_CODE_ASSIST_API_VERSION,
    GEMINI_CODE_ASSIST_ENDPOINT,
    # Constants
    GEMINI_OAUTH_CLIENT_ID,
    GEMINI_OAUTH_CLIENT_SECRET,
    GEMINI_OAUTH_SCOPES,
    # State
    ConnectionState,
    ContentPart,
    EventType,
    FunctionCall,
    GeminiClientOptions,
    GeminiModelInfo,
    # OAuth
    GeminiOAuthCredentials,
    # Configuration
    GenerationConfig,
    # Response
    LLMChunk,
    LLMUsage,
    # Messages
    Message,
    MessageOptions,
    # Models
    ModelInfo,
    Role,
    # Session
    SessionConfig,
    SessionEvent,
    SessionEventHandler,
    SessionMetadata,
    ThinkingConfig,
    # Tools (Tool class is imported from .tools)
    ToolCall,
    ToolInvocation,
    ToolResult,
)

__all__ = [
    # Version
    "__version__",
    # Client
    "GeminiClient",
    # Session
    "GeminiSession",
    # Backend
    "GeminiBackend",
    # Authentication
    "GeminiOAuthManager",
    # Tools
    "Tool",
    "ToolRegistry",
    "create_tool",
    "define_tool",
    "get_default_registry",
    "register_tool",
    # Types - Messages
    "Message",
    "Role",
    "ContentPart",
    # Types - Tools
    "ToolCall",
    "FunctionCall",
    "ToolInvocation",
    "ToolResult",
    # Types - Session
    "SessionConfig",
    "SessionMetadata",
    "SessionEvent",
    "SessionEventHandler",
    "EventType",
    "MessageOptions",
    # Types - Response
    "LLMChunk",
    "LLMUsage",
    # Types - Configuration
    "GenerationConfig",
    "ThinkingConfig",
    "GeminiClientOptions",
    # Types - State
    "ConnectionState",
    # Types - OAuth
    "GeminiOAuthCredentials",
    # Types - Models
    "ModelInfo",
    "GeminiModelInfo",
    "GEMINI_CLI_MODELS",
    # Types - Constants
    "GEMINI_OAUTH_CLIENT_ID",
    "GEMINI_OAUTH_CLIENT_SECRET",
    "GEMINI_OAUTH_SCOPES",
    "GEMINI_CODE_ASSIST_ENDPOINT",
    "GEMINI_CODE_ASSIST_API_VERSION",
    # Exceptions
    "GeminiSDKError",
    "AuthenticationError",
    "TokenRefreshError",
    "ConfigurationError",
    "APIError",
    "RateLimitError",
    "QuotaExceededError",
    "PermissionDeniedError",
    "StreamError",
    "SessionError",
    "SessionNotFoundError",
    "SessionClosedError",
    "ToolError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "OnboardingError",
]
