/**
 * Custom exceptions for GeminiSDK TypeScript
 */

export interface ErrorDetails {
  [key: string]: unknown;
}

export class GeminiSDKError extends Error {
  public readonly details: ErrorDetails;

  constructor(message: string, details: ErrorDetails = {}) {
    super(message);
    this.name = 'GeminiSDKError';
    this.details = details;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class AuthenticationError extends GeminiSDKError {
  constructor(message = 'Authentication failed', details: ErrorDetails = {}) {
    super(message, details);
    this.name = 'AuthenticationError';
  }
}

export class CredentialsNotFoundError extends AuthenticationError {
  public readonly credentialPath: string;

  constructor(credentialPath: string, message?: string) {
    const msg =
      message ??
      `Gemini OAuth credentials not found at ${credentialPath}. ` +
        'Please login using the Gemini CLI first: gemini auth login';
    super(msg, { credentialPath });
    this.name = 'CredentialsNotFoundError';
    this.credentialPath = credentialPath;
  }
}

export class TokenRefreshError extends AuthenticationError {
  public readonly statusCode?: number;
  public readonly responseBody?: string;

  constructor(
    message = 'Failed to refresh access token',
    statusCode?: number,
    responseBody?: string
  ) {
    const details: ErrorDetails = {};
    if (statusCode !== undefined) details['statusCode'] = statusCode;
    if (responseBody !== undefined) details['responseBody'] = responseBody;
    super(message, details);
    this.name = 'TokenRefreshError';
    this.statusCode = statusCode;
    this.responseBody = responseBody;
  }
}

export class TokenExpiredError extends AuthenticationError {
  constructor(message = 'Access token has expired') {
    super(message);
    this.name = 'TokenExpiredError';
  }
}

export class ConnectionError extends GeminiSDKError {
  public readonly endpoint?: string;

  constructor(
    message = 'Failed to connect to Gemini API',
    endpoint?: string,
    details: ErrorDetails = {}
  ) {
    if (endpoint) details['endpoint'] = endpoint;
    super(message, details);
    this.name = 'ConnectionError';
    this.endpoint = endpoint;
  }
}

export class APIError extends GeminiSDKError {
  public readonly statusCode: number;
  public readonly responseBody?: string;
  public readonly endpoint?: string;

  constructor(
    message: string,
    statusCode: number,
    responseBody?: string,
    endpoint?: string
  ) {
    const details: ErrorDetails = { statusCode };
    if (responseBody !== undefined) details['responseBody'] = responseBody;
    if (endpoint !== undefined) details['endpoint'] = endpoint;
    super(message, details);
    this.name = 'APIError';
    this.statusCode = statusCode;
    this.responseBody = responseBody;
    this.endpoint = endpoint;
  }
}

export class RateLimitError extends APIError {
  public readonly retryAfter?: number;

  constructor(
    message = 'Rate limit exceeded',
    statusCode = 429,
    retryAfter?: number,
    responseBody?: string
  ) {
    super(message, statusCode, responseBody);
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
    if (retryAfter !== undefined) this.details['retryAfter'] = retryAfter;
  }
}

export class QuotaExceededError extends APIError {
  public readonly resetTime?: string;

  constructor(
    message = 'Quota exceeded',
    statusCode = 429,
    resetTime?: string,
    responseBody?: string
  ) {
    super(message, statusCode, responseBody);
    this.name = 'QuotaExceededError';
    this.resetTime = resetTime;
    if (resetTime !== undefined) this.details['resetTime'] = resetTime;
  }
}

export class PermissionDeniedError extends APIError {
  constructor(
    message = 'Permission denied',
    statusCode = 403,
    responseBody?: string
  ) {
    super(message, statusCode, responseBody);
    this.name = 'PermissionDeniedError';
  }
}

export class NotFoundError extends APIError {
  public readonly resource?: string;

  constructor(
    message = 'Resource not found',
    statusCode = 404,
    resource?: string,
    responseBody?: string
  ) {
    super(message, statusCode, responseBody);
    this.name = 'NotFoundError';
    this.resource = resource;
    if (resource !== undefined) this.details['resource'] = resource;
  }
}

export class SessionError extends GeminiSDKError {
  public readonly sessionId?: string;

  constructor(message: string, sessionId?: string, details: ErrorDetails = {}) {
    if (sessionId) details['sessionId'] = sessionId;
    super(message, details);
    this.name = 'SessionError';
    this.sessionId = sessionId;
  }
}

export class SessionNotFoundError extends SessionError {
  constructor(sessionId: string) {
    super(`Session not found: ${sessionId}`, sessionId);
    this.name = 'SessionNotFoundError';
  }
}

export class SessionClosedError extends SessionError {
  constructor(sessionId?: string) {
    super('Session is closed', sessionId);
    this.name = 'SessionClosedError';
  }
}

export class ToolError extends GeminiSDKError {
  public readonly toolName?: string;

  constructor(message: string, toolName?: string, details: ErrorDetails = {}) {
    if (toolName) details['toolName'] = toolName;
    super(message, details);
    this.name = 'ToolError';
    this.toolName = toolName;
  }
}

export class ToolNotFoundError extends ToolError {
  constructor(toolName: string) {
    super(`Tool not found: ${toolName}`, toolName);
    this.name = 'ToolNotFoundError';
  }
}

export class ToolExecutionError extends ToolError {
  public readonly originalError?: Error;

  constructor(message: string, toolName: string, originalError?: Error) {
    const details: ErrorDetails = {};
    if (originalError) details['originalError'] = originalError.message;
    super(message, toolName, details);
    this.name = 'ToolExecutionError';
    this.originalError = originalError;
  }
}

export class ValidationError extends GeminiSDKError {
  public readonly field?: string;
  public readonly value?: unknown;

  constructor(message: string, field?: string, value?: unknown) {
    const details: ErrorDetails = {};
    if (field !== undefined) details['field'] = field;
    if (value !== undefined) details['value'] = String(value);
    super(message, details);
    this.name = 'ValidationError';
    this.field = field;
    this.value = value;
  }
}

export class ConfigurationError extends GeminiSDKError {
  public readonly configKey?: string;

  constructor(message: string, configKey?: string) {
    const details: ErrorDetails = {};
    if (configKey) details['configKey'] = configKey;
    super(message, details);
    this.name = 'ConfigurationError';
    this.configKey = configKey;
  }
}

export class StreamError extends GeminiSDKError {
  public readonly partialContent?: string;

  constructor(message: string, partialContent?: string) {
    const details: ErrorDetails = {};
    if (partialContent) details['partialContent'] = partialContent.slice(0, 500);
    super(message, details);
    this.name = 'StreamError';
    this.partialContent = partialContent;
  }
}

export class CancellationError extends GeminiSDKError {
  constructor(message = 'Operation was cancelled') {
    super(message);
    this.name = 'CancellationError';
  }
}

export class TimeoutError extends GeminiSDKError {
  public readonly timeout?: number;

  constructor(message = 'Operation timed out', timeout?: number) {
    const details: ErrorDetails = {};
    if (timeout !== undefined) details['timeout'] = timeout;
    super(message, details);
    this.name = 'TimeoutError';
    this.timeout = timeout;
  }
}

export class OnboardingError extends GeminiSDKError {
  public readonly tierId?: string;

  constructor(
    message = 'Failed to complete Gemini Code Assist onboarding',
    tierId?: string
  ) {
    const details: ErrorDetails = {};
    if (tierId) details['tierId'] = tierId;
    super(message, details);
    this.name = 'OnboardingError';
    this.tierId = tierId;
  }
}
