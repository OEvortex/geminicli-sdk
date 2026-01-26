"""
OAuth authentication for Gemini CLI / Code Assist API.

Based on:
- Google Gemini CLI: https://github.com/google-gemini/gemini-cli
- KiloCode's Gemini CLI provider
- Revibe's GeminiOAuthManager

This module handles OAuth2 token management for Gemini Code Assist API access.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

from .exceptions import (
    AuthenticationError,
    CredentialsNotFoundError,
    TokenRefreshError,
)
from .types import (
    GEMINI_CODE_ASSIST_API_VERSION,
    GEMINI_CODE_ASSIST_ENDPOINT,
    GEMINI_OAUTH_AUTH_ENDPOINT,
    GEMINI_OAUTH_CLIENT_ID,
    GEMINI_OAUTH_CLIENT_SECRET,
    GEMINI_OAUTH_REDIRECT_URI,
    GEMINI_OAUTH_SCOPES,
    GEMINI_OAUTH_TOKEN_ENDPOINT,
    HTTP_OK,
    TOKEN_REFRESH_BUFFER_MS,
    GeminiOAuthCredentials,
    get_geminicli_credential_path,
    get_geminicli_env_path,
)

logger = logging.getLogger(__name__)


class GeminiOAuthManager:
    """Manages OAuth authentication for Gemini CLI / Code Assist API.

    This class handles:
    - Loading cached OAuth credentials from disk
    - Refreshing access tokens when they expire
    - Providing valid access tokens for API requests

    The credentials are expected to be in the format stored by the official
    Gemini CLI after running `gemini auth login`.

    Example:
        >>> oauth = GeminiOAuthManager()
        >>> token = await oauth.ensure_authenticated()
        >>> # Use token for API requests
    """

    def __init__(
        self,
        oauth_path: str | None = None,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        """Initialize the OAuth manager.

        Args:
            oauth_path: Optional custom path to the OAuth credentials file.
            client_id: OAuth client ID. Uses official Gemini CLI client if not provided.
            client_secret: OAuth client secret. Uses official Gemini CLI secret if not provided.
        """
        self._oauth_path = oauth_path
        self._client_id = client_id or GEMINI_OAUTH_CLIENT_ID
        self._client_secret = client_secret or GEMINI_OAUTH_CLIENT_SECRET
        self._credentials: GeminiOAuthCredentials | None = None
        self._refresh_lock = asyncio.Lock()
        self._project_id: str | None = None

    def _get_credential_path(self) -> str:
        """Get the path to the credentials file."""
        return get_geminicli_credential_path(self._oauth_path)

    def _load_cached_credentials(self) -> GeminiOAuthCredentials:
        """Load OAuth credentials from the cached file.

        Returns:
            The loaded credentials.

        Raises:
            CredentialsNotFoundError: If the credentials file doesn't exist.
            AuthenticationError: If the credentials file is invalid.
        """
        key_file = self._get_credential_path()

        try:
            with open(key_file, encoding="utf-8") as f:
                data = json.load(f)

            return GeminiOAuthCredentials(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                token_type=data.get("token_type", "Bearer"),
                expiry_date=data.get("expiry_date", 0),
            )
        except FileNotFoundError:
            raise CredentialsNotFoundError(key_file) from None
        except (json.JSONDecodeError, KeyError) as e:
            raise AuthenticationError(
                f"Invalid Gemini OAuth credentials file at {key_file}: {e}"
            ) from e

    def _save_credentials(self, credentials: GeminiOAuthCredentials) -> None:
        """Save credentials to the cache file.

        Args:
            credentials: The credentials to save.
        """
        key_file = self._get_credential_path()

        # Ensure directory exists
        Path(key_file).parent.mkdir(parents=True, exist_ok=True)

        data = {
            "access_token": credentials.access_token,
            "refresh_token": credentials.refresh_token,
            "token_type": credentials.token_type,
            "expiry_date": credentials.expiry_date,
        }

        with open(key_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def _refresh_access_token(
        self,
        credentials: GeminiOAuthCredentials,
    ) -> GeminiOAuthCredentials:
        """Refresh the OAuth access token.

        Args:
            credentials: Current credentials with refresh token.

        Returns:
            New credentials with refreshed access token.

        Raises:
            TokenRefreshError: If the token refresh fails.
        """
        async with self._refresh_lock:
            # Check if another coroutine already refreshed while waiting
            if self._credentials and self._is_token_valid(self._credentials):
                return self._credentials

            if not credentials.refresh_token:
                raise TokenRefreshError("No refresh token available in credentials.")

            body_data = {
                "grant_type": "refresh_token",
                "refresh_token": credentials.refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": " ".join(GEMINI_OAUTH_SCOPES),
            }

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        GEMINI_OAUTH_TOKEN_ENDPOINT,
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Accept": "application/json",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        },
                        content=urlencode(body_data),
                    )

                    if response.status_code != HTTP_OK:
                        raise TokenRefreshError(
                            f"Token refresh failed: {response.status_code} {response.reason_phrase}",
                            status_code=response.status_code,
                            response_body=response.text,
                        )

                    try:
                        token_data = response.json()
                    except json.JSONDecodeError as e:
                        raise TokenRefreshError(
                            f"Invalid JSON response from OAuth endpoint: {response.text[:200]}"
                        ) from e

                    if token_data.get("error"):
                        raise TokenRefreshError(
                            f"Token refresh failed: {token_data['error']} - "
                            f"{token_data.get('error_description', 'Unknown error')}"
                        )

                    new_credentials = GeminiOAuthCredentials(
                        access_token=token_data["access_token"],
                        token_type=token_data.get("token_type", "Bearer"),
                        refresh_token=token_data.get("refresh_token", credentials.refresh_token),
                        expiry_date=int(time.time() * 1000)
                        + token_data.get("expires_in", 3600) * 1000,
                    )

                    # Save refreshed credentials
                    self._save_credentials(new_credentials)
                    self._credentials = new_credentials

                    logger.debug("Successfully refreshed Gemini OAuth token")
                    return new_credentials

            except httpx.RequestError as e:
                raise TokenRefreshError(f"Network error during token refresh: {e}") from e

    def _is_token_valid(self, credentials: GeminiOAuthCredentials) -> bool:
        """Check if the access token is still valid.

        Args:
            credentials: The credentials to check.

        Returns:
            True if the token is still valid (with buffer), False otherwise.
        """
        if not credentials.expiry_date:
            return False

        current_time_ms = int(time.time() * 1000)
        return current_time_ms < credentials.expiry_date - TOKEN_REFRESH_BUFFER_MS

    def invalidate_credentials(self) -> None:
        """Invalidate cached credentials to force a refresh on next request.

        Call this when receiving authentication errors (401) from the API.
        """
        self._credentials = None
        logger.debug("Invalidated cached Gemini credentials")

    async def ensure_authenticated(self, force_refresh: bool = False) -> str:
        """Ensure we have a valid access token.

        Args:
            force_refresh: If True, forces a token refresh even if current token is valid.

        Returns:
            A valid access token.

        Raises:
            CredentialsNotFoundError: If credentials file doesn't exist.
            TokenRefreshError: If token refresh fails.
        """
        # Load credentials if not cached
        if self._credentials is None:
            self._credentials = self._load_cached_credentials()

        # Refresh if needed or forced
        if force_refresh or not self._is_token_valid(self._credentials):
            self._credentials = await self._refresh_access_token(self._credentials)

        return self._credentials.access_token

    async def get_credentials(self) -> GeminiOAuthCredentials:
        """Get the current credentials, refreshing if needed.

        Returns:
            Valid credentials.
        """
        await self.ensure_authenticated()
        assert self._credentials is not None
        return self._credentials

    def get_api_endpoint(self) -> str:
        """Get the Code Assist API endpoint.

        Returns:
            The API endpoint URL.
        """
        return f"{GEMINI_CODE_ASSIST_ENDPOINT}/{GEMINI_CODE_ASSIST_API_VERSION}"

    def get_project_id(self) -> str | None:
        """Get the project ID from environment.

        Returns:
            The project ID if set, None otherwise.
        """
        # Check environment variable first
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if project_id:
            return project_id

        # Check .env file
        env_file = get_geminicli_env_path(
            os.path.dirname(self._get_credential_path()) if self._oauth_path else None
        )

        if os.path.exists(env_file):
            try:
                with open(env_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GOOGLE_CLOUD_PROJECT="):
                            return line.split("=", 1)[1].strip().strip("\"'")
            except Exception:
                pass

        return self._project_id

    def set_project_id(self, project_id: str) -> None:
        """Set the project ID.

        Args:
            project_id: The project ID to set.
        """
        self._project_id = project_id

    def generate_auth_url(self, state: str, code_verifier: str | None = None) -> str:
        """Generate the OAuth authorization URL.

        This is used for the initial OAuth flow when credentials don't exist.

        Args:
            state: Random state string for CSRF protection.
            code_verifier: Optional PKCE code verifier.

        Returns:
            The authorization URL to visit for OAuth consent.
        """
        params: dict[str, str] = {
            "client_id": self._client_id,
            "redirect_uri": GEMINI_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(GEMINI_OAUTH_SCOPES),
            "access_type": "offline",
            "state": state,
        }

        if code_verifier:
            # PKCE support
            import base64
            import hashlib

            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"

        return f"{GEMINI_OAUTH_AUTH_ENDPOINT}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        code_verifier: str | None = None,
    ) -> GeminiOAuthCredentials:
        """Exchange an authorization code for tokens.

        Args:
            code: The authorization code from the OAuth callback.
            code_verifier: The PKCE code verifier if used.

        Returns:
            The new OAuth credentials.

        Raises:
            AuthenticationError: If the exchange fails.
        """
        body_data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": GEMINI_OAUTH_REDIRECT_URI,
        }

        if code_verifier:
            body_data["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            response = await client.post(
                GEMINI_OAUTH_TOKEN_ENDPOINT,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                content=urlencode(body_data),
            )

            if response.status_code != HTTP_OK:
                raise AuthenticationError(
                    f"Code exchange failed: {response.status_code} - {response.text}"
                )

            token_data = response.json()

            if token_data.get("error"):
                raise AuthenticationError(
                    f"Code exchange failed: {token_data['error']} - "
                    f"{token_data.get('error_description', 'Unknown error')}"
                )

            credentials = GeminiOAuthCredentials(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expiry_date=int(time.time() * 1000) + token_data.get("expires_in", 3600) * 1000,
            )

            # Save credentials
            self._save_credentials(credentials)
            self._credentials = credentials

            return credentials
