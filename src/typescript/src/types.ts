/**
 * Type definitions for GeminiSDK TypeScript
 *
 * Based on:
 * - GitHub Copilot SDK types
 * - Google Gemini CLI implementation
 */

// =============================================================================
// Connection and Session Types
// =============================================================================

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';
export type LogLevel = 'none' | 'error' | 'warning' | 'info' | 'debug' | 'all';

export enum Role {
  USER = 'user',
  ASSISTANT = 'assistant',
  SYSTEM = 'system',
}

// =============================================================================
// OAuth and Authentication Types
// =============================================================================

export interface GeminiOAuthCredentials {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiryDate: number; // Timestamp in milliseconds
}

// =============================================================================
// Model Types
// =============================================================================

export interface GeminiModelInfo {
  id: string;
  name: string;
  contextWindow: number;
  maxOutput: number;
  inputPrice: number;
  outputPrice: number;
  supportsNativeTools: boolean;
  supportsThinking: boolean;
}

export interface ModelVisionLimits {
  supportedMediaTypes?: string[];
  maxPromptImages?: number;
  maxPromptImageSize?: number;
}

export interface ModelLimits {
  maxPromptTokens?: number;
  maxContextWindowTokens?: number;
  vision?: ModelVisionLimits;
}

export interface ModelSupports {
  vision: boolean;
  tools: boolean;
  thinking: boolean;
}

export interface ModelCapabilities {
  supports: ModelSupports;
  limits: ModelLimits;
}

export interface ModelInfo {
  id: string;
  name: string;
  capabilities: ModelCapabilities;
}

// =============================================================================
// Message and Content Types
// =============================================================================

export interface ContentPart {
  text?: string;
  imageUrl?: string;
  imageData?: Uint8Array;
  imageMimeType?: string;
}

export interface Message {
  role: Role;
  content: string | ContentPart[];
  name?: string;
  toolCalls?: ToolCall[];
  toolCallId?: string;
}

export interface Attachment {
  type: 'file' | 'image';
  path?: string;
  url?: string;
  data?: string; // base64 encoded
  mimeType?: string;
}

// =============================================================================
// Tool Types
// =============================================================================

export interface FunctionCall {
  name: string;
  arguments: Record<string, unknown> | string;
}

export interface ToolCall {
  id: string;
  type: 'function';
  function: FunctionCall;
}

export interface ToolInvocation {
  name: string;
  arguments: Record<string, unknown>;
  callId: string;
}

export type ToolResultType = 'success' | 'failure' | 'rejected' | 'denied';

export interface ToolResult {
  resultType?: ToolResultType;
  textResultForLlm?: string;
  binaryResult?: Uint8Array;
  sessionLog?: string;
}

export type ToolHandler = (
  invocation: ToolInvocation
) => ToolResult | Promise<ToolResult>;

export interface Tool {
  name: string;
  description: string;
  parameters?: Record<string, unknown>;
  handler?: ToolHandler;
}

// =============================================================================
// Generation Config Types
// =============================================================================

export interface GenerationConfig {
  temperature?: number;
  maxOutputTokens?: number;
  topP?: number;
  topK?: number;
  stopSequences?: string[];
}

export interface ThinkingConfig {
  includeThoughts?: boolean;
  thinkingBudget?: number;
}

// =============================================================================
// Request/Response Types
// =============================================================================

export interface MessageOptions {
  prompt: string;
  attachments?: Attachment[];
  context?: string;
}

export interface LLMUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export interface LLMChunk {
  content: string;
  reasoningContent?: string;
  toolCalls?: ToolCall[];
  usage?: LLMUsage;
  finishReason?: string;
}

// =============================================================================
// Session Types
// =============================================================================

export interface SessionConfig {
  sessionId?: string;
  model?: string;
  tools?: Tool[];
  systemMessage?: string;
  generationConfig?: GenerationConfig;
  thinkingConfig?: ThinkingConfig;
  streaming?: boolean;
}

export interface SessionMetadata {
  sessionId: string;
  startTime: string;
  modifiedTime: string;
  summary?: string;
  model: string;
}

// =============================================================================
// Client Options Types
// =============================================================================

export interface GeminiClientOptions {
  oauthPath?: string;
  clientId?: string;
  clientSecret?: string;
  baseUrl?: string;
  timeout?: number;
  logLevel?: LogLevel;
  autoRefresh?: boolean;
}

// =============================================================================
// Event Types
// =============================================================================

export enum EventType {
  SESSION_CREATED = 'session.created',
  SESSION_IDLE = 'session.idle',
  SESSION_ERROR = 'session.error',
  ASSISTANT_MESSAGE = 'assistant.message',
  ASSISTANT_MESSAGE_DELTA = 'assistant.message_delta',
  ASSISTANT_REASONING = 'assistant.reasoning',
  ASSISTANT_REASONING_DELTA = 'assistant.reasoning_delta',
  TOOL_CALL = 'tool.call',
  TOOL_RESULT = 'tool.result',
}

export interface SessionEvent {
  type: EventType;
  data: unknown;
  sessionId: string;
}

export type SessionEventHandler = (event: SessionEvent) => void;

// =============================================================================
// Constants
// =============================================================================

export const GEMINI_OAUTH_REDIRECT_URI = 'http://localhost:45289';
export const GEMINI_OAUTH_BASE_URL = 'https://accounts.google.com';
export const GEMINI_OAUTH_TOKEN_ENDPOINT = `${GEMINI_OAUTH_BASE_URL}/o/oauth2/token`;
export const GEMINI_OAUTH_AUTH_ENDPOINT = `${GEMINI_OAUTH_BASE_URL}/o/oauth2/v2/auth`;

// Official Google OAuth client credentials for Gemini CLI
export const GEMINI_OAUTH_CLIENT_ID =
  '681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com';
export const GEMINI_OAUTH_CLIENT_SECRET = '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';

export const GEMINI_OAUTH_SCOPES = [
  'https://www.googleapis.com/auth/cloud-platform',
  'https://www.googleapis.com/auth/userinfo.email',
  'https://www.googleapis.com/auth/userinfo.profile',
];

export const GEMINI_CODE_ASSIST_ENDPOINT = 'https://cloudcode-pa.googleapis.com';
export const GEMINI_CODE_ASSIST_API_VERSION = 'v1internal';

export const GEMINI_DIR = '.gemini';
export const GEMINI_CREDENTIAL_FILENAME = 'oauth_creds.json';
export const GEMINI_ENV_FILENAME = '.env';

export const TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000;

export const HTTP_OK = 200;
export const HTTP_UNAUTHORIZED = 401;
export const HTTP_FORBIDDEN = 403;

export const GEMINI_CLI_MODELS: Record<string, GeminiModelInfo> = {
  'gemini-3-pro-preview': {
    id: 'gemini-3-pro-preview',
    name: 'Gemini 3 Pro Preview',
    contextWindow: 1_000_000,
    maxOutput: 65_536,
    inputPrice: 0.0,
    outputPrice: 0.0,
    supportsNativeTools: true,
    supportsThinking: true,
  },
  'gemini-3-flash-preview': {
    id: 'gemini-3-flash-preview',
    name: 'Gemini 3 Flash Preview',
    contextWindow: 1_000_000,
    maxOutput: 65_536,
    inputPrice: 0.0,
    outputPrice: 0.0,
    supportsNativeTools: true,
    supportsThinking: true,
  },
  'gemini-2.5-pro': {
    id: 'gemini-2.5-pro',
    name: 'Gemini 2.5 Pro',
    contextWindow: 1_048_576,
    maxOutput: 65_536,
    inputPrice: 0.0,
    outputPrice: 0.0,
    supportsNativeTools: true,
    supportsThinking: true,
  },
  'gemini-2.5-flash': {
    id: 'gemini-2.5-flash',
    name: 'Gemini 2.5 Flash',
    contextWindow: 1_048_576,
    maxOutput: 65_536,
    inputPrice: 0.0,
    outputPrice: 0.0,
    supportsNativeTools: true,
    supportsThinking: true,
  },
  'gemini-2.5-flash-lite': {
    id: 'gemini-2.5-flash-lite',
    name: 'Gemini 2.5 Flash Lite',
    contextWindow: 1_000_000,
    maxOutput: 32_768,
    inputPrice: 0.0,
    outputPrice: 0.0,
    supportsNativeTools: true,
    supportsThinking: false,
  },
  auto: {
    id: 'auto',
    name: 'Auto (Default)',
    contextWindow: 1_048_576,
    maxOutput: 65_536,
    inputPrice: 0.0,
    outputPrice: 0.0,
    supportsNativeTools: true,
    supportsThinking: true,
  },
};

export function getGeminiCliCredentialPath(customPath?: string): string {
  if (customPath) return customPath;
  const home = process.env['HOME'] ?? process.env['USERPROFILE'] ?? '';
  return `${home}/${GEMINI_DIR}/${GEMINI_CREDENTIAL_FILENAME}`;
}

export function getGeminiCliEnvPath(customPath?: string): string {
  if (customPath) return customPath;
  const home = process.env['HOME'] ?? process.env['USERPROFILE'] ?? '';
  return `${home}/${GEMINI_DIR}/${GEMINI_ENV_FILENAME}`;
}
