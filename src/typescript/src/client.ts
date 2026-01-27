/**
 * GeminiSDK Client - Main entry point for the Gemini SDK.
 */

import { GeminiOAuthManager } from './auth.js';
import { GeminiBackend } from './backend.js';
import { SessionNotFoundError } from './exceptions.js';
import { GeminiSession } from './session.js';
import {
  ConnectionState,
  GEMINI_CLI_MODELS,
  GeminiClientOptions,
  ModelInfo,
  SessionConfig,
  SessionMetadata,
} from './types.js';

// Simple UUID generator
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export class GeminiClient {
  private _options: GeminiClientOptions;
  private _state: ConnectionState = 'disconnected';
  private _backend: GeminiBackend | null = null;
  private _oauthManager: GeminiOAuthManager | null = null;
  private _sessions: Map<string, GeminiSession> = new Map();
  private _started = false;
  private _autoRefreshInterval: ReturnType<typeof setInterval> | null = null;

  constructor(options: GeminiClientOptions = {}) {
    this._options = options;
  }

  get options(): GeminiClientOptions {
    return this._options;
  }

  get state(): ConnectionState {
    return this._state;
  }

  public async start(): Promise<void> {
    if (this._started) return;

    this._state = 'connecting';

    try {
      this._oauthManager = new GeminiOAuthManager(
        this._options.oauthPath,
        this._options.clientId,
        this._options.clientSecret
      );

      this._backend = new GeminiBackend({
        timeout: this._options.timeout ?? 720000,
        oauthPath: this._options.oauthPath,
        clientId: this._options.clientId,
        clientSecret: this._options.clientSecret,
      });

      await this._oauthManager.ensureAuthenticated();

      this._state = 'connected';
      this._started = true;

      if (this._options.autoRefresh !== false) {
        this.startAutoRefresh();
      }
    } catch (e) {
      this._state = 'error';
      throw e;
    }
  }

  private startAutoRefresh(): void {
    if (this._autoRefreshInterval) return;

    this._autoRefreshInterval = setInterval(async () => {
      try {
        if (this._oauthManager) {
          await this._oauthManager.ensureAuthenticated();
        }
      } catch (e) {
        // Ignore background refresh errors
      }
    }, 30000);
  }

  public async stop(): Promise<void> {
    if (this._autoRefreshInterval) {
      clearInterval(this._autoRefreshInterval);
      this._autoRefreshInterval = null;
    }

    for (const session of this._sessions.values()) {
      try {
        await session.destroy();
      } catch (e) {
        console.warn('Error destroying session:', e);
      }
    }
    this._sessions.clear();

    if (this._backend) {
      await this._backend.close();
      this._backend = null;
    }

    this._oauthManager = null;
    this._state = 'disconnected';
    this._started = false;
  }

  public async close(): Promise<void> {
    await this.stop();
  }

  public async createSession(config: SessionConfig = {}): Promise<GeminiSession> {
    if (!this._started) {
      await this.start();
    }

    if (!this._backend) {
      throw new Error('Client not connected. Call start() first.');
    }

    const sessionId = config.sessionId ?? generateUUID();
    const model = config.model ?? 'gemini-2.5-pro';

    const session = new GeminiSession({
      sessionId,
      model,
      backend: this._backend,
      tools: config.tools,
      systemMessage: config.systemMessage,
      generationConfig: config.generationConfig,
      thinkingConfig: config.thinkingConfig,
      streaming: config.streaming ?? true,
    });

    this._sessions.set(sessionId, session);
    return session;
  }

  public async getSession(sessionId: string): Promise<GeminiSession> {
    const session = this._sessions.get(sessionId);
    if (!session) {
      throw new SessionNotFoundError(sessionId);
    }
    return session;
  }

  public async listSessions(): Promise<SessionMetadata[]> {
    const result: SessionMetadata[] = [];
    for (const session of this._sessions.values()) {
      result.push({
        sessionId: session.sessionId,
        startTime: session.startTime.toISOString(),
        modifiedTime: session.modifiedTime.toISOString(),
        model: session.model,
      });
    }
    return result;
  }

  public async deleteSession(sessionId: string): Promise<void> {
    const session = this._sessions.get(sessionId);
    if (session) {
      await session.destroy();
      this._sessions.delete(sessionId);
    }
  }

  public getState(): ConnectionState {
    return this._state;
  }

  public async getAuthStatus(): Promise<{ authenticated: boolean; tokenType?: string; expiresAt?: number }> {
    if (!this._oauthManager) {
      return { authenticated: false };
    }

    try {
      const credentials = await this._oauthManager.getCredentials();
      return {
        authenticated: true,
        tokenType: credentials.tokenType,
        expiresAt: credentials.expiryDate,
      };
    } catch {
      return { authenticated: false };
    }
  }

  public async listModels(): Promise<ModelInfo[]> {
    const models: ModelInfo[] = [];

    for (const [modelId, info] of Object.entries(GEMINI_CLI_MODELS)) {
      models.push({
        id: modelId,
        name: info.name,
        capabilities: {
          supports: {
            vision: false,
            tools: info.supportsNativeTools,
            thinking: info.supportsThinking,
          },
          limits: {
            maxContextWindowTokens: info.contextWindow,
            maxPromptTokens: info.contextWindow,
          },
        },
      });
    }

    return models;
  }

  public async refreshAuth(): Promise<void> {
    if (this._oauthManager) {
      await this._oauthManager.ensureAuthenticated(true);
    }
  }
}
