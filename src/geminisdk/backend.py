"""
Backend for Gemini CLI / Google Code Assist API.

Features:
- OAuth2 authentication with Google
- Streaming support with SSE
- Native tool calls support
- Token usage tracking
- Thinking/reasoning content support

Based on:
- Google Gemini CLI: https://github.com/google-gemini/gemini-cli
- Revibe's GeminicliBackend
- Better-Copilot-Chat's GeminiHandler
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from .auth import GeminiOAuthManager
from .exceptions import (
    APIError,
    OnboardingError,
    PermissionDeniedError,
    RateLimitError,
)
from .types import (
    HTTP_FORBIDDEN,
    HTTP_UNAUTHORIZED,
    FunctionCall,
    GenerationConfig,
    LLMChunk,
    LLMUsage,
    Message,
    Role,
    ThinkingConfig,
    Tool,
    ToolCall,
)

logger = logging.getLogger(__name__)

# Retryable status codes (401 and 403 for auth/scope issues)
RETRYABLE_STATUS_CODES = frozenset({HTTP_UNAUTHORIZED, HTTP_FORBIDDEN})
ONBOARD_MAX_RETRIES = 30
ONBOARD_SLEEP_SECONDS = 2

# Default headers
DEFAULT_USER_AGENT = "geminisdk/0.1.0"
DEFAULT_CLIENT_METADATA = {
    "ideType": "IDE_UNSPECIFIED",
    "platform": "PLATFORM_UNSPECIFIED",
    "pluginType": "GEMINI",
}


class GeminiBackend:
    """Backend for Gemini CLI / Google Code Assist API.

    This class handles all API communication including:
    - Authentication via OAuth
    - Sending messages and receiving responses
    - Streaming responses with SSE
    - Tool calling
    - Project/tier management

    Example:
        >>> async with GeminiBackend() as backend:
        ...     async for chunk in backend.complete_streaming(
        ...         model="gemini-2.5-pro",
        ...         messages=[Message(role=Role.USER, content="Hello!")],
        ...     ):
        ...         print(chunk.content, end="", flush=True)
    """

    def __init__(
        self,
        *,
        timeout: float = 720.0,
        oauth_path: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        """Initialize the Gemini backend.

        Args:
            timeout: Request timeout in seconds.
            oauth_path: Optional custom path to OAuth credentials.
            client_id: OAuth client ID. Uses official Gemini CLI client if not provided.
            client_secret: OAuth client secret. Uses official Gemini CLI secret if not provided.
        """
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._owns_client = True
        self._project_id: str | None = None

        # OAuth manager for authentication
        self._oauth_manager = GeminiOAuthManager(
            oauth_path, client_id=client_id, client_secret=client_secret
        )

    async def __aenter__(self) -> GeminiBackend:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
            self._owns_client = True
        return self._client

    async def _get_auth_headers(self, force_refresh: bool = False) -> dict[str, str]:
        """Get authentication headers.

        Args:
            force_refresh: If True, forces a token refresh for OAuth.

        Returns:
            Headers dict with OAuth token.
        """
        headers = {"Content-Type": "application/json"}

        access_token = await self._oauth_manager.ensure_authenticated(force_refresh=force_refresh)
        headers["Authorization"] = f"Bearer {access_token}"

        return headers

    def _prepare_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert Messages to Gemini Code Assist format.

        Based on gemini-cli converter.ts - uses role "user" or "model" only.
        """
        result: list[dict[str, Any]] = []

        for msg in messages:
            # Gemini Code Assist uses "user" and "model" roles
            role = "model" if msg.role == Role.ASSISTANT else "user"
            content_parts: list[dict[str, Any]] = []

            if msg.content:
                if isinstance(msg.content, str):
                    content_parts.append({"text": msg.content})
                else:
                    # Handle content parts (text, images)
                    for part in msg.content:
                        if part.text:
                            content_parts.append({"text": part.text})
                        elif part.image_data and part.image_mime_type:
                            content_parts.append(
                                {
                                    "inlineData": {
                                        "mimeType": part.image_mime_type,
                                        "data": part.image_data.decode()
                                        if isinstance(part.image_data, bytes)
                                        else part.image_data,
                                    }
                                }
                            )

            if msg.tool_calls:
                # Add tool calls as function calls
                for tc in msg.tool_calls:
                    args = tc.function.arguments
                    if args is not None and not isinstance(args, str):
                        args = json.dumps(args)
                    content_parts.append(
                        {
                            "functionCall": {
                                "name": tc.function.name,
                                "args": json.loads(args) if isinstance(args, str) else args,
                            }
                        }
                    )

            if msg.tool_call_id:
                # This is a tool response
                content_parts.append(
                    {
                        "functionResponse": {
                            "name": msg.name or "",
                            "response": {"result": msg.content}
                            if isinstance(msg.content, str)
                            else msg.content,
                        }
                    }
                )

            if content_parts:
                result.append({"role": role, "parts": content_parts})

        return result

    def _prepare_tools(self, tools: list[Tool] | None) -> list[dict[str, Any]] | None:
        """Convert tools to Gemini Code Assist function declarations format.

        The API expects: [{ functionDeclarations: [...] }]
        """
        if not tools:
            return None

        func_decls: list[dict[str, Any]] = []

        for tool in tools:
            func_def: dict[str, Any] = {
                "name": tool.name,
                "description": tool.description or "",
            }

            if tool.parameters:
                params = tool.parameters
                func_def["parameters"] = {
                    "type": "object",
                    "properties": params.get("properties", {}),
                    "required": params.get("required", []),
                }

            func_decls.append(func_def)

        return [{"functionDeclarations": func_decls}]

    def _parse_tool_calls(self, parts: list[dict[str, Any]]) -> list[ToolCall] | None:
        """Parse tool calls from response parts."""
        tool_calls: list[ToolCall] = []

        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    ToolCall(
                        id=str(uuid.uuid4()),
                        type="function",
                        function=FunctionCall(
                            name=fc.get("name", ""),
                            arguments=fc.get("args", {}),
                        ),
                    )
                )

        return tool_calls if tool_calls else None

    def _build_auth_headers(self, access_token: str) -> dict[str, str]:
        """Build authorization headers."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_client_metadata(env_project_id: str | None) -> dict[str, str | None]:
        """Build client metadata for API requests."""
        return {
            "ideType": "IDE_UNSPECIFIED",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI",
            "duetProject": env_project_id,
        }

    @staticmethod
    def _build_load_request(
        env_project_id: str | None, client_metadata: dict[str, str | None]
    ) -> dict[str, Any]:
        """Build the loadCodeAssist request."""
        return {
            "cloudaicompanionProject": env_project_id,
            "metadata": client_metadata,
        }

    async def _post_load_code_assist(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        load_request: dict[str, Any],
    ) -> dict[str, Any]:
        """Post a loadCodeAssist request to get project/tier info."""
        url = f"{self._oauth_manager.get_api_endpoint()}:loadCodeAssist"

        response = await client.post(
            url,
            headers=headers,
            json=load_request,
        )
        response.raise_for_status()
        return response.json()

    def _project_from_loaded_tier(
        self, data: dict[str, Any], env_project_id: str | None
    ) -> str | None:
        """Extract project ID from loadCodeAssist response."""
        if not data.get("currentTier"):
            return None

        project_from_api = data.get("cloudaicompanionProject")
        if project_from_api:
            self._project_id = project_from_api
            return project_from_api

        if env_project_id:
            self._project_id = env_project_id
            return env_project_id

        return ""

    @staticmethod
    def _select_default_tier(data: dict[str, Any]) -> str:
        """Select the default tier from available tiers."""
        for tier in data.get("allowedTiers", []):
            if tier.get("isDefault"):
                return tier.get("id", "free-tier")
        return "free-tier"

    @staticmethod
    def _build_onboard_request(
        tier_id: str,
        env_project_id: str | None,
        client_metadata: dict[str, str | None],
    ) -> dict[str, Any]:
        """Build the onboardCodeAssist request."""
        if tier_id == "free-tier":
            return {
                "tierId": tier_id,
                "cloudaicompanionProject": None,
                "metadata": client_metadata,
            }
        return {
            "tierId": tier_id,
            "cloudaicompanionProject": env_project_id,
            "metadata": {**client_metadata, "duetProject": env_project_id},
        }

    async def _post_onboard_request(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        onboard_request: dict[str, Any],
    ) -> dict[str, Any]:
        """Post an onboardCodeAssist request."""
        url = f"{self._oauth_manager.get_api_endpoint()}:onboardUser"

        response = await client.post(
            url,
            headers=headers,
            json=onboard_request,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_project_from_lro(lro_data: dict[str, Any]) -> str | None:
        """Extract project ID from LRO response."""
        if not lro_data.get("done"):
            return None
        response_data = lro_data.get("response", {})
        cloud_ai_companion = response_data.get("cloudaicompanionProject", {})
        if isinstance(cloud_ai_companion, dict):
            return cloud_ai_companion.get("id")
        return None

    async def _onboard_for_project(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        env_project_id: str | None,
        client_metadata: dict[str, str | None],
        tier_id: str,
    ) -> str:
        """Onboard to get a project ID."""
        onboard_request = self._build_onboard_request(tier_id, env_project_id, client_metadata)

        for _ in range(ONBOARD_MAX_RETRIES):
            lro_data = await self._post_onboard_request(client, headers, onboard_request)
            project_id = self._extract_project_from_lro(lro_data)

            if project_id:
                self._project_id = project_id
                return project_id

            if lro_data.get("done"):
                break

            await asyncio.sleep(ONBOARD_SLEEP_SECONDS)

        if tier_id == "free-tier":
            return ""

        raise OnboardingError(tier_id=tier_id)

    async def _ensure_project_id(self, access_token: str) -> str:
        """Ensure we have a valid project ID.

        Matches gemini-cli behavior:
        1. First checks GOOGLE_CLOUD_PROJECT env var
        2. Falls back to loadCodeAssist API to determine project/tier
        3. For FREE tier, no project ID is required
        """
        if self._project_id:
            return self._project_id

        env_project_id = self._oauth_manager.get_project_id()
        headers = self._build_auth_headers(access_token)
        client = self._get_client()
        client_metadata = self._build_client_metadata(env_project_id)
        load_request = self._build_load_request(env_project_id, client_metadata)

        try:
            data = await self._post_load_code_assist(client, headers, load_request)
            project_id = self._project_from_loaded_tier(data, env_project_id)

            if project_id is not None:
                self._project_id = project_id
                return project_id

            tier_id = self._select_default_tier(data)
            return await self._onboard_for_project(
                client, headers, env_project_id, client_metadata, tier_id
            )

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                if error_data.get("projectValidationError"):
                    error_detail = error_data["projectValidationError"].get("message", "")
                elif error_data.get("error", {}).get("message"):
                    error_detail = error_data["error"]["message"]
            except Exception:
                error_detail = e.response.text[:200] if e.response.text else ""

            raise APIError(
                f"Gemini Code Assist access denied: {error_detail}",
                status_code=e.response.status_code,
                response_body=e.response.text,
            ) from e

    def _build_request_payload(
        self,
        model: str,
        messages: list[Message],
        generation_config: GenerationConfig | None = None,
        thinking_config: ThinkingConfig | None = None,
        tools: list[Tool] | None = None,
        project_id: str = "",
        user_prompt_id: str = "",
    ) -> dict[str, Any]:
        """Build the request payload for the Gemini API."""
        gen_config = generation_config or GenerationConfig()

        # Build generation config with camelCase keys
        generation_cfg: dict[str, Any] = {
            "temperature": gen_config.temperature,
        }

        if gen_config.max_output_tokens:
            generation_cfg["maxOutputTokens"] = gen_config.max_output_tokens
        if gen_config.top_p is not None:
            generation_cfg["topP"] = gen_config.top_p
        if gen_config.top_k is not None:
            generation_cfg["topK"] = gen_config.top_k
        if gen_config.stop_sequences:
            generation_cfg["stopSequences"] = gen_config.stop_sequences

        # Add thinking config if provided
        if thinking_config and thinking_config.include_thoughts:
            generation_cfg["thinkingConfig"] = {
                "includeThoughts": thinking_config.include_thoughts,
            }
            if thinking_config.thinking_budget:
                generation_cfg["thinkingConfig"]["thinkingBudget"] = thinking_config.thinking_budget

        # Build request body - Code Assist API format
        request_body: dict[str, Any] = {
            "contents": self._prepare_messages(messages),
            "generationConfig": generation_cfg,
        }

        # Add tools if provided
        if tools:
            request_body["tools"] = self._prepare_tools(tools)

        # Build the full payload with project info
        payload: dict[str, Any] = {
            "model": model,
            "request": request_body,
        }

        # Only include project if it's not empty (free tier doesn't require project)
        if project_id:
            payload["project"] = project_id

        if user_prompt_id:
            payload["user_prompt_id"] = user_prompt_id

        return payload

    async def _build_headers(
        self, extra_headers: dict[str, str] | None, retry_count: int
    ) -> dict[str, str]:
        """Build request headers."""
        headers = await self._get_auth_headers(force_refresh=retry_count > 0)
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def _build_payload_with_project(
        self,
        *,
        model: str,
        messages: list[Message],
        generation_config: GenerationConfig | None,
        thinking_config: ThinkingConfig | None,
        tools: list[Tool] | None,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Build payload with project ID."""
        access_token = headers["Authorization"].replace("Bearer ", "")
        project_id = await self._ensure_project_id(access_token)
        return self._build_request_payload(
            model, messages, generation_config, thinking_config, tools, project_id
        )

    def _parse_sse_line(self, line: str) -> tuple[str, str] | None:
        """Parse an SSE line and return (key, value) if valid."""
        if not line or line.startswith(":"):
            return None

        if ":" in line:
            key, value = line.split(":", 1)
            return key.strip(), value.strip()

        return None

    def _extract_completion_parts(
        self, parts: list[dict[str, Any]]
    ) -> tuple[str, str | None, list[ToolCall] | None]:
        """Extract content, reasoning, and tool calls from response parts."""
        text_content = ""
        reasoning_content: str | None = None
        tool_calls: list[ToolCall] | None = None

        for part in parts:
            if "text" in part:
                text = part["text"]
                text_content += text
            elif "thought" in part:
                reasoning_content = part.get("thought")

            if "functionCall" in part:
                fc = part["functionCall"]
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(
                    ToolCall(
                        id=str(uuid.uuid4()),
                        type="function",
                        function=FunctionCall(
                            name=fc.get("name", ""),
                            arguments=fc.get("args") or fc.get("arguments", {}),
                        ),
                    )
                )

        return text_content, reasoning_content, tool_calls

    def _parse_completion_response(self, data: dict[str, Any]) -> LLMChunk:
        """Parse a completion response."""
        # Handle both wrapped "response" and direct candidates format
        response_data = data.get("response", data) if "response" in data else data
        candidates = response_data.get("candidates", [])

        if not candidates:
            # Return empty chunk if no candidates
            return LLMChunk()

        candidate = candidates[0]
        content_obj = candidate.get("content", {})
        parts = content_obj.get("parts", [])

        content, reasoning, tool_calls = self._extract_completion_parts(parts)

        # Get usage info
        usage_data = data.get("usageMetadata", response_data.get("usageMetadata", {}))
        usage = None
        if usage_data:
            usage = LLMUsage(
                prompt_tokens=usage_data.get("promptTokenCount", 0),
                completion_tokens=usage_data.get("candidatesTokenCount", 0),
                total_tokens=usage_data.get("totalTokenCount", 0),
            )

        return LLMChunk(
            content=content,
            reasoning_content=reasoning,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=candidate.get("finishReason"),
        )

    async def _stream_sse_response(
        self, response: httpx.Response
    ) -> AsyncGenerator[LLMChunk, None]:
        """Stream SSE response and yield chunks."""
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            await self._handle_non_streaming_response(response)
            return

        sse_data_parts: list[str] = []

        async for line in response.aiter_lines():
            line = line.strip()

            if not line:
                if sse_data_parts:
                    event_data = "\n".join(sse_data_parts).strip()
                    sse_data_parts = []

                    if not event_data or event_data == "[DONE]":
                        continue

                    chunk_data = self._parse_chunk_data(event_data)
                    if chunk_data is None:
                        continue

                    self._handle_chunk_error(chunk_data)
                    yield self._parse_completion_response(chunk_data)
                continue

            parsed = self._parse_sse_line(line)
            if not parsed:
                continue

            key, value = parsed

            if key == "data":
                if value.strip() == "[DONE]":
                    break
                if value:
                    sse_data_parts.append(value.lstrip())

        if sse_data_parts:
            event_data = "\n".join(sse_data_parts).strip()
            if event_data and event_data != "[DONE]":
                chunk_data = self._parse_chunk_data(event_data)
                if chunk_data is not None:
                    self._handle_chunk_error(chunk_data)
                    yield self._parse_completion_response(chunk_data)

    async def _handle_non_streaming_response(self, response: httpx.Response) -> None:
        """Handle non-streaming response, raising appropriate errors."""
        body = await response.aread()
        body_text = body.decode("utf-8")
        if not body_text:
            return
        try:
            error_data = json.loads(body_text)
            error_msg = (
                error_data.get("error", {}).get("message")
                or error_data.get("message")
                or error_data.get("detail")
                or str(error_data)
            )
            raise APIError(error_msg, status_code=response.status_code, response_body=body_text)
        except json.JSONDecodeError as exc:
            raise APIError(
                f"Unexpected API response: {body_text[:200]}",
                status_code=response.status_code,
                response_body=body_text,
            ) from exc

    def _parse_chunk_data(self, value: str) -> dict[str, Any] | None:
        """Parse chunk data from SSE value, returning None on JSON error."""
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.debug("Failed to parse chunk data JSON.")
            return None

    def _handle_chunk_error(self, chunk_data: dict[str, Any]) -> None:
        """Handle error in chunk data."""
        error_info = chunk_data.get("error") or chunk_data.get("error", {})
        error_msg = error_info.get("message") if isinstance(error_info, dict) else str(error_info)
        if error_msg:
            raise APIError(error_msg, status_code=500)

    async def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        generation_config: GenerationConfig | None = None,
        thinking_config: ThinkingConfig | None = None,
        tools: list[Tool] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> LLMChunk:
        """Send a completion request (non-streaming).

        Args:
            model: The model ID to use.
            messages: List of messages in the conversation.
            generation_config: Optional generation configuration.
            thinking_config: Optional thinking/reasoning configuration.
            tools: Optional list of tools available to the model.
            extra_headers: Optional extra headers to include.

        Returns:
            The completion response.
        """
        return await self._complete_with_retry(
            model=model,
            messages=messages,
            generation_config=generation_config,
            thinking_config=thinking_config,
            tools=tools,
            extra_headers=extra_headers,
        )

    async def _complete_with_retry(
        self,
        *,
        model: str,
        messages: list[Message],
        generation_config: GenerationConfig | None = None,
        thinking_config: ThinkingConfig | None = None,
        tools: list[Tool] | None = None,
        extra_headers: dict[str, str] | None = None,
        _retry_count: int = 0,
    ) -> LLMChunk:
        """Internal complete method with retry logic for auth failures."""
        headers = await self._build_headers(extra_headers, _retry_count)
        url = f"{self._oauth_manager.get_api_endpoint()}:generateContent"

        payload = await self._build_payload_with_project(
            model=model,
            messages=messages,
            generation_config=generation_config,
            thinking_config=thinking_config,
            tools=tools,
            headers=headers,
        )

        try:
            client = self._get_client()
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return self._parse_completion_response(data)

        except httpx.HTTPStatusError as e:
            # Retry once with fresh token on 401/403
            if e.response.status_code in RETRYABLE_STATUS_CODES and _retry_count == 0:
                self._oauth_manager.invalidate_credentials()
                return await self._complete_with_retry(
                    model=model,
                    messages=messages,
                    generation_config=generation_config,
                    thinking_config=thinking_config,
                    tools=tools,
                    extra_headers=extra_headers,
                    _retry_count=1,
                )

            self._handle_http_error(e)
            raise  # Should not reach here

    async def complete_streaming(
        self,
        *,
        model: str,
        messages: list[Message],
        generation_config: GenerationConfig | None = None,
        thinking_config: ThinkingConfig | None = None,
        tools: list[Tool] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        """Send a streaming completion request.

        Args:
            model: The model ID to use.
            messages: List of messages in the conversation.
            generation_config: Optional generation configuration.
            thinking_config: Optional thinking/reasoning configuration.
            tools: Optional list of tools available to the model.
            extra_headers: Optional extra headers to include.

        Yields:
            Chunks of the completion response.
        """
        async for chunk in self._complete_streaming_with_retry(
            model=model,
            messages=messages,
            generation_config=generation_config,
            thinking_config=thinking_config,
            tools=tools,
            extra_headers=extra_headers,
        ):
            yield chunk

    async def _complete_streaming_with_retry(
        self,
        *,
        model: str,
        messages: list[Message],
        generation_config: GenerationConfig | None = None,
        thinking_config: ThinkingConfig | None = None,
        tools: list[Tool] | None = None,
        extra_headers: dict[str, str] | None = None,
        _retry_count: int = 0,
    ) -> AsyncGenerator[LLMChunk, None]:
        """Internal streaming method with retry logic."""
        headers = await self._build_headers(extra_headers, _retry_count)
        url = f"{self._oauth_manager.get_api_endpoint()}:streamGenerateContent"

        payload = await self._build_payload_with_project(
            model=model,
            messages=messages,
            generation_config=generation_config,
            thinking_config=thinking_config,
            tools=tools,
            headers=headers,
        )

        logger.debug(f"Streaming URL: {url}")
        logger.debug(f"Streaming payload: {json.dumps(payload, indent=2)}")

        try:
            client = self._get_client()
            async with client.stream(
                method="POST",
                url=url,
                headers=headers,
                json=payload,
                params={"alt": "sse"},
            ) as response:
                if response.status_code in RETRYABLE_STATUS_CODES and _retry_count == 0:
                    self._oauth_manager.invalidate_credentials()
                    # Need to break out and retry
                    raise httpx.HTTPStatusError(
                        f"Auth error: {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                response.raise_for_status()

                async for chunk in self._stream_sse_response(response):
                    yield chunk

        except httpx.HTTPStatusError as e:
            if e.response.status_code in RETRYABLE_STATUS_CODES and _retry_count == 0:
                self._oauth_manager.invalidate_credentials()
                async for chunk in self._complete_streaming_with_retry(
                    model=model,
                    messages=messages,
                    generation_config=generation_config,
                    thinking_config=thinking_config,
                    tools=tools,
                    extra_headers=extra_headers,
                    _retry_count=1,
                ):
                    yield chunk
                return

            self._handle_http_error(e)

    def _handle_http_error(self, e: httpx.HTTPStatusError) -> None:
        """Handle HTTP errors and raise appropriate exceptions."""
        status = e.response.status_code
        body = e.response.text

        # Try to parse error message
        error_msg = body
        try:
            error_data = e.response.json()
            if "error" in error_data:
                error_msg = error_data["error"].get("message", body)
        except Exception:
            pass

        if status == 429:
            raise RateLimitError(
                message=f"Rate limit exceeded: {error_msg}",
                response_body=body,
            )
        elif status == 403:
            raise PermissionDeniedError(
                message=f"Permission denied: {error_msg}",
                response_body=body,
            )
        else:
            raise APIError(
                message=f"API error: {error_msg}",
                status_code=status,
                response_body=body,
            )

    async def list_models(self) -> list[str]:
        """List available models.

        Returns:
            List of available model IDs.
        """
        from .types import GEMINI_CLI_MODELS

        return list(GEMINI_CLI_MODELS.keys())

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._owns_client and self._client:
            await self._client.aclose()
            self._client = None
