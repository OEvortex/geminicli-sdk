/**
 * Backend for Gemini CLI / Google Code Assist API.
 */

import { v4 as uuidv4 } from 'uuid';
import { GeminiOAuthManager } from './auth.js';
import {
  APIError,
  OnboardingError,
  PermissionDeniedError,
  RateLimitError,
} from './exceptions.js';
import {
  FunctionCall,
  GenerationConfig,
  HTTP_FORBIDDEN,
  HTTP_UNAUTHORIZED,
  LLMChunk,
  LLMUsage,
  Message,
  Role,
  ThinkingConfig,
  Tool,
  ToolCall,
} from './types.js';

const RETRYABLE_STATUS_CODES = new Set([HTTP_UNAUTHORIZED, HTTP_FORBIDDEN]);
const ONBOARD_MAX_RETRIES = 30;
const ONBOARD_SLEEP_SECONDS = 2;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Simple UUID generator if uuid package isn't available
function generateUUID(): string {
  try {
    return uuidv4();
  } catch {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }
}

export interface BackendOptions {
  timeout?: number;
  oauthPath?: string;
  clientId?: string;
  clientSecret?: string;
}

export class GeminiBackend {
  private timeout: number;
  private oauthManager: GeminiOAuthManager;
  private projectId: string | null = null;

  constructor(options: BackendOptions = {}) {
    this.timeout = options.timeout ?? 720000;
    this.oauthManager = new GeminiOAuthManager(
      options.oauthPath,
      options.clientId,
      options.clientSecret
    );
  }

  private async getAuthHeaders(forceRefresh = false): Promise<Record<string, string>> {
    const accessToken = await this.oauthManager.ensureAuthenticated(forceRefresh);
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    };
  }

  private prepareMessages(messages: Message[]): Array<Record<string, unknown>> {
    const result: Array<Record<string, unknown>> = [];

    for (const msg of messages) {
      const role = msg.role === Role.ASSISTANT ? 'model' : 'user';
      const contentParts: Array<Record<string, unknown>> = [];

      if (msg.content) {
        if (typeof msg.content === 'string') {
          contentParts.push({ text: msg.content });
        } else {
          for (const part of msg.content) {
            if (part.text) {
              contentParts.push({ text: part.text });
            } else if (part.imageData && part.imageMimeType) {
              contentParts.push({
                inlineData: {
                  mimeType: part.imageMimeType,
                  data:
                    part.imageData instanceof Uint8Array
                      ? Buffer.from(part.imageData).toString('base64')
                      : part.imageData,
                },
              });
            }
          }
        }
      }

      if (msg.toolCalls) {
        for (const tc of msg.toolCalls) {
          const args =
            typeof tc.function.arguments === 'string'
              ? JSON.parse(tc.function.arguments)
              : tc.function.arguments;
          contentParts.push({
            functionCall: {
              name: tc.function.name,
              args,
            },
          });
        }
      }

      if (msg.toolCallId) {
        contentParts.push({
          functionResponse: {
            name: msg.name ?? '',
            response:
              typeof msg.content === 'string'
                ? { result: msg.content }
                : msg.content,
          },
        });
      }

      if (contentParts.length > 0) {
        result.push({ role, parts: contentParts });
      }
    }

    return result;
  }

  private prepareTools(tools?: Tool[]): Array<Record<string, unknown>> | undefined {
    if (!tools || tools.length === 0) return undefined;

    const funcDecls: Array<Record<string, unknown>> = [];

    for (const tool of tools) {
      const funcDef: Record<string, unknown> = {
        name: tool.name,
        description: tool.description ?? '',
      };

      if (tool.parameters) {
        funcDef['parameters'] = {
          type: 'object',
          properties: (tool.parameters as Record<string, unknown>)['properties'] ?? {},
          required: (tool.parameters as Record<string, unknown>)['required'] ?? [],
        };
      }

      funcDecls.push(funcDef);
    }

    return [{ functionDeclarations: funcDecls }];
  }

  private async ensureProjectId(accessToken: string): Promise<string> {
    if (this.projectId !== null) return this.projectId;

    const envProjectId = this.oauthManager.getProjectId();
    const headers = {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    };

    const clientMetadata = {
      ideType: 'IDE_UNSPECIFIED',
      platform: 'PLATFORM_UNSPECIFIED',
      pluginType: 'GEMINI',
      duetProject: envProjectId,
    };

    const loadRequest = {
      cloudaicompanionProject: envProjectId,
      metadata: clientMetadata,
    };

    try {
      const url = `${this.oauthManager.getApiEndpoint()}:loadCodeAssist`;
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(loadRequest),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = (await response.json()) as Record<string, unknown>;

      if (data['currentTier']) {
        const projectFromApi = data['cloudaicompanionProject'] as string | undefined;
        if (projectFromApi) {
          this.projectId = projectFromApi;
          return projectFromApi;
        }
        if (envProjectId) {
          this.projectId = envProjectId;
          return envProjectId;
        }
        this.projectId = '';
        return '';
      }

      // Need to onboard
      const allowedTiers = (data['allowedTiers'] ?? []) as Array<Record<string, unknown>>;
      let tierId = 'free-tier';
      for (const tier of allowedTiers) {
        if (tier['isDefault']) {
          tierId = (tier['id'] as string) ?? 'free-tier';
          break;
        }
      }

      return this.onboardForProject(headers, envProjectId, clientMetadata, tierId);
    } catch (error) {
      throw new APIError(
        `Gemini Code Assist access denied: ${error}`,
        403,
        String(error)
      );
    }
  }

  private async onboardForProject(
    headers: Record<string, string>,
    envProjectId: string | null,
    clientMetadata: Record<string, unknown>,
    tierId: string
  ): Promise<string> {
    const onboardRequest =
      tierId === 'free-tier'
        ? {
            tierId,
            cloudaicompanionProject: null,
            metadata: clientMetadata,
          }
        : {
            tierId,
            cloudaicompanionProject: envProjectId,
            metadata: { ...clientMetadata, duetProject: envProjectId },
          };

    const url = `${this.oauthManager.getApiEndpoint()}:onboardUser`;

    for (let i = 0; i < ONBOARD_MAX_RETRIES; i++) {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(onboardRequest),
      });

      if (!response.ok) {
        throw new Error(`Onboard failed: ${response.status}`);
      }

      const lroData = (await response.json()) as Record<string, unknown>;

      if (lroData['done']) {
        const responseData = (lroData['response'] ?? {}) as Record<string, unknown>;
        const cloudAiCompanion = responseData['cloudaicompanionProject'] as
          | Record<string, unknown>
          | undefined;
        if (cloudAiCompanion?.['id']) {
          this.projectId = cloudAiCompanion['id'] as string;
          return this.projectId;
        }
        break;
      }

      await sleep(ONBOARD_SLEEP_SECONDS * 1000);
    }

    if (tierId === 'free-tier') {
      this.projectId = '';
      return '';
    }

    throw new OnboardingError(undefined, tierId);
  }

  private buildRequestPayload(
    model: string,
    messages: Message[],
    generationConfig?: GenerationConfig,
    thinkingConfig?: ThinkingConfig,
    tools?: Tool[],
    projectId = ''
  ): Record<string, unknown> {
    const genConfig: Record<string, unknown> = {
      temperature: generationConfig?.temperature ?? 0.7,
    };

    if (generationConfig?.maxOutputTokens) {
      genConfig['maxOutputTokens'] = generationConfig.maxOutputTokens;
    }
    if (generationConfig?.topP !== undefined) {
      genConfig['topP'] = generationConfig.topP;
    }
    if (generationConfig?.topK !== undefined) {
      genConfig['topK'] = generationConfig.topK;
    }
    if (generationConfig?.stopSequences) {
      genConfig['stopSequences'] = generationConfig.stopSequences;
    }

    if (thinkingConfig?.includeThoughts) {
      genConfig['thinkingConfig'] = {
        includeThoughts: thinkingConfig.includeThoughts,
        ...(thinkingConfig.thinkingBudget && {
          thinkingBudget: thinkingConfig.thinkingBudget,
        }),
      };
    }

    const requestBody: Record<string, unknown> = {
      contents: this.prepareMessages(messages),
      generationConfig: genConfig,
    };

    const preparedTools = this.prepareTools(tools);
    if (preparedTools) {
      requestBody['tools'] = preparedTools;
    }

    const payload: Record<string, unknown> = {
      model,
      request: requestBody,
    };

    if (projectId) {
      payload['project'] = projectId;
    }

    return payload;
  }

  private parseCompletionResponse(data: Record<string, unknown>): LLMChunk {
    const responseData = (data['response'] ?? data) as Record<string, unknown>;
    const candidates = (responseData['candidates'] ?? []) as Array<Record<string, unknown>>;

    if (candidates.length === 0) {
      return {
        content: '',
        reasoningContent: undefined,
        toolCalls: undefined,
        usage: undefined,
        finishReason: undefined,
      };
    }

    const candidate = candidates[0]!;
    const contentObj = (candidate['content'] ?? {}) as Record<string, unknown>;
    const parts = (contentObj['parts'] ?? []) as Array<Record<string, unknown>>;

    let textContent = '';
    let reasoningContent: string | undefined;
    let toolCalls: ToolCall[] | undefined;

    for (const part of parts) {
      if (part['text']) {
        textContent += part['text'] as string;
      }
      if (part['thought']) {
        reasoningContent = part['thought'] as string;
      }
      if (part['functionCall']) {
        const fc = part['functionCall'] as Record<string, unknown>;
        if (!toolCalls) toolCalls = [];
        toolCalls.push({
          id: generateUUID(),
          type: 'function',
          function: {
            name: (fc['name'] as string) ?? '',
            arguments: (fc['args'] ?? fc['arguments'] ?? {}) as Record<string, unknown>,
          },
        });
      }
    }

    const usageData = (data['usageMetadata'] ??
      responseData['usageMetadata'] ?? {}) as Record<string, unknown>;
    let usage: LLMUsage | undefined;

    if (Object.keys(usageData).length > 0) {
      usage = {
        promptTokens: (usageData['promptTokenCount'] as number) ?? 0,
        completionTokens: (usageData['candidatesTokenCount'] as number) ?? 0,
        totalTokens: (usageData['totalTokenCount'] as number) ?? 0,
      };
    }

    return {
      content: textContent,
      reasoningContent,
      toolCalls,
      usage,
      finishReason: candidate['finishReason'] as string | undefined,
    };
  }

  public async complete(options: {
    model: string;
    messages: Message[];
    generationConfig?: GenerationConfig;
    thinkingConfig?: ThinkingConfig;
    tools?: Tool[];
    extraHeaders?: Record<string, string>;
  }): Promise<LLMChunk> {
    return this.completeWithRetry(options, 0);
  }

  private async completeWithRetry(
    options: {
      model: string;
      messages: Message[];
      generationConfig?: GenerationConfig;
      thinkingConfig?: ThinkingConfig;
      tools?: Tool[];
      extraHeaders?: Record<string, string>;
    },
    retryCount: number
  ): Promise<LLMChunk> {
    const headers = await this.getAuthHeaders(retryCount > 0);
    if (options.extraHeaders) {
      Object.assign(headers, options.extraHeaders);
    }

    const accessToken = headers['Authorization']!.replace('Bearer ', '');
    const projectId = await this.ensureProjectId(accessToken);
    const url = `${this.oauthManager.getApiEndpoint()}:generateContent`;

    const payload = this.buildRequestPayload(
      options.model,
      options.messages,
      options.generationConfig,
      options.thinkingConfig,
      options.tools,
      projectId
    );

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (RETRYABLE_STATUS_CODES.has(response.status) && retryCount === 0) {
        this.oauthManager.invalidateCredentials();
        return this.completeWithRetry(options, 1);
      }

      if (!response.ok) {
        this.handleHttpError(response.status, await response.text());
      }

      const data = (await response.json()) as Record<string, unknown>;
      return this.parseCompletionResponse(data);
    } finally {
      clearTimeout(timeoutId);
    }
  }

  public async *completeStreaming(options: {
    model: string;
    messages: Message[];
    generationConfig?: GenerationConfig;
    thinkingConfig?: ThinkingConfig;
    tools?: Tool[];
    extraHeaders?: Record<string, string>;
  }): AsyncGenerator<LLMChunk, void, unknown> {
    yield* this.completeStreamingWithRetry(options, 0);
  }

  private async *completeStreamingWithRetry(
    options: {
      model: string;
      messages: Message[];
      generationConfig?: GenerationConfig;
      thinkingConfig?: ThinkingConfig;
      tools?: Tool[];
      extraHeaders?: Record<string, string>;
    },
    retryCount: number
  ): AsyncGenerator<LLMChunk, void, unknown> {
    const headers = await this.getAuthHeaders(retryCount > 0);
    if (options.extraHeaders) {
      Object.assign(headers, options.extraHeaders);
    }

    const accessToken = headers['Authorization']!.replace('Bearer ', '');
    const projectId = await this.ensureProjectId(accessToken);
    const url = `${this.oauthManager.getApiEndpoint()}:streamGenerateContent?alt=sse`;

    const payload = this.buildRequestPayload(
      options.model,
      options.messages,
      options.generationConfig,
      options.thinkingConfig,
      options.tools,
      projectId
    );

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (RETRYABLE_STATUS_CODES.has(response.status) && retryCount === 0) {
        this.oauthManager.invalidateCredentials();
        yield* this.completeStreamingWithRetry(options, 1);
        return;
      }

      if (!response.ok) {
        this.handleHttpError(response.status, await response.text());
      }

      if (!response.body) {
        throw new APIError('No response body', 500);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(':')) continue;

          if (trimmed.startsWith('data:')) {
            const data = trimmed.slice(5).trim();
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data) as Record<string, unknown>;
              if (parsed['error']) {
                const errorMsg =
                  typeof parsed['error'] === 'object'
                    ? ((parsed['error'] as Record<string, unknown>)['message'] as string)
                    : String(parsed['error']);
                throw new APIError(errorMsg, 500);
              }
              yield this.parseCompletionResponse(parsed);
            } catch (e) {
              if (e instanceof APIError) throw e;
              // Skip invalid JSON
            }
          }
        }
      }
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private handleHttpError(status: number, body: string): never {
    let errorMsg = body;
    try {
      const errorData = JSON.parse(body) as Record<string, unknown>;
      if (errorData['error']) {
        const err = errorData['error'] as Record<string, unknown>;
        errorMsg = (err['message'] as string) ?? body;
      }
    } catch {
      // Use body as-is
    }

    if (status === 429) {
      throw new RateLimitError(`Rate limit exceeded: ${errorMsg}`, 429, undefined, body);
    } else if (status === 403) {
      throw new PermissionDeniedError(`Permission denied: ${errorMsg}`, 403, body);
    } else {
      throw new APIError(`API error: ${errorMsg}`, status, body);
    }
  }

  public async listModels(): Promise<string[]> {
    const { GEMINI_CLI_MODELS } = await import('./types.js');
    return Object.keys(GEMINI_CLI_MODELS);
  }

  public async close(): Promise<void> {
    // No persistent connections to close in fetch-based implementation
  }
}
