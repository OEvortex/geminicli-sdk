# GeminiSDK C++

A C++17 SDK for the Gemini CLI backend (Code Assist API).

## Features

- Full OAuth authentication (auto-loads from `~/.gemini/oauth_creds.json`)
- Token auto-refresh
- Streaming (SSE) and non-streaming completions
- Tool calling support
- Thinking/reasoning mode
- Session management with event system
- Thread-safe design

## Requirements

- C++17 compiler (GCC 7+, Clang 5+, MSVC 2019+)
- CMake 3.14+
- libcurl
- nlohmann_json (fetched automatically by CMake)

## Building

```bash
# Create build directory
mkdir build && cd build

# Configure
cmake ..

# Build
cmake --build .

# Install (optional)
cmake --install . --prefix /usr/local
```

## Quick Start

```cpp
#include <geminisdk/geminisdk.hpp>
#include <iostream>

using namespace geminisdk;

int main() {
    // Create and start client
    Client client;
    client.start();
    
    // Create a session
    SessionConfig config;
    config.model = "gemini-2.5-flash";
    config.streaming = true;
    
    auto session = client.create_session(config);
    
    // Event handler for streaming
    session->on([](const SessionEvent& event) {
        if (event.event_type == EventType::AssistantMessageDelta) {
            std::cout << event.data["deltaContent"].get<std::string>() << std::flush;
        }
    });
    
    // Send a message
    MessageOptions options;
    options.prompt = "Hello, Gemini!";
    session->send(options);
    
    client.close();
    return 0;
}
```

## Tool Calling

```cpp
#include <geminisdk/geminisdk.hpp>

using namespace geminisdk;

int main() {
    Client client;
    client.start();
    
    // Define a tool
    auto tool = define_tool(
        "get_weather",
        "Get weather for a city",
        ToolParametersBuilder()
            .add_string("city", "The city name")
            .required({"city"})
    );
    
    SessionConfig config;
    config.tools = {tool};
    
    auto session = client.create_session(config);
    
    // Register handler
    session->register_tool_handler("get_weather", [](const ToolInvocation& inv) {
        std::string city = inv.arguments.at("city").get<std::string>();
        return success_result("Weather in " + city + ": 72°F, Sunny");
    });
    
    MessageOptions options;
    options.prompt = "What's the weather in Tokyo?";
    session->send_and_wait(options);
    
    return 0;
}
```

## Event Types

| Event Type | Description |
|------------|-------------|
| `AssistantMessageDelta` | Streaming text chunk |
| `AssistantMessage` | Complete message |
| `AssistantReasoning` | Thinking/reasoning content |
| `ToolCall` | Tool invocation |
| `ToolResult` | Tool execution result |
| `SessionIdle` | Session ready for input |
| `SessionError` | Error occurred |

## API Reference

### Client
- `Client(options)` - Create client
- `start()` - Connect and authenticate
- `stop()` / `close()` - Disconnect
- `create_session(config)` - Create session
- `get_session(id)` - Get existing session
- `list_sessions()` - List all sessions
- `list_models()` - Get available models

### Session
- `send(options)` - Send message (async)
- `send_and_wait(options)` - Send and wait for response
- `on(handler)` - Register event handler
- `register_tool_handler(name, handler)` - Register tool handler
- `clear_history()` - Clear conversation
- `destroy()` - Close session

## License

MIT
