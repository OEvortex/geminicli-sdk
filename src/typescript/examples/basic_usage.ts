import { GeminiClient, EventType } from '../src/index.js';

async function main(): Promise<void> {
  console.log('GeminiSDK TypeScript - Basic Usage Example\n');

  // Create client with default options
  const client = new GeminiClient();

  try {
    // Start the client (authenticates with Gemini CLI credentials)
    console.log('Starting client...');
    await client.start();
    console.log('Client started and authenticated!\n');

    // List available models
    console.log('Available models:');
    const models = await client.listModels();
    for (const model of models) {
      console.log(`  - ${model.name} (${model.id})`);
    }
    console.log();

    // Create a session
    console.log('Creating session...');
    const session = await client.createSession({
      model: 'gemini-2.5-flash',
      streaming: false, // Non-streaming for simplicity
      systemMessage: 'You are a helpful assistant.',
    });
    console.log(`Session created: ${session.sessionId}\n`);

    // Send a message and wait for response
    console.log('Sending message...');
    const response = await session.sendAndWait({
      prompt: 'What are three interesting facts about the TypeScript programming language?',
    });

    console.log('Response received:');
    console.log(`Event type: ${response.type}`);
    const data = response.data as Record<string, unknown>;
    if (data?.content) {
      console.log(`Content: ${data.content}`);
    }

    // Clean up
    console.log('\nClosing client...');
    await client.close();
    console.log('Done!');
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
}

main();
