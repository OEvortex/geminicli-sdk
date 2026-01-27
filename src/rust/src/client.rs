//! GeminiSDK Client - Main entry point for the Gemini SDK.

use crate::auth::GeminiOAuthManager;
use crate::backend::{BackendOptions, GeminiBackend};
use crate::errors::{GeminiSDKError, Result};
use crate::session::GeminiSession;
use crate::types::{
    get_gemini_cli_models, ConnectionState, GeminiClientOptions, ModelCapabilities, ModelInfo,
    ModelLimits, ModelSupports, SessionConfig, SessionMetadata,
};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use uuid::Uuid;

pub struct GeminiClient {
    options: GeminiClientOptions,
    state: Arc<Mutex<ConnectionState>>,
    backend: Arc<Mutex<Option<Arc<GeminiBackend>>>>,
    oauth_manager: Arc<Mutex<Option<GeminiOAuthManager>>>,
    sessions: Arc<Mutex<HashMap<String, Arc<GeminiSession>>>>,
    started: Arc<Mutex<bool>>,
}

impl GeminiClient {
    pub fn new(options: GeminiClientOptions) -> Self {
        Self {
            options,
            state: Arc::new(Mutex::new(ConnectionState::Disconnected)),
            backend: Arc::new(Mutex::new(None)),
            oauth_manager: Arc::new(Mutex::new(None)),
            sessions: Arc::new(Mutex::new(HashMap::new())),
            started: Arc::new(Mutex::new(false)),
        }
    }

    pub fn with_defaults() -> Self {
        Self::new(GeminiClientOptions::default())
    }

    pub async fn state(&self) -> ConnectionState {
        *self.state.lock().await
    }

    pub async fn start(&self) -> Result<()> {
        let mut started = self.started.lock().await;
        if *started {
            return Ok(());
        }

        {
            let mut state = self.state.lock().await;
            *state = ConnectionState::Connecting;
        }

        let oauth_manager = GeminiOAuthManager::new(
            self.options.oauth_path.clone(),
            self.options.client_id.clone(),
            self.options.client_secret.clone(),
        );

        let backend = GeminiBackend::new(BackendOptions {
            timeout: self.options.timeout.map(|t| std::time::Duration::from_secs_f64(t)),
            oauth_path: self.options.oauth_path.clone(),
            client_id: self.options.client_id.clone(),
            client_secret: self.options.client_secret.clone(),
        });

        // Verify authentication
        oauth_manager.ensure_authenticated(false).await?;

        {
            let mut oauth = self.oauth_manager.lock().await;
            *oauth = Some(oauth_manager);
        }

        {
            let mut be = self.backend.lock().await;
            *be = Some(Arc::new(backend));
        }

        {
            let mut state = self.state.lock().await;
            *state = ConnectionState::Connected;
        }

        *started = true;

        // Start auto-refresh if enabled
        if self.options.auto_refresh.unwrap_or(true) {
            self.start_auto_refresh();
        }

        Ok(())
    }

    fn start_auto_refresh(&self) {
        let oauth_manager = self.oauth_manager.clone();

        tokio::spawn(async move {
            loop {
                tokio::time::sleep(std::time::Duration::from_secs(30)).await;

                if let Some(ref manager) = *oauth_manager.lock().await {
                    let _ = manager.ensure_authenticated(false).await;
                }
            }
        });
    }

    pub async fn stop(&self) -> Result<()> {
        // Destroy all sessions
        let sessions: Vec<Arc<GeminiSession>> = {
            let mut sessions_guard = self.sessions.lock().await;
            let sessions: Vec<_> = sessions_guard.values().cloned().collect();
            sessions_guard.clear();
            sessions
        };

        for session in sessions {
            session.destroy().await;
        }

        {
            let mut be = self.backend.lock().await;
            *be = None;
        }

        {
            let mut oauth = self.oauth_manager.lock().await;
            *oauth = None;
        }

        {
            let mut state = self.state.lock().await;
            *state = ConnectionState::Disconnected;
        }

        {
            let mut started = self.started.lock().await;
            *started = false;
        }

        Ok(())
    }

    pub async fn close(&self) -> Result<()> {
        self.stop().await
    }

    pub async fn create_session(&self, config: SessionConfig) -> Result<Arc<GeminiSession>> {
        if !*self.started.lock().await {
            self.start().await?;
        }

        let backend = {
            let be = self.backend.lock().await;
            be.as_ref()
                .ok_or_else(|| GeminiSDKError::configuration("Client not connected"))?
                .clone()
        };

        let session_id = config.session_id.unwrap_or_else(|| Uuid::new_v4().to_string());
        let model = config.model.unwrap_or_else(|| "gemini-2.5-pro".to_string());

        let session = Arc::new(GeminiSession::new(
            session_id.clone(),
            model,
            backend,
            config.tools.unwrap_or_default(),
            config.system_message,
            config.generation_config,
            config.thinking_config,
            config.streaming.unwrap_or(true),
        ));

        {
            let mut sessions = self.sessions.lock().await;
            sessions.insert(session_id, session.clone());
        }

        Ok(session)
    }

    pub async fn get_session(&self, session_id: &str) -> Result<Arc<GeminiSession>> {
        let sessions = self.sessions.lock().await;
        sessions
            .get(session_id)
            .cloned()
            .ok_or_else(|| GeminiSDKError::session_not_found(session_id))
    }

    pub async fn list_sessions(&self) -> Vec<SessionMetadata> {
        let sessions = self.sessions.lock().await;
        let mut result = Vec::new();

        for session in sessions.values() {
            result.push(SessionMetadata {
                session_id: session.session_id().to_string(),
                start_time: session.start_time().to_rfc3339(),
                modified_time: session.modified_time().await.to_rfc3339(),
                summary: None,
                model: session.model().to_string(),
            });
        }

        result
    }

    pub async fn delete_session(&self, session_id: &str) -> Result<()> {
        let session = {
            let mut sessions = self.sessions.lock().await;
            sessions.remove(session_id)
        };

        if let Some(session) = session {
            session.destroy().await;
        }

        Ok(())
    }

    pub async fn get_auth_status(&self) -> HashMap<String, serde_json::Value> {
        let mut status = HashMap::new();

        let oauth = self.oauth_manager.lock().await;
        if let Some(ref manager) = *oauth {
            if let Ok(credentials) = manager.get_credentials().await {
                status.insert("authenticated".to_string(), serde_json::json!(true));
                status.insert(
                    "token_type".to_string(),
                    serde_json::json!(credentials.token_type),
                );
                status.insert(
                    "expires_at".to_string(),
                    serde_json::json!(credentials.expiry_date),
                );
                return status;
            }
        }

        status.insert("authenticated".to_string(), serde_json::json!(false));
        status
    }

    pub async fn list_models(&self) -> Vec<ModelInfo> {
        let models = get_gemini_cli_models();
        models
            .into_iter()
            .map(|(id, info)| ModelInfo {
                id,
                name: info.name,
                capabilities: ModelCapabilities {
                    supports: ModelSupports {
                        vision: false,
                        tools: info.supports_native_tools,
                        thinking: info.supports_thinking,
                    },
                    limits: ModelLimits {
                        max_prompt_tokens: Some(info.context_window),
                        max_context_window_tokens: Some(info.context_window),
                        vision: None,
                    },
                },
            })
            .collect()
    }

    pub async fn refresh_auth(&self) -> Result<()> {
        let oauth = self.oauth_manager.lock().await;
        if let Some(ref manager) = *oauth {
            manager.ensure_authenticated(true).await?;
        }
        Ok(())
    }
}
