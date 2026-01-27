"""
GeminiSDK Client - Main entry point for the Gemini SDK.

This module provides the GeminiClient class, which manages the connection
to the Gemini Code Assist API and provides session management capabilities.

Example:
    >>> from geminisdk import GeminiClient
    >>>
    >>> async def main():
    ...     client = GeminiClient()
    ...     session = await client.create_session({"model": "gemini-2.5-pro"})
    ...     response = await session.send_and_wait({"prompt": "Hello!"})
    ...     print(response.data.content)
    ...     await session.destroy()
    ...     await client.close()
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from .auth import GeminiOAuthManager
from .backend import GeminiBackend
from .exceptions import (
    SessionNotFoundError,
)
from .session import GeminiSession
from .types import (
    GEMINI_CLI_MODELS,
    ConnectionState,
    GeminiClientOptions,
    ModelInfo,
    SessionConfig,
    SessionMetadata,
)

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Main client for interacting with the Gemini Code Assist API.

    The GeminiClient manages the connection to the Gemini API and provides
    methods to create and manage conversation sessions. It handles OAuth
    authentication automatically using credentials stored by the Gemini CLI.

    The client follows a similar pattern to the GitHub Copilot SDK.

    Attributes:
        options: The configuration options for the client.
        state: Current connection state.

    Example:
        >>> # Create a client with default options
        >>> client = GeminiClient()
        >>>
        >>> # Create a session and send a message
        >>> session = await client.create_session({"model": "gemini-2.5-pro"})
        >>> session.on(lambda event: print(event.type))
        >>> await session.send({"prompt": "Hello!"})
        >>>
        >>> # Clean up
        >>> await session.destroy()
        >>> await client.close()

        >>> # Or use as context manager
        >>> async with GeminiClient() as client:
        ...     session = await client.create_session()
        ...     # Use session...
    """

    def __init__(self, options: GeminiClientOptions | None = None) -> None:
        """Initialize the GeminiClient.

        Args:
            options: Optional configuration options.
        """
        self._options = options or {}
        self._state: ConnectionState = "disconnected"
        self._backend: GeminiBackend | None = None
        self._oauth_manager: GeminiOAuthManager | None = None
        self._sessions: dict[str, GeminiSession] = {}
        self._started = False
        self._auto_refresh_task: asyncio.Task[None] | None = None

    @property
    def options(self) -> GeminiClientOptions:
        """Get the client options."""
        return self._options  # type: ignore

    @property
    def state(self) -> ConnectionState:
        """Get the current connection state."""
        return self._state

    async def __aenter__(self) -> GeminiClient:
        """Enter async context manager."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager."""
        await self.close()

    async def start(self) -> None:
        """
        Start the client and establish connection.

        This initializes the OAuth manager and backend, and verifies
        that valid credentials are available.

        Raises:
            AuthenticationError: If authentication fails.
            ConfigurationError: If configuration is invalid.
        """
        if self._started:
            return

        self._state = "connecting"

        try:
            # Initialize OAuth manager
            self._oauth_manager = GeminiOAuthManager(
                oauth_path=self._options.get("oauth_path"),
                client_id=self._options.get("client_id"),
                client_secret=self._options.get("client_secret"),
            )

            # Initialize backend
            self._backend = GeminiBackend(
                timeout=self._options.get("timeout", 720.0),
                oauth_path=self._options.get("oauth_path"),
                client_id=self._options.get("client_id"),
                client_secret=self._options.get("client_secret"),
            )
            await self._backend.__aenter__()

            # Verify authentication
            await self._oauth_manager.ensure_authenticated()

            self._state = "connected"
            self._started = True

            # Start auto-refresh if enabled
            if self._options.get("auto_refresh", True):
                self._start_auto_refresh()

            logger.info("GeminiClient started successfully")

        except Exception as e:
            self._state = "error"
            logger.error(f"Failed to start GeminiClient: {e}")
            raise

    def _start_auto_refresh(self) -> None:
        """Start background task to refresh tokens."""
        if self._auto_refresh_task is not None:
            return

        async def refresh_loop() -> None:
            while True:
                await asyncio.sleep(30)  # Check every 30 seconds
                try:
                    if self._oauth_manager:
                        await self._oauth_manager.ensure_authenticated()
                except Exception as e:
                    logger.debug(f"Background token refresh failed: {e}")

        self._auto_refresh_task = asyncio.create_task(refresh_loop())

    async def stop(self) -> None:
        """
        Stop the client and clean up resources.

        This closes all active sessions and releases resources.
        """
        # Cancel auto-refresh task
        if self._auto_refresh_task:
            self._auto_refresh_task.cancel()
            try:
                await self._auto_refresh_task
            except asyncio.CancelledError:
                pass
            self._auto_refresh_task = None

        # Destroy all sessions
        for session in list(self._sessions.values()):
            try:
                await session.destroy()
            except Exception as e:
                logger.warning(f"Error destroying session: {e}")

        self._sessions.clear()

        # Close backend
        if self._backend:
            await self._backend.__aexit__(None, None, None)
            self._backend = None

        self._oauth_manager = None
        self._state = "disconnected"
        self._started = False

        logger.info("GeminiClient stopped")

    async def close(self) -> None:
        """Alias for stop()."""
        await self.stop()

    async def create_session(self, config: SessionConfig | None = None) -> GeminiSession:
        """
        Create a new conversation session.

        Sessions maintain conversation state and handle message exchange
        with the Gemini API.

        Args:
            config: Optional configuration for the session, including
                model selection, tools, system messages, etc.

        Returns:
            A GeminiSession instance for the new session.

        Raises:
            RuntimeError: If the client is not connected.

        Example:
            >>> # Basic session
            >>> session = await client.create_session()
            >>>
            >>> # Session with model and configuration
            >>> session = await client.create_session({
            ...     "model": "gemini-2.5-pro",
            ...     "streaming": True,
            ...     "system_message": "You are a helpful assistant.",
            ... })
        """
        if not self._started:
            await self.start()

        if not self._backend:
            raise RuntimeError("Client not connected. Call start() first.")

        cfg = config or {}
        session_id = cfg.get("session_id") or str(uuid.uuid4())
        model = cfg.get("model", "gemini-2.5-pro")

        # Create session
        session = GeminiSession(
            session_id=session_id,
            model=model,
            backend=self._backend,
            tools=cfg.get("tools"),
            system_message=cfg.get("system_message"),
            generation_config=cfg.get("generation_config"),
            thinking_config=cfg.get("thinking_config"),
            streaming=cfg.get("streaming", True),
        )

        self._sessions[session_id] = session
        logger.debug(f"Created session {session_id} with model {model}")

        return session

    async def get_session(self, session_id: str) -> GeminiSession:
        """
        Get an existing session by ID.

        Args:
            session_id: The session ID.

        Returns:
            The session instance.

        Raises:
            SessionNotFoundError: If the session doesn't exist.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        return session

    async def list_sessions(self) -> list[SessionMetadata]:
        """
        List all active sessions.

        Returns:
            List of session metadata.
        """
        result: list[SessionMetadata] = []
        for session in self._sessions.values():
            result.append(
                {
                    "session_id": session.session_id,
                    "start_time": session.start_time.isoformat(),
                    "modified_time": session.modified_time.isoformat(),
                    "model": session.model,
                }
            )
        return result

    async def delete_session(self, session_id: str) -> None:
        """
        Delete a session.

        Args:
            session_id: The session ID to delete.
        """
        session = self._sessions.pop(session_id, None)
        if session:
            await session.destroy()
            logger.debug(f"Deleted session {session_id}")

    def get_state(self) -> ConnectionState:
        """
        Get the current connection state.

        Returns:
            The connection state.
        """
        return self._state

    async def get_auth_status(self) -> dict[str, Any]:
        """
        Get the current authentication status.

        Returns:
            Authentication status information.
        """
        if not self._oauth_manager:
            return {"authenticated": False}

        try:
            credentials = await self._oauth_manager.get_credentials()
            return {
                "authenticated": True,
                "token_type": credentials.token_type,
                "expires_at": credentials.expiry_date,
            }
        except Exception:
            return {"authenticated": False}

    async def list_models(self) -> list[ModelInfo]:
        """
        List available models.

        Returns:
            List of model information.
        """
        models: list[ModelInfo] = []

        for model_id, info in GEMINI_CLI_MODELS.items():
            models.append(
                {
                    "id": model_id,
                    "name": info.name,
                    "capabilities": {
                        "supports": {
                            "vision": False,
                            "tools": info.supports_native_tools,
                            "thinking": info.supports_thinking,
                        },
                        "limits": {
                            "max_context_window_tokens": info.context_window,
                            "max_prompt_tokens": info.context_window,
                        },
                    },
                }
            )

        return models

    async def refresh_auth(self) -> None:
        """
        Force refresh the authentication token.
        """
        if self._oauth_manager:
            await self._oauth_manager.ensure_authenticated(force_refresh=True)
            logger.debug("Authentication token refreshed")
