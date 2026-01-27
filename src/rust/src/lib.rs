//! GeminiSDK - Rust SDK for Google Gemini CLI / Code Assist API
//!
//! This crate provides a full-featured client for the Google Gemini API
//! with support for:
//! - OAuth authentication (using Gemini CLI credentials)
//! - Session-based conversations
//! - Streaming responses (SSE)
//! - Tool/function calling
//! - Thinking/reasoning mode
//!
//! ## Quick Start
//!
//! ```rust,no_run
//! use geminisdk::{GeminiClient, SessionConfig, MessageOptions};
//!
//! #[tokio::main]
//! async fn main() -> Result<(), Box<dyn std::error::Error>> {
//!     // Create and start client
//!     let client = GeminiClient::with_defaults();
//!     client.start().await?;
//!
//!     // Create a session
//!     let session = client.create_session(SessionConfig {
//!         model: Some("gemini-2.5-pro".to_string()),
//!         streaming: Some(true),
//!         ..Default::default()
//!     }).await?;
//!
//!     // Send a message
//!     let response = session.send_and_wait(MessageOptions {
//!         prompt: "Hello, Gemini!".to_string(),
//!         attachments: None,
//!         context: None,
//!     }).await?;
//!
//!     println!("Response: {:?}", response);
//!
//!     client.close().await?;
//!     Ok(())
//! }
//! ```

pub mod auth;
pub mod backend;
pub mod client;
pub mod errors;
pub mod session;
pub mod tools;
pub mod types;

// Re-exports for convenience
pub use auth::GeminiOAuthManager;
pub use backend::{BackendOptions, GeminiBackend};
pub use client::GeminiClient;
pub use errors::{GeminiSDKError, Result};
pub use session::GeminiSession;
pub use tools::{
    create_tool, failure_result, rejected_result, success_result, ToolParameters, ToolRegistry,
};
pub use types::{
    // Constants
    get_geminicli_credential_path,
    get_geminicli_env_path,
    get_gemini_cli_models,
    GEMINI_CODE_ASSIST_API_VERSION,
    GEMINI_CODE_ASSIST_ENDPOINT,
    GEMINI_CREDENTIAL_FILENAME,
    GEMINI_DIR,
    GEMINI_ENV_FILENAME,
    GEMINI_OAUTH_AUTH_ENDPOINT,
    GEMINI_OAUTH_BASE_URL,
    GEMINI_OAUTH_CLIENT_ID,
    GEMINI_OAUTH_CLIENT_SECRET,
    GEMINI_OAUTH_REDIRECT_URI,
    GEMINI_OAUTH_SCOPES,
    GEMINI_OAUTH_TOKEN_ENDPOINT,
    // Types
    Attachment,
    ConnectionState,
    ContentPart,
    EventType,
    FunctionCall,
    GeminiClientOptions,
    GeminiModelInfo,
    GeminiOAuthCredentials,
    GenerationConfig,
    LLMChunk,
    LLMUsage,
    LogLevel,
    Message,
    MessageContent,
    MessageOptions,
    ModelCapabilities,
    ModelInfo,
    ModelLimits,
    ModelSupports,
    ModelVisionLimits,
    Role,
    SessionConfig,
    SessionEvent,
    SessionMetadata,
    ThinkingConfig,
    Tool,
    ToolCall,
    ToolInvocation,
    ToolResult,
    ToolResultType,
};
