package geminisdk

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
)

// Connection states
type ConnectionState string

const (
	StateDisconnected ConnectionState = "disconnected"
	StateConnecting   ConnectionState = "connecting"
	StateConnected    ConnectionState = "connected"
	StateError        ConnectionState = "error"
)

// Log levels
type LogLevel string

const (
	LogNone    LogLevel = "none"
	LogError   LogLevel = "error"
	LogWarning LogLevel = "warning"
	LogInfo    LogLevel = "info"
	LogDebug   LogLevel = "debug"
	LogAll     LogLevel = "all"
)

// Roles
type Role string

const (
	RoleUser      Role = "user"
	RoleAssistant Role = "assistant"
	RoleSystem    Role = "system"
)

// Event types
type EventType string

const (
	EventSessionCreated         EventType = "session.created"
	EventSessionIdle            EventType = "session.idle"
	EventSessionError           EventType = "session.error"
	EventAssistantMessage       EventType = "assistant.message"
	EventAssistantMessageDelta  EventType = "assistant.message_delta"
	EventAssistantReasoning     EventType = "assistant.reasoning"
	EventAssistantReasoningDelta EventType = "assistant.reasoning_delta"
	EventToolCall               EventType = "tool.call"
	EventToolResult             EventType = "tool.result"
)

// OAuth constants
const (
	GeminiOAuthRedirectURI    = "http://localhost:45289"
	GeminiOAuthBaseURL        = "https://accounts.google.com"
	GeminiOAuthTokenEndpoint  = "https://accounts.google.com/o/oauth2/token"
	GeminiOAuthAuthEndpoint   = "https://accounts.google.com/o/oauth2/v2/auth"
	GeminiOAuthClientID       = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
	GeminiOAuthClientSecret   = "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"
	GeminiCodeAssistEndpoint  = "https://cloudcode-pa.googleapis.com"
	GeminiCodeAssistAPIVersion = "v1internal"
	GeminiDir                 = ".gemini"
	GeminiCredentialFilename  = "oauth_creds.json"
	GeminiEnvFilename         = ".env"
	TokenRefreshBufferMs      = 5 * 60 * 1000
)

var GeminiOAuthScopes = []string{
	"https://www.googleapis.com/auth/cloud-platform",
	"https://www.googleapis.com/auth/userinfo.email",
	"https://www.googleapis.com/auth/userinfo.profile",
}

// GeminiOAuthCredentials represents OAuth credentials
type GeminiOAuthCredentials struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	TokenType    string `json:"token_type"`
	ExpiryDate   int64  `json:"expiry_date"`
}

// GeminiModelInfo represents model information
type GeminiModelInfo struct {
	ID                  string  `json:"id"`
	Name                string  `json:"name"`
	ContextWindow       int64   `json:"context_window"`
	MaxOutput           int64   `json:"max_output"`
	InputPrice          float64 `json:"input_price"`
	OutputPrice         float64 `json:"output_price"`
	SupportsNativeTools bool    `json:"supports_native_tools"`
	SupportsThinking    bool    `json:"supports_thinking"`
}

// ModelSupports represents model support flags
type ModelSupports struct {
	Vision   bool `json:"vision"`
	Tools    bool `json:"tools"`
	Thinking bool `json:"thinking"`
}

// ModelVisionLimits represents vision limits
type ModelVisionLimits struct {
	SupportedMediaTypes []string `json:"supported_media_types,omitempty"`
	MaxPromptImages     int      `json:"max_prompt_images,omitempty"`
	MaxPromptImageSize  int64    `json:"max_prompt_image_size,omitempty"`
}

// ModelLimits represents model limits
type ModelLimits struct {
	MaxPromptTokens        *int64             `json:"max_prompt_tokens,omitempty"`
	MaxContextWindowTokens *int64             `json:"max_context_window_tokens,omitempty"`
	Vision                 *ModelVisionLimits `json:"vision,omitempty"`
}

// ModelCapabilities represents model capabilities
type ModelCapabilities struct {
	Supports ModelSupports `json:"supports"`
	Limits   ModelLimits   `json:"limits"`
}

// ModelInfo represents a model
type ModelInfo struct {
	ID           string            `json:"id"`
	Name         string            `json:"name"`
	Capabilities ModelCapabilities `json:"capabilities"`
}

// ContentPart represents a content part
type ContentPart struct {
	Text          string `json:"text,omitempty"`
	ImageURL      string `json:"image_url,omitempty"`
	ImageData     []byte `json:"image_data,omitempty"`
	ImageMimeType string `json:"image_mime_type,omitempty"`
}

// Message represents a conversation message
type Message struct {
	Role       Role          `json:"role"`
	Content    string        `json:"content"`
	Parts      []ContentPart `json:"parts,omitempty"`
	Name       string        `json:"name,omitempty"`
	ToolCalls  []ToolCall    `json:"tool_calls,omitempty"`
	ToolCallID string        `json:"tool_call_id,omitempty"`
}

// Attachment represents a file attachment
type Attachment struct {
	Type     string `json:"type"`
	Path     string `json:"path,omitempty"`
	URL      string `json:"url,omitempty"`
	Data     string `json:"data,omitempty"`
	MimeType string `json:"mime_type,omitempty"`
}

// FunctionCall represents a function call
type FunctionCall struct {
	Name      string          `json:"name"`
	Arguments json.RawMessage `json:"arguments"`
}

// ToolCall represents a tool invocation
type ToolCall struct {
	ID       string       `json:"id"`
	Type     string       `json:"type"`
	Function FunctionCall `json:"function"`
}

// ToolInvocation represents a tool invocation for handlers
type ToolInvocation struct {
	Name      string                 `json:"name"`
	Arguments map[string]interface{} `json:"arguments"`
	CallID    string                 `json:"call_id"`
}

// ToolResultType represents tool result types
type ToolResultType string

const (
	ToolResultSuccess  ToolResultType = "success"
	ToolResultFailure  ToolResultType = "failure"
	ToolResultRejected ToolResultType = "rejected"
	ToolResultDenied   ToolResultType = "denied"
)

// ToolResult represents the result of a tool execution
type ToolResult struct {
	ResultType       ToolResultType `json:"result_type,omitempty"`
	TextResultForLLM string         `json:"text_result_for_llm,omitempty"`
	BinaryResult     []byte         `json:"binary_result,omitempty"`
	SessionLog       string         `json:"session_log,omitempty"`
}

// Tool represents a tool definition
type Tool struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	Parameters  json.RawMessage `json:"parameters,omitempty"`
}

// GenerationConfig represents generation configuration
type GenerationConfig struct {
	Temperature     float64  `json:"temperature,omitempty"`
	MaxOutputTokens int      `json:"max_output_tokens,omitempty"`
	TopP            float64  `json:"top_p,omitempty"`
	TopK            int      `json:"top_k,omitempty"`
	StopSequences   []string `json:"stop_sequences,omitempty"`
}

// ThinkingConfig represents thinking configuration
type ThinkingConfig struct {
	IncludeThoughts bool `json:"include_thoughts"`
	ThinkingBudget  int  `json:"thinking_budget,omitempty"`
}

// MessageOptions represents options for sending a message
type MessageOptions struct {
	Prompt      string       `json:"prompt"`
	Attachments []Attachment `json:"attachments,omitempty"`
	Context     string       `json:"context,omitempty"`
}

// LLMUsage represents token usage
type LLMUsage struct {
	PromptTokens     int64 `json:"prompt_tokens"`
	CompletionTokens int64 `json:"completion_tokens"`
	TotalTokens      int64 `json:"total_tokens"`
}

// LLMChunk represents a response chunk
type LLMChunk struct {
	Content          string     `json:"content"`
	ReasoningContent string     `json:"reasoning_content,omitempty"`
	ToolCalls        []ToolCall `json:"tool_calls,omitempty"`
	Usage            *LLMUsage  `json:"usage,omitempty"`
	FinishReason     string     `json:"finish_reason,omitempty"`
}

// SessionConfig represents session configuration
type SessionConfig struct {
	SessionID        string           `json:"session_id,omitempty"`
	Model            string           `json:"model,omitempty"`
	Tools            []Tool           `json:"tools,omitempty"`
	SystemMessage    string           `json:"system_message,omitempty"`
	GenerationConfig *GenerationConfig `json:"generation_config,omitempty"`
	ThinkingConfig   *ThinkingConfig  `json:"thinking_config,omitempty"`
	Streaming        bool             `json:"streaming"`
}

// SessionMetadata represents session metadata
type SessionMetadata struct {
	SessionID    string `json:"session_id"`
	StartTime    string `json:"start_time"`
	ModifiedTime string `json:"modified_time"`
	Summary      string `json:"summary,omitempty"`
	Model        string `json:"model"`
}

// ClientOptions represents client configuration options
type ClientOptions struct {
	OAuthPath    string        `json:"oauth_path,omitempty"`
	ClientID     string        `json:"client_id,omitempty"`
	ClientSecret string        `json:"client_secret,omitempty"`
	BaseURL      string        `json:"base_url,omitempty"`
	Timeout      float64       `json:"timeout,omitempty"`
	LogLevel     LogLevel      `json:"log_level,omitempty"`
	AutoRefresh  bool          `json:"auto_refresh"`
}

// SessionEvent represents an event from a session
type SessionEvent struct {
	EventType EventType              `json:"event_type"`
	Data      map[string]interface{} `json:"data"`
	SessionID string                 `json:"session_id"`
}

// GetGeminiCLICredentialPath returns the path to Gemini CLI credentials
func GetGeminiCLICredentialPath(customPath string) string {
	if customPath != "" {
		return customPath
	}
	homeDir, _ := os.UserHomeDir()
	return filepath.Join(homeDir, GeminiDir, GeminiCredentialFilename)
}

// GetGeminiCLIEnvPath returns the path to Gemini CLI environment file
func GetGeminiCLIEnvPath(customPath string) string {
	if customPath != "" {
		return customPath
	}
	homeDir, _ := os.UserHomeDir()
	return filepath.Join(homeDir, GeminiDir, GeminiEnvFilename)
}

// GetGeminiCLIModels returns available Gemini CLI models
func GetGeminiCLIModels() map[string]GeminiModelInfo {
	return map[string]GeminiModelInfo{
		"gemini-3-pro-preview": {
			ID:                  "gemini-3-pro-preview",
			Name:                "Gemini 3 Pro Preview",
			ContextWindow:       1000000,
			MaxOutput:           65536,
			SupportsNativeTools: true,
			SupportsThinking:    true,
		},
		"gemini-3-flash-preview": {
			ID:                  "gemini-3-flash-preview",
			Name:                "Gemini 3 Flash Preview",
			ContextWindow:       1000000,
			MaxOutput:           65536,
			SupportsNativeTools: true,
			SupportsThinking:    true,
		},
		"gemini-2.5-pro": {
			ID:                  "gemini-2.5-pro",
			Name:                "Gemini 2.5 Pro",
			ContextWindow:       1048576,
			MaxOutput:           65536,
			SupportsNativeTools: true,
			SupportsThinking:    true,
		},
		"gemini-2.5-flash": {
			ID:                  "gemini-2.5-flash",
			Name:                "Gemini 2.5 Flash",
			ContextWindow:       1048576,
			MaxOutput:           65536,
			SupportsNativeTools: true,
			SupportsThinking:    true,
		},
		"gemini-2.5-flash-lite": {
			ID:                  "gemini-2.5-flash-lite",
			Name:                "Gemini 2.5 Flash Lite",
			ContextWindow:       1000000,
			MaxOutput:           32768,
			SupportsNativeTools: true,
			SupportsThinking:    false,
		},
		"auto": {
			ID:                  "auto",
			Name:                "Auto (Default)",
			ContextWindow:       1048576,
			MaxOutput:           65536,
			SupportsNativeTools: true,
			SupportsThinking:    true,
		},
	}
}

// GetUserAgent returns the user agent string
func GetUserAgent() string {
	return "GeminiSDK-Go/0.1.0 (" + runtime.GOOS + "; " + runtime.GOARCH + ")"
}
