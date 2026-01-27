package geminisdk

import "fmt"

// GeminiSDKError is the base error type
type GeminiSDKError struct {
	Message string
	Code    string
	Details map[string]interface{}
}

func (e *GeminiSDKError) Error() string {
	if e.Code != "" {
		return fmt.Sprintf("[%s] %s", e.Code, e.Message)
	}
	return e.Message
}

// AuthenticationError represents authentication failures
type AuthenticationError struct {
	GeminiSDKError
}

// CredentialsNotFoundError represents missing credentials
type CredentialsNotFoundError struct {
	GeminiSDKError
	CredentialPath string
}

// TokenRefreshError represents token refresh failures
type TokenRefreshError struct {
	GeminiSDKError
	StatusCode   int
	ResponseBody string
}

// TokenExpiredError represents expired tokens
type TokenExpiredError struct {
	GeminiSDKError
}

// ConnectionError represents connection failures
type ConnectionError struct {
	GeminiSDKError
	Endpoint string
}

// APIError represents API errors
type APIError struct {
	GeminiSDKError
	StatusCode   int
	ResponseBody string
	Endpoint     string
}

// RateLimitError represents rate limiting
type RateLimitError struct {
	APIError
	RetryAfter int
}

// QuotaExceededError represents quota exhaustion
type QuotaExceededError struct {
	APIError
	ResetTime string
}

// PermissionDeniedError represents permission failures
type PermissionDeniedError struct {
	APIError
}

// NotFoundError represents resource not found
type NotFoundError struct {
	APIError
	Resource string
}

// SessionError represents session errors
type SessionError struct {
	GeminiSDKError
	SessionID string
}

// SessionNotFoundError represents missing sessions
type SessionNotFoundError struct {
	SessionError
}

// SessionClosedError represents closed sessions
type SessionClosedError struct {
	SessionError
}

// ToolError represents tool errors
type ToolError struct {
	GeminiSDKError
	ToolName string
}

// ToolNotFoundError represents missing tools
type ToolNotFoundError struct {
	ToolError
}

// ToolExecutionError represents tool execution failures
type ToolExecutionError struct {
	ToolError
	OriginalError error
}

// ValidationError represents validation failures
type ValidationError struct {
	GeminiSDKError
	Field string
	Value interface{}
}

// ConfigurationError represents configuration errors
type ConfigurationError struct {
	GeminiSDKError
	ConfigKey string
}

// StreamError represents streaming errors
type StreamError struct {
	GeminiSDKError
	PartialContent string
}

// CancellationError represents cancelled operations
type CancellationError struct {
	GeminiSDKError
}

// TimeoutError represents timeouts
type TimeoutError struct {
	GeminiSDKError
	Timeout float64
}

// OnboardingError represents onboarding failures
type OnboardingError struct {
	GeminiSDKError
	TierID string
}

// Helper functions to create errors

// NewAuthenticationError creates a new authentication error
func NewAuthenticationError(message string) *AuthenticationError {
	return &AuthenticationError{
		GeminiSDKError: GeminiSDKError{
			Message: message,
			Code:    "AUTHENTICATION_ERROR",
		},
	}
}

// NewCredentialsNotFoundError creates a new credentials not found error
func NewCredentialsNotFoundError(path string) *CredentialsNotFoundError {
	return &CredentialsNotFoundError{
		GeminiSDKError: GeminiSDKError{
			Message: fmt.Sprintf("Credentials not found at %s", path),
			Code:    "CREDENTIALS_NOT_FOUND",
		},
		CredentialPath: path,
	}
}

// NewTokenRefreshError creates a new token refresh error
func NewTokenRefreshError(message string, statusCode int, responseBody string) *TokenRefreshError {
	return &TokenRefreshError{
		GeminiSDKError: GeminiSDKError{
			Message: message,
			Code:    "TOKEN_REFRESH_ERROR",
		},
		StatusCode:   statusCode,
		ResponseBody: responseBody,
	}
}

// NewAPIError creates a new API error
func NewAPIError(message string, statusCode int, endpoint string) *APIError {
	return &APIError{
		GeminiSDKError: GeminiSDKError{
			Message: message,
			Code:    "API_ERROR",
		},
		StatusCode: statusCode,
		Endpoint:   endpoint,
	}
}

// NewRateLimitError creates a new rate limit error
func NewRateLimitError(message string, retryAfter int) *RateLimitError {
	return &RateLimitError{
		APIError: APIError{
			GeminiSDKError: GeminiSDKError{
				Message: message,
				Code:    "RATE_LIMIT_ERROR",
			},
			StatusCode: 429,
		},
		RetryAfter: retryAfter,
	}
}

// NewSessionNotFoundError creates a new session not found error
func NewSessionNotFoundError(sessionID string) *SessionNotFoundError {
	return &SessionNotFoundError{
		SessionError: SessionError{
			GeminiSDKError: GeminiSDKError{
				Message: fmt.Sprintf("Session not found: %s", sessionID),
				Code:    "SESSION_NOT_FOUND",
			},
			SessionID: sessionID,
		},
	}
}

// NewSessionClosedError creates a new session closed error
func NewSessionClosedError(sessionID string) *SessionClosedError {
	return &SessionClosedError{
		SessionError: SessionError{
			GeminiSDKError: GeminiSDKError{
				Message: "Session is closed",
				Code:    "SESSION_CLOSED",
			},
			SessionID: sessionID,
		},
	}
}

// NewToolNotFoundError creates a new tool not found error
func NewToolNotFoundError(toolName string) *ToolNotFoundError {
	return &ToolNotFoundError{
		ToolError: ToolError{
			GeminiSDKError: GeminiSDKError{
				Message: fmt.Sprintf("Tool not found: %s", toolName),
				Code:    "TOOL_NOT_FOUND",
			},
			ToolName: toolName,
		},
	}
}

// NewToolExecutionError creates a new tool execution error
func NewToolExecutionError(toolName string, err error) *ToolExecutionError {
	return &ToolExecutionError{
		ToolError: ToolError{
			GeminiSDKError: GeminiSDKError{
				Message: fmt.Sprintf("Error executing tool '%s': %v", toolName, err),
				Code:    "TOOL_EXECUTION_ERROR",
			},
			ToolName: toolName,
		},
		OriginalError: err,
	}
}

// NewConfigurationError creates a new configuration error
func NewConfigurationError(message string) *ConfigurationError {
	return &ConfigurationError{
		GeminiSDKError: GeminiSDKError{
			Message: message,
			Code:    "CONFIGURATION_ERROR",
		},
	}
}

// NewStreamError creates a new stream error
func NewStreamError(message string) *StreamError {
	return &StreamError{
		GeminiSDKError: GeminiSDKError{
			Message: message,
			Code:    "STREAM_ERROR",
		},
	}
}

// NewOnboardingError creates a new onboarding error
func NewOnboardingError(message string, tierID string) *OnboardingError {
	return &OnboardingError{
		GeminiSDKError: GeminiSDKError{
			Message: message,
			Code:    "ONBOARDING_ERROR",
		},
		TierID: tierID,
	}
}
