# GeminiSDK TypeScript

TypeScript SDK for Google Gemini Code Assist API - similar to GitHub Copilot SDK.

## Installation

```bash
npm install geminisdk
# or
yarn add geminisdk
# or
pnpm add geminisdk
```

## Prerequisites

Before using this SDK, you need to authenticate with Gemini CLI:

```bash
npm install -g @google/gemini-cli
gemini auth login
```

## Quick Start

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

## Features

- 🔐 **OAuth Authentication** - Seamless auth using Gemini CLI credentials
- 🌊 **Streaming Responses** - Real-time streaming with SSE
- 🛠️ **Tool Calling** - Define and use custom tools
- 💬 **Session Management** - Manage conversation state
- 🧠 **Thinking/Reasoning** - Support for model reasoning

## API Reference

### GeminiClient

Main client for interacting with the API.

```typescript
const client = new GeminiClient({
  timeout: 720000,        // Request timeout
  autoRefresh: true,      // Auto-refresh tokens
});

await client.start();
const session = await client.createSession({ model: 'gemini-2.5-pro' });
await client.close();
```

### GeminiSession

Manages conversation sessions.

```typescript
const session = await client.createSession({
  model: 'gemini-2.5-pro',
  streaming: true,
  systemMessage: 'You are a helpful assistant.',
});

// Subscribe to events
session.on((event) => {
  console.log(event.type, event.data);
});

// Send message
await session.send({ prompt: 'Hello!' });

// Or send and wait
const response = await session.sendAndWait({ prompt: 'Hello!' });
```

### Tools

Define custom tools for the model to use.

```typescript
import { defineTool, createTool } from 'geminisdk';

const weatherTool = defineTool(
  {
    name: 'get_weather',
    description: 'Get current weather',
    parameters: {
      type: 'object',
      properties: {
        city: { type: 'string', description: 'City name' },
      },
      required: ['city'],
    },
  },
  async (args) => {
    return `Weather in ${args.city}: Sunny, 72°F`;
  }
);

const session = await client.createSession({
  tools: [weatherTool],
});
```

## License

MIT
