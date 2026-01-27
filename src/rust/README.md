# GeminiSDK - Rust

Rust SDK for Google Gemini CLI / Code Assist API. Full-featured client with OAuth authentication, streaming, sessions, and tool calling.

## Installation

Add to your `Cargo.toml`:

```toml
[dependencies]
geminisdk = "0.1.0"
tokio = { version = "1", features = ["full"] }
```

## Prerequisites

You need Gemini CLI credentials. Install Gemini CLI and authenticate:

```bash
# Install Gemini CLI
npm install -g @anthropic-ai/gemini-cli
# or
pip install gemini-cli

# Authenticate
gemini auth login
```

This creates `~/.gemini/oauth_creds.json` which this SDK uses.

## Quick Start

```rust
use geminisdk::{GeminiClient, SessionConfig, MessageOptions};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create client
    let client = GeminiClient::with_defaults();
    client.start().await?;

    // Create session
    let session = client.create_session(SessionConfig {
        model: Some("gemini-2.5-pro".to_string()),
        streaming: Some(true),
        ..Default::default()
    }).await?;

    // Send message and wait for response
    let response = session.send_and_wait(MessageOptions {
        prompt: "What is the capital of France?".to_string(),
        attachments: None,
        context: None,
    }).await?;

    println!("Response: {:?}", response.data);

    client.close().await?;
    Ok(())
}
```

## Streaming Responses

```rust
use geminisdk::{GeminiClient, SessionConfig, MessageOptions, EventType};
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = GeminiClient::with_defaults();
    client.start().await?;

    let session = client.create_session(SessionConfig {
        model: Some("gemini-2.5-flash".to_string()),
        streaming: Some(true),
        ..Default::default()
    }).await?;

    // Register event handler for streaming
    session.on(Arc::new(|event| {
        match event.event_type {
            EventType::AssistantMessageDelta => {
                if let Some(delta) = event.data.get("deltaContent") {
                    print!("{}", delta.as_str().unwrap_or(""));
                }
            }
            EventType::AssistantMessage => {
                println!("\n--- Complete ---");
            }
            _ => {}
        }
    })).await;

    session.send(MessageOptions {
        prompt: "Write a haiku about Rust programming".to_string(),
        attachments: None,
        context: None,
    }).await?;

    client.close().await?;
    Ok(())
}
```

## Tool Calling

```rust
use geminisdk::{
    GeminiClient, SessionConfig, MessageOptions,
    create_tool, ToolParameters, ToolInvocation, ToolResult, success_result,
};

async fn get_weather(inv: ToolInvocation) -> ToolResult {
    let city = inv.arguments.get("city")
        .and_then(|v| v.as_str())
        .unwrap_or("Unknown");
    
    success_result(format!("Weather in {}: 72°F, Sunny", city))
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = GeminiClient::with_defaults();
    client.start().await?;

    // Create tool
    let weather_tool = create_tool(
        "get_weather",
        "Get current weather for a city",
        Some(ToolParameters::new()
            .add_string("city", "The city name")
            .required(vec!["city"])
            .to_value()),
    );

    let session = client.create_session(SessionConfig {
        model: Some("gemini-2.5-pro".to_string()),
        tools: Some(vec![weather_tool]),
        streaming: Some(false),
        ..Default::default()
    }).await?;

    let response = session.send_and_wait(MessageOptions {
        prompt: "What's the weather in Tokyo?".to_string(),
        attachments: None,
        context: None,
    }).await?;

    println!("Response: {:?}", response);

    client.close().await?;
    Ok(())
}
```

## Thinking Mode

```rust
use geminisdk::{GeminiClient, SessionConfig, MessageOptions, ThinkingConfig};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = GeminiClient::with_defaults();
    client.start().await?;

    let session = client.create_session(SessionConfig {
        model: Some("gemini-2.5-pro".to_string()),
        thinking_config: Some(ThinkingConfig {
            include_thoughts: true,
            thinking_budget: Some(10000),
        }),
        ..Default::default()
    }).await?;

    let response = session.send_and_wait(MessageOptions {
        prompt: "Solve: If x^2 + 5x + 6 = 0, what is x?".to_string(),
        attachments: None,
        context: None,
    }).await?;

    println!("Response: {:?}", response);

    client.close().await?;
    Ok(())
}
```

## API Reference

### GeminiClient

- `GeminiClient::new(options)` - Create with options
- `GeminiClient::with_defaults()` - Create with defaults
- `client.start()` - Initialize and authenticate
- `client.stop()` / `client.close()` - Cleanup
- `client.create_session(config)` - Create conversation session
- `client.list_models()` - List available models

### GeminiSession

- `session.send(options)` - Send message (async)
- `session.send_and_wait(options)` - Send and wait for response
- `session.on(handler)` - Register event handler
- `session.messages()` - Get conversation history
- `session.destroy()` - Close session

### Event Types

- `SessionCreated`, `SessionIdle`, `SessionError`
- `AssistantMessage`, `AssistantMessageDelta`
- `AssistantReasoning`, `AssistantReasoningDelta`
- `ToolCall`, `ToolResult`

## Available Models

- `gemini-3-pro-preview`, `gemini-3-flash-preview`
- `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`
- `auto` (default)

## License

MIT License
