//! Type definitions for GeminiSDK Rust
//!
//! Based on:
//! - GitHub Copilot SDK types
//! - Google Gemini CLI implementation

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// =============================================================================
// Connection and Session Types
// =============================================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ConnectionState {
    Disconnected,
    Connecting,
    Connected,
    Error,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LogLevel {
    None,
    Error,
    Warning,
    Info,
    Debug,
    All,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    User,
    Assistant,
    System,
}

impl Role {
    pub fn as_str(&self) -> &'static str {
        match self {
            Role::User => "user",
            Role::Assistant => "assistant",
            Role::System => "system",
        }
    }
}

// =============================================================================
// OAuth and Authentication Types
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeminiOAuthCredentials {
    pub access_token: String,
    pub refresh_token: String,
    #[serde(default = "default_token_type")]
    pub token_type: String,
    #[serde(default)]
    pub expiry_date: u64,
}

fn default_token_type() -> String {
    "Bearer".to_string()
}

// =============================================================================
// Model Types
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeminiModelInfo {
    pub id: String,
    pub name: String,
    #[serde(default = "default_context_window")]
    pub context_window: u64,
    #[serde(default = "default_max_output")]
    pub max_output: u64,
    #[serde(default)]
    pub input_price: f64,
    #[serde(default)]
    pub output_price: f64,
    #[serde(default = "default_true")]
    pub supports_native_tools: bool,
    #[serde(default = "default_true")]
    pub supports_thinking: bool,
}

fn default_context_window() -> u64 {
    1_048_576
}

fn default_max_output() -> u64 {
    32_768
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelVisionLimits {
    pub supported_media_types: Option<Vec<String>>,
    pub max_prompt_images: Option<u32>,
    pub max_prompt_image_size: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelLimits {
    pub max_prompt_tokens: Option<u64>,
    pub max_context_window_tokens: Option<u64>,
    pub vision: Option<ModelVisionLimits>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelSupports {
    pub vision: bool,
    pub tools: bool,
    pub thinking: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCapabilities {
    pub supports: ModelSupports,
    pub limits: ModelLimits,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub id: String,
    pub name: String,
    pub capabilities: ModelCapabilities,
}

// =============================================================================
// Message and Content Types
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContentPart {
    pub text: Option<String>,
    pub image_url: Option<String>,
    pub image_data: Option<Vec<u8>>,
    pub image_mime_type: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: Role,
    pub content: MessageContent,
    pub name: Option<String>,
    pub tool_calls: Option<Vec<ToolCall>>,
    pub tool_call_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum MessageContent {
    Text(String),
    Parts(Vec<ContentPart>),
}

impl MessageContent {
    pub fn as_text(&self) -> Option<&str> {
        match self {
            MessageContent::Text(s) => Some(s),
            MessageContent::Parts(_) => None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Attachment {
    #[serde(rename = "type")]
    pub attachment_type: String,
    pub path: Option<String>,
    pub url: Option<String>,
    pub data: Option<String>,
    pub mime_type: Option<String>,
}

// =============================================================================
// Tool Types
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FunctionCall {
    pub name: String,
    pub arguments: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    pub id: String,
    #[serde(rename = "type", default = "default_function_type")]
    pub call_type: String,
    pub function: FunctionCall,
}

fn default_function_type() -> String {
    "function".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolInvocation {
    pub name: String,
    pub arguments: HashMap<String, serde_json::Value>,
    pub call_id: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ToolResultType {
    Success,
    Failure,
    Rejected,
    Denied,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    pub result_type: Option<ToolResultType>,
    pub text_result_for_llm: Option<String>,
    pub binary_result: Option<Vec<u8>>,
    pub session_log: Option<String>,
}

impl Default for ToolResult {
    fn default() -> Self {
        Self {
            result_type: Some(ToolResultType::Success),
            text_result_for_llm: None,
            binary_result: None,
            session_log: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tool {
    pub name: String,
    pub description: String,
    pub parameters: Option<serde_json::Value>,
}

// =============================================================================
// Generation Config Types
// =============================================================================

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GenerationConfig {
    #[serde(default = "default_temperature")]
    pub temperature: f64,
    pub max_output_tokens: Option<u32>,
    pub top_p: Option<f64>,
    pub top_k: Option<u32>,
    pub stop_sequences: Option<Vec<String>>,
}

fn default_temperature() -> f64 {
    0.7
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ThinkingConfig {
    #[serde(default = "default_true")]
    pub include_thoughts: bool,
    pub thinking_budget: Option<u32>,
}

// =============================================================================
// Request/Response Types
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageOptions {
    pub prompt: String,
    pub attachments: Option<Vec<Attachment>>,
    pub context: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LLMUsage {
    #[serde(default)]
    pub prompt_tokens: u64,
    #[serde(default)]
    pub completion_tokens: u64,
    #[serde(default)]
    pub total_tokens: u64,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LLMChunk {
    #[serde(default)]
    pub content: String,
    pub reasoning_content: Option<String>,
    pub tool_calls: Option<Vec<ToolCall>>,
    pub usage: Option<LLMUsage>,
    pub finish_reason: Option<String>,
}

// =============================================================================
// Session Types
// =============================================================================

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SessionConfig {
    pub session_id: Option<String>,
    pub model: Option<String>,
    pub tools: Option<Vec<Tool>>,
    pub system_message: Option<String>,
    pub generation_config: Option<GenerationConfig>,
    pub thinking_config: Option<ThinkingConfig>,
    pub streaming: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionMetadata {
    pub session_id: String,
    pub start_time: String,
    pub modified_time: String,
    pub summary: Option<String>,
    pub model: String,
}

// =============================================================================
// Client Options Types
// =============================================================================

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GeminiClientOptions {
    pub oauth_path: Option<String>,
    pub client_id: Option<String>,
    pub client_secret: Option<String>,
    pub base_url: Option<String>,
    pub timeout: Option<f64>,
    pub log_level: Option<LogLevel>,
    pub auto_refresh: Option<bool>,
}

// =============================================================================
// Event Types
// =============================================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EventType {
    #[serde(rename = "session.created")]
    SessionCreated,
    #[serde(rename = "session.idle")]
    SessionIdle,
    #[serde(rename = "session.error")]
    SessionError,
    #[serde(rename = "assistant.message")]
    AssistantMessage,
    #[serde(rename = "assistant.message_delta")]
    AssistantMessageDelta,
    #[serde(rename = "assistant.reasoning")]
    AssistantReasoning,
    #[serde(rename = "assistant.reasoning_delta")]
    AssistantReasoningDelta,
    #[serde(rename = "tool.call")]
    ToolCall,
    #[serde(rename = "tool.result")]
    ToolResult,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionEvent {
    pub event_type: EventType,
    pub data: serde_json::Value,
    pub session_id: String,
}

// =============================================================================
// Constants
// =============================================================================

pub const GEMINI_OAUTH_REDIRECT_URI: &str = "http://localhost:45289";
pub const GEMINI_OAUTH_BASE_URL: &str = "https://accounts.google.com";
pub const GEMINI_OAUTH_TOKEN_ENDPOINT: &str = "https://accounts.google.com/o/oauth2/token";
pub const GEMINI_OAUTH_AUTH_ENDPOINT: &str = "https://accounts.google.com/o/oauth2/v2/auth";

pub const GEMINI_OAUTH_CLIENT_ID: &str =
    "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com";
pub const GEMINI_OAUTH_CLIENT_SECRET: &str = "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";

pub const GEMINI_OAUTH_SCOPES: &[&str] = &[
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
];

pub const GEMINI_CODE_ASSIST_ENDPOINT: &str = "https://cloudcode-pa.googleapis.com";
pub const GEMINI_CODE_ASSIST_API_VERSION: &str = "v1internal";

pub const GEMINI_DIR: &str = ".gemini";
pub const GEMINI_CREDENTIAL_FILENAME: &str = "oauth_creds.json";
pub const GEMINI_ENV_FILENAME: &str = ".env";

pub const TOKEN_REFRESH_BUFFER_MS: u64 = 5 * 60 * 1000;

pub const HTTP_OK: u16 = 200;
pub const HTTP_UNAUTHORIZED: u16 = 401;
pub const HTTP_FORBIDDEN: u16 = 403;

/// Get available Gemini CLI models
pub fn get_gemini_cli_models() -> HashMap<String, GeminiModelInfo> {
    let mut models = HashMap::new();

    models.insert(
        "gemini-3-pro-preview".to_string(),
        GeminiModelInfo {
            id: "gemini-3-pro-preview".to_string(),
            name: "Gemini 3 Pro Preview".to_string(),
            context_window: 1_000_000,
            max_output: 65_536,
            input_price: 0.0,
            output_price: 0.0,
            supports_native_tools: true,
            supports_thinking: true,
        },
    );

    models.insert(
        "gemini-3-flash-preview".to_string(),
        GeminiModelInfo {
            id: "gemini-3-flash-preview".to_string(),
            name: "Gemini 3 Flash Preview".to_string(),
            context_window: 1_000_000,
            max_output: 65_536,
            input_price: 0.0,
            output_price: 0.0,
            supports_native_tools: true,
            supports_thinking: true,
        },
    );

    models.insert(
        "gemini-2.5-pro".to_string(),
        GeminiModelInfo {
            id: "gemini-2.5-pro".to_string(),
            name: "Gemini 2.5 Pro".to_string(),
            context_window: 1_048_576,
            max_output: 65_536,
            input_price: 0.0,
            output_price: 0.0,
            supports_native_tools: true,
            supports_thinking: true,
        },
    );

    models.insert(
        "gemini-2.5-flash".to_string(),
        GeminiModelInfo {
            id: "gemini-2.5-flash".to_string(),
            name: "Gemini 2.5 Flash".to_string(),
            context_window: 1_048_576,
            max_output: 65_536,
            input_price: 0.0,
            output_price: 0.0,
            supports_native_tools: true,
            supports_thinking: true,
        },
    );

    models.insert(
        "gemini-2.5-flash-lite".to_string(),
        GeminiModelInfo {
            id: "gemini-2.5-flash-lite".to_string(),
            name: "Gemini 2.5 Flash Lite".to_string(),
            context_window: 1_000_000,
            max_output: 32_768,
            input_price: 0.0,
            output_price: 0.0,
            supports_native_tools: true,
            supports_thinking: false,
        },
    );

    models.insert(
        "auto".to_string(),
        GeminiModelInfo {
            id: "auto".to_string(),
            name: "Auto (Default)".to_string(),
            context_window: 1_048_576,
            max_output: 65_536,
            input_price: 0.0,
            output_price: 0.0,
            supports_native_tools: true,
            supports_thinking: true,
        },
    );

    models
}

/// Get the path to Gemini CLI OAuth credentials file
pub fn get_geminicli_credential_path(custom_path: Option<&str>) -> String {
    if let Some(path) = custom_path {
        return path.to_string();
    }

    let home = dirs::home_dir().unwrap_or_default();
    home.join(GEMINI_DIR)
        .join(GEMINI_CREDENTIAL_FILENAME)
        .to_string_lossy()
        .to_string()
}

/// Get the path to Gemini CLI environment file
pub fn get_geminicli_env_path(custom_path: Option<&str>) -> String {
    if let Some(path) = custom_path {
        return path.to_string();
    }

    let home = dirs::home_dir().unwrap_or_default();
    home.join(GEMINI_DIR)
        .join(GEMINI_ENV_FILENAME)
        .to_string_lossy()
        .to_string()
}
