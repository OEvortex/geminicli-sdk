import { GeminiClient, EventType, Tool, ToolInvocation, ToolResult } from '../src/index.js';

async function main(): Promise<void> {
  console.log('GeminiSDK TypeScript - Tool Calling Example\n');

  const client = new GeminiClient();

  try {
    await client.start();

    // Create tool with handler
    const weatherTool: Tool = {
      name: 'get_weather',
      description: 'Get current weather for a city',
      parameters: {
        type: 'object',
        properties: {
          city: { type: 'string', description: 'The city name' },
        },
        required: ['city'],
      },
      handler: async (invocation: ToolInvocation): Promise<ToolResult> => {
        const city = (invocation.arguments as Record<string, unknown>)?.city || 'Unknown';
        return {
          resultType: 'success',
          textResultForLlm: `Weather in ${city}: 72°F, Sunny`,
        };
      },
    };

    const session = await client.createSession({
      model: 'gemini-2.5-pro',
      tools: [weatherTool],
      streaming: false,
    });

    // Register event handler
    session.on((event) => {
      const data = event.data as Record<string, unknown>;
      if (event.type === EventType.TOOL_CALL) {
        console.log(`Tool called: ${data.name}`);
      } else if (event.type === EventType.TOOL_RESULT) {
        console.log(`Tool result: ${data.result}`);
      }
    });

    const response = await session.sendAndWait({
      prompt: "What's the weather in Tokyo?",
    });

    const responseData = response.data as Record<string, unknown>;
    if (responseData?.content) {
      console.log(`\nFinal response: ${responseData.content}`);
    }

    await client.close();
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
}

main();
