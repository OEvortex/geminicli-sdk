"""
Example: Basic usage of GeminiSDK.

This example demonstrates:
- Creating a GeminiClient
- Creating a session
- Sending messages with streaming
- Using event handlers
"""

import asyncio

from geminisdk import GeminiClient, EventType


async def basic_example():
    """Basic example showing streaming chat."""
    print("=== Basic Streaming Example ===\n")
    
    async with GeminiClient() as client:
        # Create a session
        session = await client.create_session({
            "model": "gemini-2.5-pro",
            "streaming": True,
        })
        
        # Subscribe to events
        def on_event(event):
            if event.type == EventType.ASSISTANT_MESSAGE_DELTA:
                # Print streaming content without newline
                print(event.data["delta_content"], end="", flush=True)
            elif event.type == EventType.ASSISTANT_MESSAGE:
                # Final message received
                print("\n\n--- Response complete ---")
            elif event.type == EventType.SESSION_ERROR:
                print(f"\nError: {event.data['error']}")
        
        session.on(on_event)
        
        # Send a message
        print("User: What is Python?\n")
        print("Assistant: ", end="")
        
        await session.send({
            "prompt": "What is Python? Explain in 2-3 sentences.",
        })


async def non_streaming_example():
    """Example using non-streaming send_and_wait."""
    print("\n\n=== Non-Streaming Example ===\n")
    
    async with GeminiClient() as client:
        session = await client.create_session({
            "model": "gemini-2.5-flash",
            "streaming": False,
        })
        
        print("User: Write a haiku about coding.\n")
        
        response = await session.send_and_wait({
            "prompt": "Write a haiku about coding.",
        })
        
        print(f"Assistant: {response.data['content']}")


async def main():
    """Run examples."""
    try:
        await basic_example()
        await non_streaming_example()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you've authenticated with Gemini CLI:")
        print("  npm install -g @google/gemini-cli")
        print("  gemini auth login")


if __name__ == "__main__":
    asyncio.run(main())
