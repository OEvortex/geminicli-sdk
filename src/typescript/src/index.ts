/**
 * GeminiSDK TypeScript - A TypeScript SDK for Google Gemini Code Assist API.
 *
 * This SDK provides a high-level interface for interacting with the Gemini
 * Code Assist API, supporting OAuth authentication, streaming responses,
 * tool calling, and session management.
 *
 * @example
 * ```typescript
 * import { GeminiClient, EventType } from 'geminisdk';
 *
 * async function main() {
 *   const client = new GeminiClient();
 *   await client.start();
 *
 *   const session = await client.createSession({
 *     model: 'gemini-2.5-pro',
 *     streaming: true,
 *   });
 *
 *   session.on((event) => {
 *     if (event.type === EventType.ASSISTANT_MESSAGE_DELTA) {
 *       process.stdout.write((event.data as any).deltaContent);
 *     }
 *   });
 *
 *   await session.send({ prompt: 'What is TypeScript?' });
 *   await client.close();
 * }
 *
 * main();
 * ```
 */

export const VERSION = '0.1.1';

// Client
export { GeminiClient } from './client.js';

// Session
export { GeminiSession } from './session.js';

// Backend
export { GeminiBackend } from './backend.js';

// Authentication
export { GeminiOAuthManager } from './auth.js';

// Tools
export {
  ToolRegistry,
  createTool,
  defineTool,
  getDefaultRegistry,
  registerTool,
} from './tools.js';

// Types
export {
  // Connection
  ConnectionState,
  LogLevel,
  Role,
  // OAuth
  GeminiOAuthCredentials,
  // Models
  GeminiModelInfo,
  ModelVisionLimits,
  ModelLimits,
  ModelSupports,
  ModelCapabilities,
  ModelInfo,
  // Messages
  ContentPart,
  Message,
  Attachment,
  // Tools
  FunctionCall,
  ToolCall,
  ToolInvocation,
  ToolResultType,
  ToolResult,
  ToolHandler,
  Tool,
  // Generation
  GenerationConfig,
  ThinkingConfig,
  // Request/Response
  MessageOptions,
  LLMUsage,
  LLMChunk,
  // Session
  SessionConfig,
  SessionMetadata,
  // Client
  GeminiClientOptions,
  // Events
  EventType,
  SessionEvent,
  SessionEventHandler,
  // Constants
  GEMINI_OAUTH_REDIRECT_URI,
  GEMINI_OAUTH_BASE_URL,
  GEMINI_OAUTH_TOKEN_ENDPOINT,
  GEMINI_OAUTH_AUTH_ENDPOINT,
  GEMINI_OAUTH_CLIENT_ID,
  GEMINI_OAUTH_CLIENT_SECRET,
  GEMINI_OAUTH_SCOPES,
  GEMINI_CODE_ASSIST_ENDPOINT,
  GEMINI_CODE_ASSIST_API_VERSION,
  GEMINI_DIR,
  GEMINI_CREDENTIAL_FILENAME,
  GEMINI_ENV_FILENAME,
  TOKEN_REFRESH_BUFFER_MS,
  HTTP_OK,
  HTTP_UNAUTHORIZED,
  HTTP_FORBIDDEN,
  GEMINI_CLI_MODELS,
  getGeminiCliCredentialPath,
  getGeminiCliEnvPath,
} from './types.js';

// Exceptions
export {
  GeminiSDKError,
  AuthenticationError,
  CredentialsNotFoundError,
  TokenRefreshError,
  TokenExpiredError,
  ConnectionError,
  APIError,
  RateLimitError,
  QuotaExceededError,
  PermissionDeniedError,
  NotFoundError,
  SessionError,
  SessionNotFoundError,
  SessionClosedError,
  ToolError,
  ToolNotFoundError,
  ToolExecutionError,
  ValidationError,
  ConfigurationError,
  StreamError,
  CancellationError,
  TimeoutError,
  OnboardingError,
} from './exceptions.js';
