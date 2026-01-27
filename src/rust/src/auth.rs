//! OAuth authentication for Gemini CLI / Code Assist API.

use crate::errors::{GeminiSDKError, Result};
use crate::types::{
    get_geminicli_credential_path, get_geminicli_env_path, GeminiOAuthCredentials,
    GEMINI_CODE_ASSIST_API_VERSION, GEMINI_CODE_ASSIST_ENDPOINT, GEMINI_OAUTH_CLIENT_ID,
    GEMINI_OAUTH_CLIENT_SECRET, GEMINI_OAUTH_SCOPES, GEMINI_OAUTH_TOKEN_ENDPOINT,
    HTTP_OK, TOKEN_REFRESH_BUFFER_MS,
};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::Mutex;

#[derive(Debug, Serialize)]
struct TokenRefreshRequest<'a> {
    grant_type: &'static str,
    refresh_token: &'a str,
    client_id: &'a str,
    client_secret: &'a str,
    scope: String,
}

#[derive(Debug, Deserialize)]
struct TokenResponse {
    access_token: String,
    token_type: Option<String>,
    refresh_token: Option<String>,
    expires_in: Option<u64>,
    error: Option<String>,
    error_description: Option<String>,
}

pub struct GeminiOAuthManager {
    oauth_path: Option<String>,
    client_id: String,
    client_secret: String,
    credentials: Arc<Mutex<Option<GeminiOAuthCredentials>>>,
    project_id: Arc<Mutex<Option<String>>>,
    http_client: Client,
}

impl GeminiOAuthManager {
    pub fn new(
        oauth_path: Option<String>,
        client_id: Option<String>,
        client_secret: Option<String>,
    ) -> Self {
        Self {
            oauth_path,
            client_id: client_id.unwrap_or_else(|| GEMINI_OAUTH_CLIENT_ID.to_string()),
            client_secret: client_secret.unwrap_or_else(|| GEMINI_OAUTH_CLIENT_SECRET.to_string()),
            credentials: Arc::new(Mutex::new(None)),
            project_id: Arc::new(Mutex::new(None)),
            http_client: Client::new(),
        }
    }

    fn get_credential_path(&self) -> String {
        get_geminicli_credential_path(self.oauth_path.as_deref())
    }

    fn load_cached_credentials(&self) -> Result<GeminiOAuthCredentials> {
        let key_file = self.get_credential_path();

        if !Path::new(&key_file).exists() {
            return Err(GeminiSDKError::credentials_not_found(&key_file));
        }

        let content = fs::read_to_string(&key_file)?;
        let creds: GeminiOAuthCredentials = serde_json::from_str(&content)?;
        Ok(creds)
    }

    fn save_credentials(&self, credentials: &GeminiOAuthCredentials) -> Result<()> {
        let key_file = self.get_credential_path();
        let parent = Path::new(&key_file).parent();

        if let Some(dir) = parent {
            fs::create_dir_all(dir)?;
        }

        let content = serde_json::to_string_pretty(credentials)?;
        fs::write(&key_file, content)?;
        Ok(())
    }

    async fn refresh_access_token(
        &self,
        credentials: &GeminiOAuthCredentials,
    ) -> Result<GeminiOAuthCredentials> {
        if credentials.refresh_token.is_empty() {
            return Err(GeminiSDKError::token_refresh(
                "No refresh token available in credentials.",
            ));
        }

        let scope = GEMINI_OAUTH_SCOPES.join(" ");
        let params = [
            ("grant_type", "refresh_token"),
            ("refresh_token", &credentials.refresh_token),
            ("client_id", &self.client_id),
            ("client_secret", &self.client_secret),
            ("scope", &scope),
        ];

        let response = self
            .http_client
            .post(GEMINI_OAUTH_TOKEN_ENDPOINT)
            .header("Content-Type", "application/x-www-form-urlencoded")
            .header("Accept", "application/json")
            .header(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            .form(&params)
            .send()
            .await?;

        let status = response.status();
        if status.as_u16() != HTTP_OK {
            let body = response.text().await.unwrap_or_default();
            return Err(GeminiSDKError::TokenRefresh {
                message: format!("Token refresh failed: {} {}", status.as_u16(), status),
                status_code: Some(status.as_u16()),
                response_body: Some(body),
            });
        }

        let token_data: TokenResponse = response.json().await?;

        if let Some(error) = token_data.error {
            return Err(GeminiSDKError::token_refresh(format!(
                "{} - {}",
                error,
                token_data.error_description.unwrap_or_default()
            )));
        }

        let now_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64;

        let new_credentials = GeminiOAuthCredentials {
            access_token: token_data.access_token,
            refresh_token: token_data
                .refresh_token
                .unwrap_or_else(|| credentials.refresh_token.clone()),
            token_type: token_data.token_type.unwrap_or_else(|| "Bearer".to_string()),
            expiry_date: now_ms + token_data.expires_in.unwrap_or(3600) * 1000,
        };

        self.save_credentials(&new_credentials)?;
        Ok(new_credentials)
    }

    fn is_token_valid(&self, credentials: &GeminiOAuthCredentials) -> bool {
        if credentials.expiry_date == 0 {
            return false;
        }

        let now_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64;

        now_ms < credentials.expiry_date - TOKEN_REFRESH_BUFFER_MS
    }

    pub fn invalidate_credentials(&self) {
        if let Ok(mut creds) = self.credentials.try_lock() {
            *creds = None;
        }
    }

    pub async fn ensure_authenticated(&self, force_refresh: bool) -> Result<String> {
        let mut creds_guard = self.credentials.lock().await;

        if creds_guard.is_none() {
            *creds_guard = Some(self.load_cached_credentials()?);
        }

        let creds = creds_guard.as_ref().unwrap();

        if force_refresh || !self.is_token_valid(creds) {
            let new_creds = self.refresh_access_token(creds).await?;
            let token = new_creds.access_token.clone();
            *creds_guard = Some(new_creds);
            return Ok(token);
        }

        Ok(creds.access_token.clone())
    }

    pub async fn get_credentials(&self) -> Result<GeminiOAuthCredentials> {
        self.ensure_authenticated(false).await?;
        let creds_guard = self.credentials.lock().await;
        Ok(creds_guard.as_ref().unwrap().clone())
    }

    pub fn get_api_endpoint(&self) -> String {
        format!(
            "{}/{}",
            GEMINI_CODE_ASSIST_ENDPOINT, GEMINI_CODE_ASSIST_API_VERSION
        )
    }

    pub fn get_project_id(&self) -> Option<String> {
        if let Ok(project_id) = std::env::var("GOOGLE_CLOUD_PROJECT") {
            return Some(project_id);
        }

        let env_file = get_geminicli_env_path(None);
        if let Ok(content) = fs::read_to_string(env_file) {
            for line in content.lines() {
                let trimmed = line.trim();
                if trimmed.starts_with("GOOGLE_CLOUD_PROJECT=") {
                    return Some(
                        trimmed
                            .split('=')
                            .nth(1)
                            .unwrap_or("")
                            .trim()
                            .trim_matches(|c| c == '"' || c == '\'')
                            .to_string(),
                    );
                }
            }
        }

        if let Ok(guard) = self.project_id.try_lock() {
            return guard.clone();
        }

        None
    }

    pub fn set_project_id(&self, project_id: String) {
        if let Ok(mut guard) = self.project_id.try_lock() {
            *guard = Some(project_id);
        }
    }
}
