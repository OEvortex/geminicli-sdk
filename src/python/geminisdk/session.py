"""
GeminiSDK Session - Manages individual conversation sessions.

This module provides the GeminiSession class for managing conversations
with the Gemini API, similar to CopilotSession in the GitHub Copilot SDK.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .backend import GeminiBackend
from .exceptions import (
    SessionClosedError,
)
from .types import (
    EventType,
    GenerationConfig,
    Message,
    MessageOptions,
    Role,
    SessionEvent,
    SessionEventHandler,
    ThinkingConfig,
    Tool,
    ToolCall,
    ToolInvocation,
)

logger = logging.getLogger(__name__)


class GeminiSession:
    """
    A conversation session with the Gemini API.

    Sessions maintain conversation history, handle events, and manage
    tool execution. They provide both streaming and non-streaming
    message interfaces.

    This class follows a similar pattern to CopilotSession in the
    GitHub Copilot SDK.

    Example:
        >>> session = await client.create_session({"model": "gemini-2.5-pro"})
        >>>
        >>> # Subscribe to events
        >>> session.on(lambda event: print(event.type, event.data))
        >>>
        >>> # Send a message
        >>> await session.send({"prompt": "Hello!"})
        >>>
        >>> # Or send and wait for response
        >>> response = await session.send_and_wait({"prompt": "Hello!"})
        >>> print(response.data.content)
    """

    def __init__(
        self,
        session_id: str,
        model: str,
        backend: GeminiBackend,
        tools: list[Tool] | None = None,
        system_message: str | None = None,
        generation_config: GenerationConfig | None = None,
        thinking_config: ThinkingConfig | None = None,
        streaming: bool = True,
    ) -> None:
        """Initialize the session.

        Args:
            session_id: Unique session identifier.
            model: The model ID to use.
            backend: The backend for API communication.
            tools: Optional list of tools available to the model.
            system_message: Optional system message.
            generation_config: Optional generation configuration.
            thinking_config: Optional thinking configuration.
            streaming: Whether to use streaming responses.
        """
        self._session_id = session_id
        self._model = model
        self._backend = backend
        self._tools = tools or []
        self._tool_handlers: dict[str, Callable[..., Any]] = {}
        self._system_message = system_message
        self._generation_config = generation_config
        self._thinking_config = thinking_config
        self._streaming = streaming

        self._messages: list[Message] = []
        self._event_handlers: list[SessionEventHandler] = []
        self._closed = False
        self._start_time = datetime.now(timezone.utc)
        self._modified_time = datetime.now(timezone.utc)

        # Register tool handlers
        for tool in self._tools:
            if tool.handler:
                self._tool_handlers[tool.name] = tool.handler

        # Add system message if provided
        if system_message:
            self._messages.append(Message(role=Role.SYSTEM, content=system_message))

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return self._session_id

    @property
    def model(self) -> str:
        """Get the model ID."""
        return self._model

    @property
    def start_time(self) -> datetime:
        """Get the session start time."""
        return self._start_time

    @property
    def modified_time(self) -> datetime:
        """Get the last modified time."""
        return self._modified_time

    @property
    def messages(self) -> list[Message]:
        """Get the conversation history."""
        return self._messages.copy()

    def on(self, handler: SessionEventHandler) -> Callable[[], None]:
        """
        Subscribe to session events.

        Args:
            handler: Event handler function.

        Returns:
            Unsubscribe function.

        Example:
            >>> def on_event(event):
            ...     if event.type == EventType.ASSISTANT_MESSAGE:
            ...         print(event.data.content)
            ...
            >>> unsubscribe = session.on(on_event)
            >>> # Later: unsubscribe()
        """
        self._event_handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._event_handlers:
                self._event_handlers.remove(handler)

        return unsubscribe

    def _emit(self, event_type: EventType, data: Any) -> None:
        """Emit an event to all handlers."""
        event = SessionEvent(
            type=event_type,
            data=data,
            session_id=self._session_id,
        )
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.warning(f"Event handler error: {e}")

    async def send(self, options: MessageOptions) -> None:
        """
        Send a message to the model.

        This is an async method that sends the message and returns
        immediately. Use event handlers to receive the response.

        Args:
            options: Message options including prompt.

        Raises:
            SessionClosedError: If the session is closed.
        """
        if self._closed:
            raise SessionClosedError(self._session_id)

        prompt = options.get("prompt", "")
        context = options.get("context")

        # Build user message
        content = prompt
        if context:
            content = f"{context}\n\n{prompt}"

        user_message = Message(role=Role.USER, content=content)
        self._messages.append(user_message)
        self._modified_time = datetime.now(timezone.utc)

        # Get response
        try:
            if self._streaming:
                await self._stream_response()
            else:
                await self._get_response()
        except Exception as e:
            self._emit(EventType.SESSION_ERROR, {"error": str(e)})
            raise

    async def send_and_wait(self, options: MessageOptions) -> SessionEvent:
        """
        Send a message and wait for the complete response.

        This is a convenience method that sends a message and waits
        for the assistant's complete response.

        Args:
            options: Message options including prompt.

        Returns:
            The final assistant message event.

        Raises:
            SessionClosedError: If the session is closed.
        """
        response_event: SessionEvent | None = None
        done = asyncio.Event()

        def on_event(event: SessionEvent) -> None:
            nonlocal response_event
            if event.type == EventType.ASSISTANT_MESSAGE:
                response_event = event
                done.set()
            elif event.type == EventType.SESSION_IDLE:
                done.set()
            elif event.type == EventType.SESSION_ERROR:
                done.set()

        unsubscribe = self.on(on_event)

        try:
            await self.send(options)
            await done.wait()

            if response_event is None:
                raise RuntimeError("No response received")

            return response_event
        finally:
            unsubscribe()

    async def _stream_response(self) -> None:
        """Stream the response from the model."""
        full_content = ""
        full_reasoning = ""
        all_tool_calls: list[ToolCall] = []
        final_usage = None

        try:
            async for chunk in self._backend.complete_streaming(
                model=self._model,
                messages=self._messages,
                generation_config=self._generation_config,
                thinking_config=self._thinking_config,
                tools=self._tools if self._tools else None,
            ):
                # Emit delta events
                if chunk.content:
                    full_content += chunk.content
                    self._emit(
                        EventType.ASSISTANT_MESSAGE_DELTA,
                        {
                            "delta_content": chunk.content,
                            "content": full_content,
                        },
                    )

                if chunk.reasoning_content:
                    full_reasoning += chunk.reasoning_content
                    self._emit(
                        EventType.ASSISTANT_REASONING_DELTA,
                        {
                            "delta_content": chunk.reasoning_content,
                            "content": full_reasoning,
                        },
                    )

                if chunk.tool_calls:
                    all_tool_calls.extend(chunk.tool_calls)

                if chunk.usage:
                    final_usage = chunk.usage

            # Handle tool calls if any
            if all_tool_calls:
                await self._handle_tool_calls(all_tool_calls)

            # Emit final message
            assistant_message = Message(
                role=Role.ASSISTANT,
                content=full_content,
                tool_calls=all_tool_calls if all_tool_calls else None,
            )
            self._messages.append(assistant_message)

            if full_reasoning:
                self._emit(
                    EventType.ASSISTANT_REASONING,
                    {
                        "content": full_reasoning,
                    },
                )

            self._emit(
                EventType.ASSISTANT_MESSAGE,
                {
                    "content": full_content,
                    "tool_calls": all_tool_calls if all_tool_calls else None,
                    "usage": final_usage,
                },
            )

            self._emit(EventType.SESSION_IDLE, {})

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise

    async def _get_response(self) -> None:
        """Get a non-streaming response from the model."""
        try:
            chunk = await self._backend.complete(
                model=self._model,
                messages=self._messages,
                generation_config=self._generation_config,
                thinking_config=self._thinking_config,
                tools=self._tools if self._tools else None,
            )

            # Handle tool calls if any
            if chunk.tool_calls:
                await self._handle_tool_calls(chunk.tool_calls)

            # Add assistant message
            assistant_message = Message(
                role=Role.ASSISTANT,
                content=chunk.content,
                tool_calls=chunk.tool_calls,
            )
            self._messages.append(assistant_message)

            if chunk.reasoning_content:
                self._emit(
                    EventType.ASSISTANT_REASONING,
                    {
                        "content": chunk.reasoning_content,
                    },
                )

            self._emit(
                EventType.ASSISTANT_MESSAGE,
                {
                    "content": chunk.content,
                    "tool_calls": chunk.tool_calls,
                    "usage": chunk.usage,
                },
            )

            self._emit(EventType.SESSION_IDLE, {})

        except Exception as e:
            logger.error(f"Response error: {e}")
            raise

    async def _handle_tool_calls(self, tool_calls: list[ToolCall]) -> None:
        """Handle tool calls from the model."""
        for tool_call in tool_calls:
            tool_name = tool_call.function.name

            self._emit(
                EventType.TOOL_CALL,
                {
                    "name": tool_name,
                    "arguments": tool_call.function.arguments,
                    "call_id": tool_call.id,
                },
            )

            # Find and execute handler
            handler = self._tool_handlers.get(tool_name)
            if not handler:
                logger.warning(f"No handler for tool: {tool_name}")
                # Add error response to messages
                self._messages.append(
                    Message(
                        role=Role.USER,
                        content=f"Error: Tool '{tool_name}' not found",
                        tool_call_id=tool_call.id,
                        name=tool_name,
                    )
                )
                continue

            try:
                # Build invocation
                invocation: ToolInvocation = {
                    "name": tool_name,
                    "arguments": tool_call.function.arguments
                    if isinstance(tool_call.function.arguments, dict)
                    else {},
                    "call_id": tool_call.id,
                }

                # Execute handler
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(invocation)
                else:
                    result = handler(invocation)

                # Format result
                if isinstance(result, dict):
                    result_text = result.get("text_result_for_llm", str(result))
                else:
                    result_text = str(result)

                self._emit(
                    EventType.TOOL_RESULT,
                    {
                        "name": tool_name,
                        "call_id": tool_call.id,
                        "result": result_text,
                    },
                )

                # Add result to messages
                self._messages.append(
                    Message(
                        role=Role.USER,
                        content=result_text,
                        tool_call_id=tool_call.id,
                        name=tool_name,
                    )
                )

            except Exception as e:
                logger.error(f"Tool execution error for {tool_name}: {e}")
                error_msg = f"Error executing tool '{tool_name}': {e}"

                self._emit(
                    EventType.TOOL_RESULT,
                    {
                        "name": tool_name,
                        "call_id": tool_call.id,
                        "error": str(e),
                    },
                )

                self._messages.append(
                    Message(
                        role=Role.USER,
                        content=error_msg,
                        tool_call_id=tool_call.id,
                        name=tool_name,
                    )
                )

    def get_messages(self) -> list[Message]:
        """
        Get the conversation history.

        Returns:
            List of messages in the conversation.
        """
        return self._messages.copy()

    def add_tool(self, tool: Tool) -> None:
        """
        Add a tool to the session.

        Args:
            tool: The tool to add.
        """
        self._tools.append(tool)
        if tool.handler:
            self._tool_handlers[tool.name] = tool.handler

    def remove_tool(self, tool_name: str) -> None:
        """
        Remove a tool from the session.

        Args:
            tool_name: The name of the tool to remove.
        """
        self._tools = [t for t in self._tools if t.name != tool_name]
        self._tool_handlers.pop(tool_name, None)

    async def clear_history(self) -> None:
        """Clear the conversation history (except system message)."""
        if self._system_message:
            self._messages = [Message(role=Role.SYSTEM, content=self._system_message)]
        else:
            self._messages = []
        self._modified_time = datetime.now(timezone.utc)

    async def destroy(self) -> None:
        """
        Destroy the session and clean up resources.
        """
        self._closed = True
        self._event_handlers.clear()
        self._tool_handlers.clear()
        self._messages.clear()
        logger.debug(f"Session {self._session_id} destroyed")
