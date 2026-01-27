/**
 * OAuth authentication for Gemini CLI / Code Assist API.
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  AuthenticationError,
  CredentialsNotFoundError,
  TokenRefreshError,
} from './exceptions.js';
import {
  GeminiOAuthCredentials,
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
  getGeminiCliCredentialPath,
  getGeminiCliEnvPath,
} from './types.js';

export class GeminiOAuthManager {
  private oauthPath?: string;
  private clientId: string;
  private clientSecret: string;
  private credentials: GeminiOAuthCredentials | null = null;
  private refreshLock: Promise<GeminiOAuthCredentials> | null = null;
  private projectId: string | null = null;

  constructor(
    oauthPath?: string,
    clientId?: string,
    clientSecret?: string
  ) {
    this.oauthPath = oauthPath;
    this.clientId = clientId ?? GEMINI_OAUTH_CLIENT_ID;
    this.clientSecret = clientSecret ?? GEMINI_OAUTH_CLIENT_SECRET;
  }

  private getCredentialPath(): string {
    return getGeminiCliCredentialPath(this.oauthPath);
  }

  private loadCachedCredentials(): GeminiOAuthCredentials {
    const keyFile = this.getCredentialPath();

    try {
      const data = JSON.parse(fs.readFileSync(keyFile, 'utf-8')) as Record<string, unknown>;

      return {
        accessToken: data['access_token'] as string,
        refreshToken: data['refresh_token'] as string,
        tokenType: (data['token_type'] as string) ?? 'Bearer',
        expiryDate: (data['expiry_date'] as number) ?? 0,
      };
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
        throw new CredentialsNotFoundError(keyFile);
      }
      throw new AuthenticationError(
        `Invalid Gemini OAuth credentials file at ${keyFile}: ${error}`
      );
    }
  }

  private saveCredentials(credentials: GeminiOAuthCredentials): void {
    const keyFile = this.getCredentialPath();
    const dir = path.dirname(keyFile);

    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const data = {
      access_token: credentials.accessToken,
      refresh_token: credentials.refreshToken,
      token_type: credentials.tokenType,
      expiry_date: credentials.expiryDate,
    };

    fs.writeFileSync(keyFile, JSON.stringify(data, null, 2), 'utf-8');
  }

  private async refreshAccessToken(
    credentials: GeminiOAuthCredentials
  ): Promise<GeminiOAuthCredentials> {
    // Check if refresh is already in progress
    if (this.refreshLock) {
      return this.refreshLock;
    }

    this.refreshLock = this.doRefresh(credentials);
    try {
      return await this.refreshLock;
    } finally {
      this.refreshLock = null;
    }
  }

  private async doRefresh(
    credentials: GeminiOAuthCredentials
  ): Promise<GeminiOAuthCredentials> {
    if (!credentials.refreshToken) {
      throw new TokenRefreshError('No refresh token available in credentials.');
    }

    const bodyData = new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: credentials.refreshToken,
      client_id: this.clientId,
      client_secret: this.clientSecret,
      scope: GEMINI_OAUTH_SCOPES.join(' '),
    });

    const response = await fetch(GEMINI_OAUTH_TOKEN_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        Accept: 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
      body: bodyData.toString(),
    });

    if (response.status !== HTTP_OK) {
      throw new TokenRefreshError(
        `Token refresh failed: ${response.status} ${response.statusText}`,
        response.status,
        await response.text()
      );
    }

    const tokenData = (await response.json()) as Record<string, unknown>;

    if (tokenData['error']) {
      throw new TokenRefreshError(
        `Token refresh failed: ${tokenData['error']} - ${tokenData['error_description'] ?? 'Unknown error'}`
      );
    }

    const newCredentials: GeminiOAuthCredentials = {
      accessToken: tokenData['access_token'] as string,
      tokenType: (tokenData['token_type'] as string) ?? 'Bearer',
      refreshToken: (tokenData['refresh_token'] as string) ?? credentials.refreshToken,
      expiryDate:
        Date.now() + ((tokenData['expires_in'] as number) ?? 3600) * 1000,
    };

    this.saveCredentials(newCredentials);
    this.credentials = newCredentials;

    return newCredentials;
  }

  private isTokenValid(credentials: GeminiOAuthCredentials): boolean {
    if (!credentials.expiryDate) return false;
    return Date.now() < credentials.expiryDate - TOKEN_REFRESH_BUFFER_MS;
  }

  public invalidateCredentials(): void {
    this.credentials = null;
  }

  public async ensureAuthenticated(forceRefresh = false): Promise<string> {
    if (this.credentials === null) {
      this.credentials = this.loadCachedCredentials();
    }

    if (forceRefresh || !this.isTokenValid(this.credentials)) {
      this.credentials = await this.refreshAccessToken(this.credentials);
    }

    return this.credentials.accessToken;
  }

  public async getCredentials(): Promise<GeminiOAuthCredentials> {
    await this.ensureAuthenticated();
    return this.credentials!;
  }

  public getApiEndpoint(): string {
    return `${GEMINI_CODE_ASSIST_ENDPOINT}/${GEMINI_CODE_ASSIST_API_VERSION}`;
  }

  public getProjectId(): string | null {
    const envProjectId = process.env['GOOGLE_CLOUD_PROJECT'];
    if (envProjectId) return envProjectId;

    const envFile = getGeminiCliEnvPath(
      this.oauthPath ? path.dirname(this.getCredentialPath()) : undefined
    );

    if (fs.existsSync(envFile)) {
      try {
        const content = fs.readFileSync(envFile, 'utf-8');
        for (const line of content.split('\n')) {
          const trimmed = line.trim();
          if (trimmed.startsWith('GOOGLE_CLOUD_PROJECT=')) {
            return trimmed.split('=')[1]?.trim().replace(/['"]/g, '') ?? null;
          }
        }
      } catch {
        // Ignore
      }
    }

    return this.projectId;
  }

  public setProjectId(projectId: string): void {
    this.projectId = projectId;
  }

  public generateAuthUrl(state: string, codeVerifier?: string): string {
    const params = new URLSearchParams({
      client_id: this.clientId,
      redirect_uri: GEMINI_OAUTH_REDIRECT_URI,
      response_type: 'code',
      scope: GEMINI_OAUTH_SCOPES.join(' '),
      access_type: 'offline',
      state,
    });

    if (codeVerifier) {
      const encoder = new TextEncoder();
      const data = encoder.encode(codeVerifier);
      // Create SHA-256 hash for PKCE
      // In real implementation, you'd use crypto.subtle.digest
      params.set('code_challenge_method', 'S256');
    }

    return `${GEMINI_OAUTH_AUTH_ENDPOINT}?${params.toString()}`;
  }

  public async exchangeCode(
    code: string,
    codeVerifier?: string
  ): Promise<GeminiOAuthCredentials> {
    const bodyData = new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      client_id: this.clientId,
      client_secret: this.clientSecret,
      redirect_uri: GEMINI_OAUTH_REDIRECT_URI,
    });

    if (codeVerifier) {
      bodyData.set('code_verifier', codeVerifier);
    }

    const response = await fetch(GEMINI_OAUTH_TOKEN_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        Accept: 'application/json',
      },
      body: bodyData.toString(),
    });

    if (response.status !== HTTP_OK) {
      throw new AuthenticationError(
        `Code exchange failed: ${response.status} - ${await response.text()}`
      );
    }

    const tokenData = (await response.json()) as Record<string, unknown>;

    if (tokenData['error']) {
      throw new AuthenticationError(
        `Code exchange failed: ${tokenData['error']} - ${tokenData['error_description'] ?? 'Unknown error'}`
      );
    }

    const credentials: GeminiOAuthCredentials = {
      accessToken: tokenData['access_token'] as string,
      refreshToken: tokenData['refresh_token'] as string,
      tokenType: (tokenData['token_type'] as string) ?? 'Bearer',
      expiryDate:
        Date.now() + ((tokenData['expires_in'] as number) ?? 3600) * 1000,
    };

    this.saveCredentials(credentials);
    this.credentials = credentials;

    return credentials;
  }
}
