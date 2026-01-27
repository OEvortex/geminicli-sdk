//! Backend for Gemini CLI / Google Code Assist API.

use crate::auth::GeminiOAuthManager;
use crate::errors::{GeminiSDKError, Result};
use crate::types::{
    FunctionCall, GenerationConfig, LLMChunk, LLMUsage, Message, MessageContent, Role,
    ThinkingConfig, Tool, ToolCall, HTTP_FORBIDDEN, HTTP_UNAUTHORIZED,
};
use futures::stream::{Stream, StreamExt};
use reqwest::Client;
use serde_json::{json, Value};
use std::pin::Pin;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Mutex;
use uuid::Uuid;

const ONBOARD_MAX_RETRIES: u32 = 30;
const ONBOARD_SLEEP_SECONDS: u64 = 2;

#[derive(Debug, Clone)]
pub struct BackendOptions {
    pub timeout: Option<Duration>,
    pub oauth_path: Option<String>,
    pub client_id: Option<String>,
    pub client_secret: Option<String>,
}

impl Default for BackendOptions {
    fn default() -> Self {
        Self {
            timeout: Some(Duration::from_secs(720)),
            oauth_path: None,
            client_id: None,
            client_secret: None,
        }
    }
}

pub struct GeminiBackend {
    timeout: Duration,
    oauth_manager: GeminiOAuthManager,
    project_id: Arc<Mutex<Option<String>>>,
    http_client: Client,
}

impl GeminiBackend {
    pub fn new(options: BackendOptions) -> Self {
        let timeout = options.timeout.unwrap_or(Duration::from_secs(720));
        Self {
            timeout,
            oauth_manager: GeminiOAuthManager::new(
                options.oauth_path,
                options.client_id,
                options.client_secret,
            ),
            project_id: Arc::new(Mutex::new(None)),
            http_client: Client::builder()
                .timeout(timeout)
                .build()
                .unwrap_or_default(),
        }
    }

    async fn get_auth_headers(&self, force_refresh: bool) -> Result<Vec<(String, String)>> {
        let access_token = self.oauth_manager.ensure_authenticated(force_refresh).await?;
        Ok(vec![
            ("Content-Type".to_string(), "application/json".to_string()),
            ("Authorization".to_string(), format!("Bearer {}", access_token)),
        ])
    }

    fn prepare_messages(&self, messages: &[Message]) -> Vec<Value> {
        let mut result = Vec::new();

        for msg in messages {
            let role = match msg.role {
                Role::Assistant => "model",
                _ => "user",
            };

            let mut content_parts: Vec<Value> = Vec::new();

            match &msg.content {
                MessageContent::Text(text) => {
                    content_parts.push(json!({"text": text}));
                }
                MessageContent::Parts(parts) => {
                    for part in parts {
                        if let Some(text) = &part.text {
                            content_parts.push(json!({"text": text}));
                        }
                        if let Some(data) = &part.image_data {
                            if let Some(mime) = &part.image_mime_type {
                                let b64 = base64_encode(data);
                                content_parts.push(json!({
                                    "inlineData": {
                                        "mimeType": mime,
                                        "data": b64
                                    }
                                }));
                            }
                        }
                    }
                }
            }

            if let Some(tool_calls) = &msg.tool_calls {
                for tc in tool_calls {
                    content_parts.push(json!({
                        "functionCall": {
                            "name": tc.function.name,
                            "args": tc.function.arguments
                        }
                    }));
                }
            }

            if let Some(_tool_call_id) = &msg.tool_call_id {
                let response_content = match &msg.content {
                    MessageContent::Text(s) => json!({"result": s}),
                    MessageContent::Parts(_) => json!({"result": ""}),
                };
                content_parts.push(json!({
                    "functionResponse": {
                        "name": msg.name.as_deref().unwrap_or(""),
                        "response": response_content
                    }
                }));
            }

            if !content_parts.is_empty() {
                result.push(json!({
                    "role": role,
                    "parts": content_parts
                }));
            }
        }

        result
    }

    fn prepare_tools(&self, tools: &[Tool]) -> Option<Vec<Value>> {
        if tools.is_empty() {
            return None;
        }

        let func_decls: Vec<Value> = tools
            .iter()
            .map(|tool| {
                let mut func_def = json!({
                    "name": tool.name,
                    "description": tool.description
                });

                if let Some(params) = &tool.parameters {
                    if let Some(obj) = func_def.as_object_mut() {
                        obj.insert(
                            "parameters".to_string(),
                            json!({
                                "type": "object",
                                "properties": params.get("properties").unwrap_or(&json!({})),
                                "required": params.get("required").unwrap_or(&json!([]))
                            }),
                        );
                    }
                }

                func_def
            })
            .collect();

        Some(vec![json!({"functionDeclarations": func_decls})])
    }

    async fn ensure_project_id(&self, access_token: &str) -> Result<String> {
        {
            let guard = self.project_id.lock().await;
            if let Some(ref pid) = *guard {
                return Ok(pid.clone());
            }
        }

        let env_project_id = self.oauth_manager.get_project_id();

        let client_metadata = json!({
            "ideType": "IDE_UNSPECIFIED",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI",
            "duetProject": env_project_id
        });

        let load_request = json!({
            "cloudaicompanionProject": env_project_id,
            "metadata": client_metadata
        });

        let url = format!("{}:loadCodeAssist", self.oauth_manager.get_api_endpoint());

        let response = self
            .http_client
            .post(&url)
            .header("Authorization", format!("Bearer {}", access_token))
            .header("Content-Type", "application/json")
            .json(&load_request)
            .send()
            .await?;

        if !response.status().is_success() {
            let body = response.text().await.unwrap_or_default();
            return Err(GeminiSDKError::api_error(
                format!("Gemini Code Assist access denied: {}", body),
                403,
            ));
        }

        let data: Value = response.json().await?;

        if data.get("currentTier").is_some() {
            let project_from_api = data
                .get("cloudaicompanionProject")
                .and_then(|v| v.as_str())
                .map(String::from);

            let project_id = project_from_api
                .or(env_project_id)
                .unwrap_or_default();

            let mut guard = self.project_id.lock().await;
            *guard = Some(project_id.clone());
            return Ok(project_id);
        }

        // Need to onboard
        let allowed_tiers = data
            .get("allowedTiers")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();

        let tier_id = allowed_tiers
            .iter()
            .find(|t| t.get("isDefault").and_then(|v| v.as_bool()).unwrap_or(false))
            .and_then(|t| t.get("id"))
            .and_then(|v| v.as_str())
            .unwrap_or("free-tier")
            .to_string();

        self.onboard_for_project(access_token, env_project_id, &tier_id)
            .await
    }

    async fn onboard_for_project(
        &self,
        access_token: &str,
        env_project_id: Option<String>,
        tier_id: &str,
    ) -> Result<String> {
        let client_metadata = json!({
            "ideType": "IDE_UNSPECIFIED",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI",
            "duetProject": env_project_id
        });

        let onboard_request = if tier_id == "free-tier" {
            json!({
                "tierId": tier_id,
                "cloudaicompanionProject": null,
                "metadata": client_metadata
            })
        } else {
            json!({
                "tierId": tier_id,
                "cloudaicompanionProject": env_project_id,
                "metadata": client_metadata
            })
        };

        let url = format!("{}:onboardUser", self.oauth_manager.get_api_endpoint());

        for _ in 0..ONBOARD_MAX_RETRIES {
            let response = self
                .http_client
                .post(&url)
                .header("Authorization", format!("Bearer {}", access_token))
                .header("Content-Type", "application/json")
                .json(&onboard_request)
                .send()
                .await?;

            if !response.status().is_success() {
                return Err(GeminiSDKError::onboarding("Onboard request failed"));
            }

            let lro_data: Value = response.json().await?;

            if lro_data.get("done").and_then(|v| v.as_bool()).unwrap_or(false) {
                if let Some(project_id) = lro_data
                    .get("response")
                    .and_then(|r| r.get("cloudaicompanionProject"))
                    .and_then(|c| c.get("id"))
                    .and_then(|v| v.as_str())
                {
                    let mut guard = self.project_id.lock().await;
                    *guard = Some(project_id.to_string());
                    return Ok(project_id.to_string());
                }
                break;
            }

            tokio::time::sleep(Duration::from_secs(ONBOARD_SLEEP_SECONDS)).await;
        }

        if tier_id == "free-tier" {
            let mut guard = self.project_id.lock().await;
            *guard = Some(String::new());
            return Ok(String::new());
        }

        Err(GeminiSDKError::Onboarding {
            message: "Failed to complete onboarding".to_string(),
            tier_id: Some(tier_id.to_string()),
        })
    }

    fn build_request_payload(
        &self,
        model: &str,
        messages: &[Message],
        generation_config: Option<&GenerationConfig>,
        thinking_config: Option<&ThinkingConfig>,
        tools: Option<&[Tool]>,
        project_id: &str,
    ) -> Value {
        let gen_config = generation_config.cloned().unwrap_or_default();

        let mut generation_cfg = json!({
            "temperature": gen_config.temperature
        });

        if let Some(tokens) = gen_config.max_output_tokens {
            generation_cfg["maxOutputTokens"] = json!(tokens);
        }
        if let Some(top_p) = gen_config.top_p {
            generation_cfg["topP"] = json!(top_p);
        }
        if let Some(top_k) = gen_config.top_k {
            generation_cfg["topK"] = json!(top_k);
        }
        if let Some(stops) = &gen_config.stop_sequences {
            generation_cfg["stopSequences"] = json!(stops);
        }

        if let Some(thinking) = thinking_config {
            if thinking.include_thoughts {
                let mut thinking_cfg = json!({"includeThoughts": true});
                if let Some(budget) = thinking.thinking_budget {
                    thinking_cfg["thinkingBudget"] = json!(budget);
                }
                generation_cfg["thinkingConfig"] = thinking_cfg;
            }
        }

        let mut request_body = json!({
            "contents": self.prepare_messages(messages),
            "generationConfig": generation_cfg
        });

        if let Some(tools) = tools {
            if let Some(prepared) = self.prepare_tools(tools) {
                request_body["tools"] = json!(prepared);
            }
        }

        let mut payload = json!({
            "model": model,
            "request": request_body
        });

        if !project_id.is_empty() {
            payload["project"] = json!(project_id);
        }

        payload
    }

    fn parse_completion_response(&self, data: &Value) -> LLMChunk {
        let response_data = data.get("response").unwrap_or(data);
        let candidates = response_data
            .get("candidates")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();

        if candidates.is_empty() {
            return LLMChunk::default();
        }

        let candidate = &candidates[0];
        let empty_obj = json!({});
        let content_obj = candidate.get("content").unwrap_or(&empty_obj);
        let parts = content_obj
            .get("parts")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();

        let mut text_content = String::new();
        let mut reasoning_content: Option<String> = None;
        let mut tool_calls: Vec<ToolCall> = Vec::new();

        for part in &parts {
            if let Some(text) = part.get("text").and_then(|v| v.as_str()) {
                text_content.push_str(text);
            }
            if let Some(thought) = part.get("thought").and_then(|v| v.as_str()) {
                reasoning_content = Some(thought.to_string());
            }
            if let Some(fc) = part.get("functionCall") {
                let name = fc.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let args = fc
                    .get("args")
                    .or_else(|| fc.get("arguments"))
                    .cloned()
                    .unwrap_or(json!({}));

                tool_calls.push(ToolCall {
                    id: Uuid::new_v4().to_string(),
                    call_type: "function".to_string(),
                    function: FunctionCall {
                        name: name.to_string(),
                        arguments: args,
                    },
                });
            }
        }

        let usage_data = data
            .get("usageMetadata")
            .or_else(|| response_data.get("usageMetadata"));

        let usage = usage_data.map(|u| LLMUsage {
            prompt_tokens: u
                .get("promptTokenCount")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            completion_tokens: u
                .get("candidatesTokenCount")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            total_tokens: u
                .get("totalTokenCount")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
        });

        LLMChunk {
            content: text_content,
            reasoning_content,
            tool_calls: if tool_calls.is_empty() {
                None
            } else {
                Some(tool_calls)
            },
            usage,
            finish_reason: candidate
                .get("finishReason")
                .and_then(|v| v.as_str())
                .map(String::from),
        }
    }

    pub async fn complete(
        &self,
        model: &str,
        messages: &[Message],
        generation_config: Option<&GenerationConfig>,
        thinking_config: Option<&ThinkingConfig>,
        tools: Option<&[Tool]>,
    ) -> Result<LLMChunk> {
        self.complete_impl(model, messages, generation_config, thinking_config, tools, 0)
            .await
    }

    fn complete_impl<'a>(
        &'a self,
        model: &'a str,
        messages: &'a [Message],
        generation_config: Option<&'a GenerationConfig>,
        thinking_config: Option<&'a ThinkingConfig>,
        tools: Option<&'a [Tool]>,
        retry_count: u32,
    ) -> Pin<Box<dyn std::future::Future<Output = Result<LLMChunk>> + Send + 'a>> {
        Box::pin(async move {
            let headers = self.get_auth_headers(retry_count > 0).await?;
            let access_token = headers
                .iter()
                .find(|(k, _)| k == "Authorization")
                .map(|(_, v)| v.replace("Bearer ", ""))
                .unwrap_or_default();

            let project_id = self.ensure_project_id(&access_token).await?;
            let url = format!("{}:generateContent", self.oauth_manager.get_api_endpoint());

            let payload = self.build_request_payload(
                model,
                messages,
                generation_config,
                thinking_config,
                tools,
                &project_id,
            );

            let mut request = self.http_client.post(&url);
            for (key, value) in &headers {
                request = request.header(key.as_str(), value.as_str());
            }

            let response = request.json(&payload).send().await?;
            let status = response.status().as_u16();

            if (status == HTTP_UNAUTHORIZED || status == HTTP_FORBIDDEN) && retry_count == 0 {
                self.oauth_manager.invalidate_credentials();
                return self
                    .complete_impl(model, messages, generation_config, thinking_config, tools, 1)
                    .await;
            }

            if !response.status().is_success() {
                let body = response.text().await.unwrap_or_default();
                return Err(self.handle_http_error(status, &body));
            }

            let data: Value = response.json().await?;
            Ok(self.parse_completion_response(&data))
        })
    }

    pub async fn complete_streaming(
        &self,
        model: &str,
        messages: &[Message],
        generation_config: Option<&GenerationConfig>,
        thinking_config: Option<&ThinkingConfig>,
        tools: Option<&[Tool]>,
    ) -> Result<Pin<Box<dyn Stream<Item = Result<LLMChunk>> + Send>>> {
        self.complete_streaming_impl(model, messages, generation_config, thinking_config, tools, 0)
            .await
    }

    fn complete_streaming_impl<'a>(
        &'a self,
        model: &'a str,
        messages: &'a [Message],
        generation_config: Option<&'a GenerationConfig>,
        thinking_config: Option<&'a ThinkingConfig>,
        tools: Option<&'a [Tool]>,
        retry_count: u32,
    ) -> Pin<Box<dyn std::future::Future<Output = Result<Pin<Box<dyn Stream<Item = Result<LLMChunk>> + Send>>>> + Send + 'a>> {
        Box::pin(async move {
            let headers = self.get_auth_headers(retry_count > 0).await?;
            let access_token = headers
                .iter()
                .find(|(k, _)| k == "Authorization")
                .map(|(_, v)| v.replace("Bearer ", ""))
                .unwrap_or_default();

            let project_id = self.ensure_project_id(&access_token).await?;
            let url = format!(
                "{}:streamGenerateContent?alt=sse",
                self.oauth_manager.get_api_endpoint()
            );

            let payload = self.build_request_payload(
                model,
                messages,
                generation_config,
                thinking_config,
                tools,
                &project_id,
            );

            let mut request = self.http_client.post(&url);
            for (key, value) in &headers {
                request = request.header(key.as_str(), value.as_str());
            }

            let response = request.json(&payload).send().await?;
            let status = response.status().as_u16();

            if (status == HTTP_UNAUTHORIZED || status == HTTP_FORBIDDEN) && retry_count == 0 {
                self.oauth_manager.invalidate_credentials();
                return self
                    .complete_streaming_impl(
                        model,
                        messages,
                        generation_config,
                        thinking_config,
                        tools,
                        1,
                    )
                    .await;
            }

            if !response.status().is_success() {
                let body = response.text().await.unwrap_or_default();
                return Err(self.handle_http_error(status, &body));
            }

            let bytes_stream = response.bytes_stream();
            let stream = bytes_stream.map(move |chunk_result| {
                match chunk_result {
                    Ok(bytes) => {
                        let text = String::from_utf8_lossy(&bytes);
                        let mut chunks = Vec::new();

                        for line in text.lines() {
                            let trimmed = line.trim();
                            if trimmed.is_empty() || trimmed.starts_with(':') {
                                continue;
                            }

                            if let Some(data) = trimmed.strip_prefix("data:") {
                                let data = data.trim();
                                if data == "[DONE]" {
                                    continue;
                                }

                                if let Ok(parsed) = serde_json::from_str::<Value>(data) {
                                    let chunk = parse_chunk(&parsed);
                                    chunks.push(Ok(chunk));
                                }
                            }
                        }

                        if chunks.is_empty() {
                            Ok(LLMChunk::default())
                        } else {
                            chunks.into_iter().next().unwrap_or(Ok(LLMChunk::default()))
                        }
                    }
                    Err(e) => Err(GeminiSDKError::stream(e.to_string())),
                }
            });

            Ok(Box::pin(stream) as Pin<Box<dyn Stream<Item = Result<LLMChunk>> + Send>>)
        })
    }

    fn handle_http_error(&self, status: u16, body: &str) -> GeminiSDKError {
        let error_msg = if let Ok(data) = serde_json::from_str::<Value>(body) {
            data.get("error")
                .and_then(|e| e.get("message"))
                .and_then(|m| m.as_str())
                .unwrap_or(body)
                .to_string()
        } else {
            body.to_string()
        };

        match status {
            429 => GeminiSDKError::rate_limit(format!("Rate limit exceeded: {}", error_msg)),
            403 => GeminiSDKError::permission_denied(format!("Permission denied: {}", error_msg)),
            _ => GeminiSDKError::api_error(format!("API error: {}", error_msg), status),
        }
    }

    pub async fn list_models(&self) -> Vec<String> {
        crate::types::get_gemini_cli_models()
            .keys()
            .cloned()
            .collect()
    }
}

fn parse_chunk(data: &Value) -> LLMChunk {
    let response_data = data.get("response").unwrap_or(data);
    let candidates = response_data
        .get("candidates")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    if candidates.is_empty() {
        return LLMChunk::default();
    }

    let candidate = &candidates[0];
    let empty_obj = json!({});
    let content_obj = candidate.get("content").unwrap_or(&empty_obj);
    let parts = content_obj
        .get("parts")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    let mut text_content = String::new();
    let mut reasoning_content: Option<String> = None;
    let mut tool_calls: Vec<ToolCall> = Vec::new();

    for part in &parts {
        if let Some(text) = part.get("text").and_then(|v| v.as_str()) {
            text_content.push_str(text);
        }
        if let Some(thought) = part.get("thought").and_then(|v| v.as_str()) {
            reasoning_content = Some(thought.to_string());
        }
        if let Some(fc) = part.get("functionCall") {
            let name = fc.get("name").and_then(|v| v.as_str()).unwrap_or("");
            let args = fc
                .get("args")
                .or_else(|| fc.get("arguments"))
                .cloned()
                .unwrap_or(json!({}));

            tool_calls.push(ToolCall {
                id: Uuid::new_v4().to_string(),
                call_type: "function".to_string(),
                function: FunctionCall {
                    name: name.to_string(),
                    arguments: args,
                },
            });
        }
    }

    let usage_data = data
        .get("usageMetadata")
        .or_else(|| response_data.get("usageMetadata"));

    let usage = usage_data.map(|u| LLMUsage {
        prompt_tokens: u
            .get("promptTokenCount")
            .and_then(|v| v.as_u64())
            .unwrap_or(0),
        completion_tokens: u
            .get("candidatesTokenCount")
            .and_then(|v| v.as_u64())
            .unwrap_or(0),
        total_tokens: u
            .get("totalTokenCount")
            .and_then(|v| v.as_u64())
            .unwrap_or(0),
    });

    LLMChunk {
        content: text_content,
        reasoning_content,
        tool_calls: if tool_calls.is_empty() {
            None
        } else {
            Some(tool_calls)
        },
        usage,
        finish_reason: candidate
            .get("finishReason")
            .and_then(|v| v.as_str())
            .map(String::from),
    }
}

fn base64_encode(data: &[u8]) -> String {
    use base64::{Engine as _, engine::general_purpose::STANDARD};
    STANDARD.encode(data)
}
