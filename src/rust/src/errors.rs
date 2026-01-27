//! Custom errors for GeminiSDK Rust

use std::collections::HashMap;
use thiserror::Error;

/// Base error type for all GeminiSDK errors
#[derive(Error, Debug)]
pub enum GeminiSDKError {
    #[error("Authentication error: {message}")]
    Authentication {
        message: String,
        details: HashMap<String, String>,
    },

    #[error("Credentials not found at {credential_path}")]
    CredentialsNotFound { credential_path: String },

    #[error("Token refresh failed: {message}")]
    TokenRefresh {
        message: String,
        status_code: Option<u16>,
        response_body: Option<String>,
    },

    #[error("Token expired")]
    TokenExpired,

    #[error("Connection error: {message}")]
    Connection {
        message: String,
        endpoint: Option<String>,
    },

    #[error("API error: {message} (status: {status_code})")]
    Api {
        message: String,
        status_code: u16,
        response_body: Option<String>,
        endpoint: Option<String>,
    },

    #[error("Rate limit exceeded")]
    RateLimit {
        message: String,
        status_code: u16,
        retry_after: Option<u64>,
        response_body: Option<String>,
    },

    #[error("Quota exceeded")]
    QuotaExceeded {
        message: String,
        status_code: u16,
        reset_time: Option<String>,
        response_body: Option<String>,
    },

    #[error("Permission denied: {message}")]
    PermissionDenied {
        message: String,
        status_code: u16,
        response_body: Option<String>,
    },

    #[error("Resource not found: {resource:?}")]
    NotFound {
        message: String,
        status_code: u16,
        resource: Option<String>,
        response_body: Option<String>,
    },

    #[error("Session error: {message}")]
    Session {
        message: String,
        session_id: Option<String>,
    },

    #[error("Session not found: {session_id}")]
    SessionNotFound { session_id: String },

    #[error("Session is closed")]
    SessionClosed { session_id: Option<String> },

    #[error("Tool error: {message}")]
    Tool {
        message: String,
        tool_name: Option<String>,
    },

    #[error("Tool not found: {tool_name}")]
    ToolNotFound { tool_name: String },

    #[error("Tool execution error: {message}")]
    ToolExecution {
        message: String,
        tool_name: String,
        original_error: Option<String>,
    },

    #[error("Validation error: {message}")]
    Validation {
        message: String,
        field: Option<String>,
        value: Option<String>,
    },

    #[error("Configuration error: {message}")]
    Configuration {
        message: String,
        config_key: Option<String>,
    },

    #[error("Stream error: {message}")]
    Stream {
        message: String,
        partial_content: Option<String>,
    },

    #[error("Operation cancelled")]
    Cancellation { message: String },

    #[error("Operation timed out")]
    Timeout {
        message: String,
        timeout: Option<f64>,
    },

    #[error("Onboarding error: {message}")]
    Onboarding {
        message: String,
        tier_id: Option<String>,
    },

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),
}

impl GeminiSDKError {
    pub fn authentication(message: impl Into<String>) -> Self {
        Self::Authentication {
            message: message.into(),
            details: HashMap::new(),
        }
    }

    pub fn credentials_not_found(path: impl Into<String>) -> Self {
        Self::CredentialsNotFound {
            credential_path: path.into(),
        }
    }

    pub fn token_refresh(message: impl Into<String>) -> Self {
        Self::TokenRefresh {
            message: message.into(),
            status_code: None,
            response_body: None,
        }
    }

    pub fn api_error(message: impl Into<String>, status_code: u16) -> Self {
        Self::Api {
            message: message.into(),
            status_code,
            response_body: None,
            endpoint: None,
        }
    }

    pub fn rate_limit(message: impl Into<String>) -> Self {
        Self::RateLimit {
            message: message.into(),
            status_code: 429,
            retry_after: None,
            response_body: None,
        }
    }

    pub fn permission_denied(message: impl Into<String>) -> Self {
        Self::PermissionDenied {
            message: message.into(),
            status_code: 403,
            response_body: None,
        }
    }

    pub fn session_not_found(session_id: impl Into<String>) -> Self {
        Self::SessionNotFound {
            session_id: session_id.into(),
        }
    }

    pub fn session_closed(session_id: Option<String>) -> Self {
        Self::SessionClosed { session_id }
    }

    pub fn tool_not_found(tool_name: impl Into<String>) -> Self {
        Self::ToolNotFound {
            tool_name: tool_name.into(),
        }
    }

    pub fn tool_execution(message: impl Into<String>, tool_name: impl Into<String>) -> Self {
        Self::ToolExecution {
            message: message.into(),
            tool_name: tool_name.into(),
            original_error: None,
        }
    }

    pub fn configuration(message: impl Into<String>) -> Self {
        Self::Configuration {
            message: message.into(),
            config_key: None,
        }
    }

    pub fn stream(message: impl Into<String>) -> Self {
        Self::Stream {
            message: message.into(),
            partial_content: None,
        }
    }

    pub fn onboarding(message: impl Into<String>) -> Self {
        Self::Onboarding {
            message: message.into(),
            tier_id: None,
        }
    }
}

pub type Result<T> = std::result::Result<T, GeminiSDKError>;
