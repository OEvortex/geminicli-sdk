import { GeminiClient, EventType } from '../src/index.js';

async function main(): Promise<void> {
  console.log('GeminiSDK TypeScript - Streaming Example\n');

  const client = new GeminiClient();

  try {
    await client.start();

    const session = await client.createSession({
      model: 'gemini-2.5-flash',
      streaming: true,
    });

    // Register event handler for streaming
    session.on((event) => {
      switch (event.type) {
        case EventType.ASSISTANT_MESSAGE_DELTA:
          process.stdout.write((event.data as any).deltaContent || '');
          break;
        case EventType.ASSISTANT_MESSAGE:
          console.log('\n--- Complete ---');
          break;
        default:
          break;
      }
    });

    await session.send({
      prompt: 'Write a haiku about TypeScript programming',
    });

    await client.close();
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  }
}

main();
