//! GeminiSDK Session - Manages individual conversation sessions.

use crate::backend::GeminiBackend;
use crate::errors::{GeminiSDKError, Result};
use crate::types::{
    EventType, GenerationConfig, Message, MessageContent, MessageOptions, Role, SessionEvent,
    ThinkingConfig, Tool, ToolCall, ToolInvocation, ToolResult,
};
use chrono::{DateTime, Utc};
use futures::StreamExt;
use serde_json::json;
use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use tokio::sync::Mutex;

pub type ToolHandler = Arc<
    dyn Fn(ToolInvocation) -> Pin<Box<dyn Future<Output = ToolResult> + Send>> + Send + Sync,
>;
pub type SessionEventHandler = Arc<dyn Fn(SessionEvent) + Send + Sync>;

pub struct GeminiSession {
    session_id: String,
    model: String,
    backend: Arc<GeminiBackend>,
    tools: Vec<Tool>,
    tool_handlers: HashMap<String, ToolHandler>,
    system_message: Option<String>,
    generation_config: Option<GenerationConfig>,
    thinking_config: Option<ThinkingConfig>,
    streaming: bool,

    messages: Arc<Mutex<Vec<Message>>>,
    event_handlers: Arc<Mutex<Vec<SessionEventHandler>>>,
    closed: Arc<Mutex<bool>>,
    start_time: DateTime<Utc>,
    modified_time: Arc<Mutex<DateTime<Utc>>>,
}

impl GeminiSession {
    pub fn new(
        session_id: String,
        model: String,
        backend: Arc<GeminiBackend>,
        tools: Vec<Tool>,
        system_message: Option<String>,
        generation_config: Option<GenerationConfig>,
        thinking_config: Option<ThinkingConfig>,
        streaming: bool,
    ) -> Self {
        let mut messages = Vec::new();
        if let Some(ref sys_msg) = system_message {
            messages.push(Message {
                role: Role::System,
                content: MessageContent::Text(sys_msg.clone()),
                name: None,
                tool_calls: None,
                tool_call_id: None,
            });
        }

        Self {
            session_id,
            model,
            backend,
            tools,
            tool_handlers: HashMap::new(),
            system_message,
            generation_config,
            thinking_config,
            streaming,
            messages: Arc::new(Mutex::new(messages)),
            event_handlers: Arc::new(Mutex::new(Vec::new())),
            closed: Arc::new(Mutex::new(false)),
            start_time: Utc::now(),
            modified_time: Arc::new(Mutex::new(Utc::now())),
        }
    }

    pub fn session_id(&self) -> &str {
        &self.session_id
    }

    pub fn model(&self) -> &str {
        &self.model
    }

    pub fn start_time(&self) -> DateTime<Utc> {
        self.start_time
    }

    pub async fn modified_time(&self) -> DateTime<Utc> {
        *self.modified_time.lock().await
    }

    pub async fn messages(&self) -> Vec<Message> {
        self.messages.lock().await.clone()
    }

    pub fn register_tool_handler(&mut self, name: String, handler: ToolHandler) {
        self.tool_handlers.insert(name, handler);
    }

    pub async fn on(&self, handler: SessionEventHandler) {
        self.event_handlers.lock().await.push(handler);
    }

    async fn emit(&self, event_type: EventType, data: serde_json::Value) {
        let event = SessionEvent {
            event_type,
            data,
            session_id: self.session_id.clone(),
        };

        let handlers = self.event_handlers.lock().await;
        for handler in handlers.iter() {
            handler(event.clone());
        }
    }

    pub async fn send(&self, options: MessageOptions) -> Result<()> {
        if *self.closed.lock().await {
            return Err(GeminiSDKError::session_closed(Some(self.session_id.clone())));
        }

        let mut content = options.prompt.clone();
        if let Some(context) = &options.context {
            content = format!("{}\n\n{}", context, content);
        }

        let user_message = Message {
            role: Role::User,
            content: MessageContent::Text(content),
            name: None,
            tool_calls: None,
            tool_call_id: None,
        };

        {
            let mut messages = self.messages.lock().await;
            messages.push(user_message);
        }

        {
            let mut modified = self.modified_time.lock().await;
            *modified = Utc::now();
        }

        let result = if self.streaming {
            self.stream_response().await
        } else {
            self.get_response().await
        };

        if let Err(ref e) = result {
            self.emit(EventType::SessionError, json!({"error": e.to_string()}))
                .await;
        }

        result
    }

    pub async fn send_and_wait(&self, options: MessageOptions) -> Result<SessionEvent> {
        let (tx, rx) = tokio::sync::oneshot::channel();
        let tx = Arc::new(Mutex::new(Some(tx)));

        let handler: SessionEventHandler = {
            let tx = tx.clone();
            Arc::new(move |event: SessionEvent| {
                if matches!(
                    event.event_type,
                    EventType::AssistantMessage | EventType::SessionIdle | EventType::SessionError
                ) {
                    if let Some(sender) = tx.try_lock().ok().and_then(|mut g| g.take()) {
                        let _ = sender.send(event);
                    }
                }
            })
        };

        self.on(handler).await;
        self.send(options).await?;

        rx.await.map_err(|_| GeminiSDKError::Session {
            message: "No response received".to_string(),
            session_id: Some(self.session_id.clone()),
        })
    }

    async fn stream_response(&self) -> Result<()> {
        let mut full_content = String::new();
        let mut full_reasoning = String::new();
        let mut all_tool_calls: Vec<ToolCall> = Vec::new();
        let mut final_usage = None;

        let messages = self.messages.lock().await.clone();
        let tools = if self.tools.is_empty() {
            None
        } else {
            Some(self.tools.as_slice())
        };

        let mut stream = self
            .backend
            .complete_streaming(
                &self.model,
                &messages,
                self.generation_config.as_ref(),
                self.thinking_config.as_ref(),
                tools,
            )
            .await?;

        while let Some(chunk_result) = stream.next().await {
            let chunk = chunk_result?;

            if !chunk.content.is_empty() {
                full_content.push_str(&chunk.content);
                self.emit(
                    EventType::AssistantMessageDelta,
                    json!({
                        "deltaContent": chunk.content,
                        "content": full_content
                    }),
                )
                .await;
            }

            if let Some(reasoning) = &chunk.reasoning_content {
                full_reasoning.push_str(reasoning);
                self.emit(
                    EventType::AssistantReasoningDelta,
                    json!({
                        "deltaContent": reasoning,
                        "content": full_reasoning
                    }),
                )
                .await;
            }

            if let Some(tool_calls) = chunk.tool_calls {
                all_tool_calls.extend(tool_calls);
            }

            if chunk.usage.is_some() {
                final_usage = chunk.usage;
            }
        }

        if !all_tool_calls.is_empty() {
            self.handle_tool_calls(&all_tool_calls).await?;
        }

        let assistant_message = Message {
            role: Role::Assistant,
            content: MessageContent::Text(full_content.clone()),
            name: None,
            tool_calls: if all_tool_calls.is_empty() {
                None
            } else {
                Some(all_tool_calls.clone())
            },
            tool_call_id: None,
        };

        {
            let mut messages = self.messages.lock().await;
            messages.push(assistant_message);
        }

        if !full_reasoning.is_empty() {
            self.emit(
                EventType::AssistantReasoning,
                json!({"content": full_reasoning}),
            )
            .await;
        }

        self.emit(
            EventType::AssistantMessage,
            json!({
                "content": full_content,
                "toolCalls": if all_tool_calls.is_empty() { None } else { Some(&all_tool_calls) },
                "usage": final_usage
            }),
        )
        .await;

        self.emit(EventType::SessionIdle, json!({})).await;

        Ok(())
    }

    async fn get_response(&self) -> Result<()> {
        let messages = self.messages.lock().await.clone();
        let tools = if self.tools.is_empty() {
            None
        } else {
            Some(self.tools.as_slice())
        };

        let chunk = self
            .backend
            .complete(
                &self.model,
                &messages,
                self.generation_config.as_ref(),
                self.thinking_config.as_ref(),
                tools,
            )
            .await?;

        if let Some(ref tool_calls) = chunk.tool_calls {
            self.handle_tool_calls(tool_calls).await?;
        }

        let assistant_message = Message {
            role: Role::Assistant,
            content: MessageContent::Text(chunk.content.clone()),
            name: None,
            tool_calls: chunk.tool_calls.clone(),
            tool_call_id: None,
        };

        {
            let mut messages = self.messages.lock().await;
            messages.push(assistant_message);
        }

        if let Some(reasoning) = &chunk.reasoning_content {
            self.emit(EventType::AssistantReasoning, json!({"content": reasoning}))
                .await;
        }

        self.emit(
            EventType::AssistantMessage,
            json!({
                "content": chunk.content,
                "toolCalls": chunk.tool_calls,
                "usage": chunk.usage
            }),
        )
        .await;

        self.emit(EventType::SessionIdle, json!({})).await;

        Ok(())
    }

    async fn handle_tool_calls(&self, tool_calls: &[ToolCall]) -> Result<()> {
        for tool_call in tool_calls {
            let tool_name = &tool_call.function.name;

            self.emit(
                EventType::ToolCall,
                json!({
                    "name": tool_name,
                    "arguments": tool_call.function.arguments,
                    "callId": tool_call.id
                }),
            )
            .await;

            let handler = self.tool_handlers.get(tool_name);

            if handler.is_none() {
                log::warn!("No handler for tool: {}", tool_name);
                let mut messages = self.messages.lock().await;
                messages.push(Message {
                    role: Role::User,
                    content: MessageContent::Text(format!("Error: Tool '{}' not found", tool_name)),
                    name: Some(tool_name.clone()),
                    tool_calls: None,
                    tool_call_id: Some(tool_call.id.clone()),
                });
                continue;
            }

            let handler = handler.unwrap();

            let invocation = ToolInvocation {
                name: tool_name.clone(),
                arguments: tool_call
                    .function
                    .arguments
                    .as_object()
                    .map(|o| {
                        o.iter()
                            .map(|(k, v)| (k.clone(), v.clone()))
                            .collect()
                    })
                    .unwrap_or_default(),
                call_id: tool_call.id.clone(),
            };

            match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| handler(invocation))) {
                Ok(future) => {
                    let result = future.await;
                    let result_text = result
                        .text_result_for_llm
                        .unwrap_or_else(|| "Success".to_string());

                    self.emit(
                        EventType::ToolResult,
                        json!({
                            "name": tool_name,
                            "callId": tool_call.id,
                            "result": result_text
                        }),
                    )
                    .await;

                    let mut messages = self.messages.lock().await;
                    messages.push(Message {
                        role: Role::User,
                        content: MessageContent::Text(result_text),
                        name: Some(tool_name.clone()),
                        tool_calls: None,
                        tool_call_id: Some(tool_call.id.clone()),
                    });
                }
                Err(e) => {
                    let error_msg = format!(
                        "Error executing tool '{}': {:?}",
                        tool_name,
                        e.downcast_ref::<&str>()
                    );
                    log::error!("{}", error_msg);

                    self.emit(
                        EventType::ToolResult,
                        json!({
                            "name": tool_name,
                            "callId": tool_call.id,
                            "error": error_msg
                        }),
                    )
                    .await;

                    let mut messages = self.messages.lock().await;
                    messages.push(Message {
                        role: Role::User,
                        content: MessageContent::Text(error_msg),
                        name: Some(tool_name.clone()),
                        tool_calls: None,
                        tool_call_id: Some(tool_call.id.clone()),
                    });
                }
            }
        }

        Ok(())
    }

    pub fn add_tool(&mut self, tool: Tool) {
        self.tools.push(tool);
    }

    pub fn remove_tool(&mut self, tool_name: &str) {
        self.tools.retain(|t| t.name != tool_name);
        self.tool_handlers.remove(tool_name);
    }

    pub async fn clear_history(&self) {
        let mut messages = self.messages.lock().await;
        messages.clear();

        if let Some(ref sys_msg) = self.system_message {
            messages.push(Message {
                role: Role::System,
                content: MessageContent::Text(sys_msg.clone()),
                name: None,
                tool_calls: None,
                tool_call_id: None,
            });
        }

        let mut modified = self.modified_time.lock().await;
        *modified = Utc::now();
    }

    pub async fn destroy(&self) {
        let mut closed = self.closed.lock().await;
        *closed = true;

        let mut handlers = self.event_handlers.lock().await;
        handlers.clear();

        let mut messages = self.messages.lock().await;
        messages.clear();
    }
}
