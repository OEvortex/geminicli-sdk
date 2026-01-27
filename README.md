# GeminiCLI SDK

A **multi-language SDK** for Google Gemini Code Assist API, inspired by the [GitHub Copilot SDK](https://github.com/github/copilot-sdk).

GeminiCLI SDK provides high-level interfaces for interacting with the Gemini Code Assist API in **Python**, **TypeScript**, **Rust**, **Go**, and **C++**, supporting:

- 🔐 **OAuth Authentication** - Seamless authentication using Gemini CLI credentials
- 🌊 **Streaming Responses** - Real-time streaming with Server-Sent Events (SSE)
- 🛠️ **Tool Calling** - Define and use custom tools with the model
- 💬 **Session Management** - Manage conversation state and history
- 🧠 **Thinking/Reasoning** - Support for model thinking/reasoning content

## Available SDKs

| Language | Location | Package Name | Status |
|----------|----------|--------------|--------|
| **Python** | [`src/python/`](./src/python/) | `geminisdk` | ✅ Production Ready |
| **TypeScript** | [`src/typescript/`](./src/typescript/) | `geminisdk` | ✅ Production Ready |
| **Rust** | [`src/rust/`](./src/rust/) | `geminisdk` | ✅ Production Ready |
| **Go** | [`src/go/`](./src/go/) | `geminisdk` | ✅ Production Ready |
| **C++** | [`src/cpp/`](./src/cpp/) | `geminisdk` | ✅ Production Ready |

## Prerequisites

Before using any SDK, you need to authenticate with Google. The easiest way is to use the [Gemini CLI](https://github.com/google-gemini/gemini-cli):

```bash
# Install Gemini CLI
npm install -g @google/gemini-cli

# Authenticate
gemini auth login
```

This will store your OAuth credentials in `~/.gemini/oauth_creds.json`.

---

## Quick Start

### Python

```bash
pip install geminisdk
```

```python
import asyncio
from geminisdk import GeminiClient

async def main():
    async with GeminiClient() as client:
        session = await client.create_session({
            "model": "gemini-2.5-pro",
            "streaming": True,
        })
        
        response = await session.send_and_wait({
            "prompt": "Explain Python decorators in simple terms.",
        })
        print(response.data["content"])

asyncio.run(main())
```

### TypeScript

```bash
npm install geminisdk
```

```typescript
import { GeminiClient, EventType } from 'geminisdk';

async function main() {
  const client = new GeminiClient();
  
  const session = await client.createSession({
    model: 'gemini-2.5-pro',
    streaming: true,
  });

  session.on((event) => {
    if (event.type === EventType.ASSISTANT_MESSAGE_DELTA) {
      process.stdout.write((event.data as any).deltaContent);
    }
  });

  await session.send({ prompt: 'What is TypeScript?' });
  await client.close();
}

main();
```

### Rust

```toml
# Cargo.toml
[dependencies]
geminisdk = { path = "src/rust" }
tokio = { version = "1", features = ["full"] }
```

```rust
use geminisdk::{GeminiClient, SessionConfig, MessageOptions};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = GeminiClient::with_defaults();
    client.start().await?;

    let session = client.create_session(SessionConfig {
        model: Some("gemini-2.5-pro".to_string()),
        ..Default::default()
    }).await?;

    let response = session.send_and_wait(MessageOptions {
        prompt: "Hello, Gemini!".to_string(),
        ..Default::default()
    }).await?;

    println!("{:?}", response);
    client.close().await?;
    Ok(())
}
```

### Go

```go
package main

import (
    "context"
    "fmt"
    "github.com/OEvortex/geminicli-sdk/src/go"
)

func main() {
    client := geminisdk.NewClient(nil)
    client.Start(context.Background())
    defer client.Close()

    session, _ := client.CreateSession(&geminisdk.SessionConfig{
        Model: "gemini-2.5-pro",
    })

    response, _ := session.SendAndWait(context.Background(), &geminisdk.MessageOptions{
        Prompt: "Hello, Gemini!",
    })
    
    fmt.Println(response.Data)
}
```

### C++

```cpp
#include <geminisdk/geminisdk.hpp>
#include <iostream>

int main() {
    geminisdk::Client client;
    client.start();

    geminisdk::SessionConfig config;
    config.model = "gemini-2.5-pro";
    
    auto session = client.create_session(config);
    
    geminisdk::MessageOptions options;
    options.prompt = "Hello, Gemini!";
    
    auto response = session->send_and_wait(options);
    std::cout << response.data["content"].get<std::string>() << std::endl;
    
    client.close();
    return 0;
}
```

---

## Python SDK (Full Documentation)

```python
import asyncio
from geminisdk import GeminiClient

async def main():
    # Create a client (uses Gemini CLI credentials by default)
    async with GeminiClient() as client:
        # Create a session
        session = await client.create_session({
            "model": "gemini-2.5-pro",
            "streaming": True,
        })
        
        # Send a message and wait for response
        response = await session.send_and_wait({
            "prompt": "Explain Python decorators in simple terms.",
        })
        
        print(response.data["content"])

if __name__ == "__main__":
    asyncio.run(main())
```

## Streaming Example

```python
import asyncio
from geminisdk import GeminiClient, EventType

async def main():
    async with GeminiClient() as client:
        session = await client.create_session({
            "model": "gemini-2.5-pro",
        })
        
        # Subscribe to events
        def on_event(event):
            if event.type == EventType.ASSISTANT_MESSAGE_DELTA:
                # Print streaming content
                print(event.data["delta_content"], end="", flush=True)
            elif event.type == EventType.ASSISTANT_MESSAGE:
                # Final message
                print("\n--- Done ---")
        
        session.on(on_event)
        
        # Send message (events will be emitted)
        await session.send({
            "prompt": "Write a haiku about programming.",
        })

asyncio.run(main())
```

## Tool Calling Example

```python
import asyncio
from geminisdk import GeminiClient, define_tool

# Define a tool using the decorator
@define_tool(
    name="get_weather",
    description="Get the current weather for a location",
)
def get_weather(city: str, country: str = "US") -> str:
    """Get weather information.
    
    Args:
        city: The city name.
        country: The country code.
    """
    # In a real app, call a weather API
    return f"Weather in {city}, {country}: Sunny, 72°F"

@define_tool(
    name="calculate",
    description="Perform a mathematical calculation",
)
def calculate(expression: str) -> str:
    """Evaluate a math expression.
    
    Args:
        expression: The math expression to evaluate.
    """
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}"

async def main():
    async with GeminiClient() as client:
        session = await client.create_session({
            "model": "gemini-2.5-pro",
            "tools": [get_weather, calculate],
        })
        
        response = await session.send_and_wait({
            "prompt": "What's the weather in Tokyo? Also, what is 15 * 23?",
        })
        
        print(response.data["content"])

asyncio.run(main())
```

## Backend API (Low-Level)

For more control, you can use the backend directly:

```python
import asyncio
from geminisdk import GeminiBackend, Message, Role, GenerationConfig

async def main():
    async with GeminiBackend() as backend:
        messages = [
            Message(role=Role.SYSTEM, content="You are a helpful assistant."),
            Message(role=Role.USER, content="Hello!"),
        ]
        
        # Non-streaming
        response = await backend.complete(
            model="gemini-2.5-pro",
            messages=messages,
            generation_config=GenerationConfig(
                temperature=0.7,
                max_output_tokens=1000,
            ),
        )
        print(response.content)
        
        # Streaming
        async for chunk in backend.complete_streaming(
            model="gemini-2.5-pro",
            messages=messages,
        ):
            if chunk.content:
                print(chunk.content, end="", flush=True)

asyncio.run(main())
```

## Configuration

### Client Options

```python
from geminisdk import GeminiClient

client = GeminiClient({
    # Custom OAuth credentials path
    "oauth_path": "/path/to/oauth_creds.json",
    
    # Request timeout (default: 720 seconds)
    "timeout": 300.0,
    
    # Auto-refresh tokens in background (default: True)
    "auto_refresh": True,
    
    # Custom OAuth client credentials (optional)
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
})
```

### Session Options

```python
session = await client.create_session({
    # Model selection
    "model": "gemini-2.5-pro",
    
    # Enable streaming (default: True)
    "streaming": True,
    
    # System message
    "system_message": "You are a helpful coding assistant.",
    
    # Tools
    "tools": [my_tool1, my_tool2],
    
    # Generation config
    "generation_config": GenerationConfig(
        temperature=0.7,
        max_output_tokens=2048,
        top_p=0.9,
    ),
    
    # Enable thinking/reasoning
    "thinking_config": ThinkingConfig(
        include_thoughts=True,
        thinking_budget=1024,
    ),
})
```

## Available Models

| Model ID | Description | Features |
|----------|-------------|----------|
| `gemini-3-pro-preview` | Gemini 3 Pro Preview | Tools, Thinking |
| `gemini-3-flash-preview` | Gemini 3 Flash Preview | Tools, Thinking |
| `gemini-2.5-pro` | Gemini 2.5 Pro | Tools, Thinking |
| `gemini-2.5-flash` | Gemini 2.5 Flash | Tools, Thinking |
| `gemini-2.5-flash-lite` | Gemini 2.5 Flash Lite | Tools |
| `auto-gemini-3` | Auto (Gemini 3) | Tools, Thinking |
| `auto-gemini-2.5` | Auto (Gemini 2.5) | Tools, Thinking |
| `auto` | Auto (Default) | Tools, Thinking |

## Events

The SDK emits various events during a session:

| Event Type | Description |
|------------|-------------|
| `ASSISTANT_MESSAGE_DELTA` | Partial content received (streaming) |
| `ASSISTANT_MESSAGE` | Complete message received |
| `ASSISTANT_REASONING_DELTA` | Partial reasoning content (streaming) |
| `ASSISTANT_REASONING` | Complete reasoning content |
| `TOOL_CALL` | Model is calling a tool |
| `TOOL_RESULT` | Tool execution result |
| `SESSION_IDLE` | Session is idle |
| `SESSION_ERROR` | An error occurred |

## Error Handling

```python
from geminisdk import (
    GeminiClient,
    AuthenticationError,
    APIError,
    RateLimitError,
)

async def main():
    try:
        async with GeminiClient() as client:
            session = await client.create_session()
            response = await session.send_and_wait({"prompt": "Hello"})
            
    except AuthenticationError as e:
        print(f"Authentication failed: {e}")
        
    except RateLimitError as e:
        print(f"Rate limited: {e}")
        
    except APIError as e:
        print(f"API error: {e}")
```

## Architecture

The SDK follows a layered architecture:

```
┌─────────────────────────────────────────┐
│             GeminiClient                │  High-level client
├─────────────────────────────────────────┤
│             GeminiSession               │  Session management
├─────────────────────────────────────────┤
│             GeminiBackend               │  API communication
├─────────────────────────────────────────┤
│           GeminiOAuthManager            │  Authentication
└─────────────────────────────────────────┘
```

## References

This SDK is inspired by:

- [GitHub Copilot SDK](https://github.com/github/copilot-sdk) - SDK architecture and patterns
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) - OAuth credentials and API
- [Revibe](https://github.com/OEvortex/revibe) - GeminiCLI backend implementation
- [Better-Copilot-Chat](https://github.com/OEvortex/better-copilot-chat) - Provider patterns

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
