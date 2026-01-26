"""
Example: Low-level backend usage.

This example demonstrates using the GeminiBackend directly
for more control over API requests.
"""

import asyncio

from geminisdk import (
    GeminiBackend,
    Message,
    Role,
    GenerationConfig,
    ThinkingConfig,
)


async def basic_backend_example():
    """Basic backend usage with non-streaming response."""
    print("=== Backend Non-Streaming Example ===\n")
    
    async with GeminiBackend() as backend:
        messages = [
            Message(role=Role.SYSTEM, content="You are a helpful assistant."),
            Message(role=Role.USER, content="What is the capital of France?"),
        ]
        
        response = await backend.complete(
            model="gemini-2.5-flash",
            messages=messages,
            generation_config=GenerationConfig(
                temperature=0.7,
                max_output_tokens=100,
            ),
        )
        
        print(f"Response: {response.content}")
        if response.usage:
            print(f"Tokens - Prompt: {response.usage.prompt_tokens}, "
                  f"Completion: {response.usage.completion_tokens}")


async def streaming_backend_example():
    """Backend usage with streaming response."""
    print("\n\n=== Backend Streaming Example ===\n")
    
    async with GeminiBackend() as backend:
        messages = [
            Message(role=Role.USER, content="Write a short poem about AI."),
        ]
        
        print("Response: ", end="")
        
        async for chunk in backend.complete_streaming(
            model="gemini-2.5-pro",
            messages=messages,
            generation_config=GenerationConfig(
                temperature=0.9,
                max_output_tokens=200,
            ),
        ):
            if chunk.content:
                print(chunk.content, end="", flush=True)
        
        print("\n")


async def thinking_example():
    """Example with thinking/reasoning enabled."""
    print("\n=== Thinking/Reasoning Example ===\n")
    
    async with GeminiBackend() as backend:
        messages = [
            Message(
                role=Role.USER,
                content="Solve this step by step: If a train travels at 60 mph "
                        "and needs to cover 180 miles, how long will it take?",
            ),
        ]
        
        response = await backend.complete(
            model="gemini-2.5-pro",
            messages=messages,
            thinking_config=ThinkingConfig(
                include_thoughts=True,
                thinking_budget=512,
            ),
        )
        
        if response.reasoning_content:
            print("Thinking:")
            print(response.reasoning_content)
            print("\n---\n")
        
        print(f"Answer: {response.content}")


async def main():
    """Run all backend examples."""
    try:
        await basic_backend_example()
        await streaming_backend_example()
        await thinking_example()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you've authenticated with Gemini CLI:")
        print("  npm install -g @google/gemini-cli")
        print("  gemini auth login")


if __name__ == "__main__":
    asyncio.run(main())
