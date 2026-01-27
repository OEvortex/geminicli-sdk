# GeminiSDK - Go

Go SDK for Google Gemini CLI / Code Assist API. Full-featured client with OAuth authentication, streaming, sessions, and tool calling.

## Installation

```bash
go get github.com/OEvortex/geminicli-sdk/go
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

```go
package main

import (
    "context"
    "fmt"
    "log"

    "github.com/OEvortex/geminicli-sdk/go"
)

func main() {
    ctx := context.Background()

    // Create client
    client := geminisdk.NewClient(nil)
    if err := client.Start(ctx); err != nil {
        log.Fatal(err)
    }
    defer client.Close()

    // Create session
    session, err := client.CreateSession(ctx, &geminisdk.SessionConfig{
        Model:     "gemini-2.5-pro",
        Streaming: true,
    })
    if err != nil {
        log.Fatal(err)
    }

    // Send message and wait for response
    response, err := session.SendAndWait(ctx, &geminisdk.MessageOptions{
        Prompt: "What is the capital of France?",
    })
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("Response: %v\n", response.Data["content"])
}
```

## Streaming Responses

```go
package main

import (
    "context"
    "fmt"

    "github.com/OEvortex/geminicli-sdk/go"
)

func main() {
    ctx := context.Background()
    client := geminisdk.NewClient(nil)
    client.Start(ctx)
    defer client.Close()

    session, _ := client.CreateSession(ctx, &geminisdk.SessionConfig{
        Model:     "gemini-2.5-flash",
        Streaming: true,
    })

    // Register event handler for streaming
    session.On(func(event geminisdk.SessionEvent) {
        switch event.EventType {
        case geminisdk.EventAssistantMessageDelta:
            if delta, ok := event.Data["deltaContent"].(string); ok {
                fmt.Print(delta)
            }
        case geminisdk.EventAssistantMessage:
            fmt.Println("\n--- Complete ---")
        }
    })

    session.Send(ctx, &geminisdk.MessageOptions{
        Prompt: "Write a haiku about Go programming",
    })
}
```

## Tool Calling

```go
package main

import (
    "context"
    "fmt"

    "github.com/OEvortex/geminicli-sdk/go"
)

func main() {
    ctx := context.Background()
    client := geminisdk.NewClient(nil)
    client.Start(ctx)
    defer client.Close()

    // Define tool
    weatherTool := geminisdk.DefineTool(
        "get_weather",
        "Get current weather for a city",
        geminisdk.NewToolParameters().
            AddString("city", "The city name").
            Required("city"),
    )

    session, _ := client.CreateSession(ctx, &geminisdk.SessionConfig{
        Model:     "gemini-2.5-pro",
        Tools:     []geminisdk.Tool{weatherTool},
        Streaming: false,
    })

    // Register tool handler
    session.RegisterToolHandler("get_weather", func(ctx context.Context, inv geminisdk.ToolInvocation) geminisdk.ToolResult {
        city := inv.Arguments["city"].(string)
        return geminisdk.SuccessResult(fmt.Sprintf("Weather in %s: 72°F, Sunny", city))
    })

    response, _ := session.SendAndWait(ctx, &geminisdk.MessageOptions{
        Prompt: "What's the weather in Tokyo?",
    })

    fmt.Printf("Response: %v\n", response.Data["content"])
}
```

## Thinking Mode

```go
session, _ := client.CreateSession(ctx, &geminisdk.SessionConfig{
    Model: "gemini-2.5-pro",
    ThinkingConfig: &geminisdk.ThinkingConfig{
        IncludeThoughts: true,
        ThinkingBudget:  10000,
    },
})

session.On(func(event geminisdk.SessionEvent) {
    if event.EventType == geminisdk.EventAssistantReasoning {
        fmt.Printf("Thinking: %v\n", event.Data["content"])
    }
})
```

## API Reference

### Client

- `NewClient(options)` - Create client
- `client.Start(ctx)` - Initialize and authenticate  
- `client.Stop()` / `client.Close()` - Cleanup
- `client.CreateSession(ctx, config)` - Create session
- `client.GetSession(id)` - Get existing session
- `client.ListSessions()` - List all sessions
- `client.ListModels()` - List available models

### Session

- `session.Send(ctx, options)` - Send message (async)
- `session.SendAndWait(ctx, options)` - Send and wait
- `session.On(handler)` - Register event handler
- `session.RegisterToolHandler(name, handler)` - Register tool
- `session.Messages()` - Get conversation history
- `session.ClearHistory()` - Clear messages
- `session.Destroy()` - Close session

### Event Types

- `EventSessionCreated`, `EventSessionIdle`, `EventSessionError`
- `EventAssistantMessage`, `EventAssistantMessageDelta`
- `EventAssistantReasoning`, `EventAssistantReasoningDelta`
- `EventToolCall`, `EventToolResult`

### Tool Helpers

- `CreateTool(name, desc, params)` - Create tool
- `DefineTool(name, desc, builder)` - Create with builder
- `NewToolParameters()` - Parameters builder
- `SuccessResult(text)` - Success result
- `FailureResult(text)` - Failure result

## Available Models

- `gemini-3-pro-preview`, `gemini-3-flash-preview`
- `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`
- `auto` (default)

## License

MIT License
