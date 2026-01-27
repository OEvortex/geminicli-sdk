"""
Example: Using tools with GeminiSDK.

This example demonstrates:
- Defining tools with the @define_tool decorator
- Creating tools programmatically
- Tool execution with automatic argument parsing
"""

import asyncio

from geminisdk import GeminiClient, EventType, define_tool, create_tool


# Define a tool using the decorator
@define_tool(
    name="get_weather",
    description="Get the current weather for a location",
)
def get_weather(city: str, country: str = "US") -> str:
    """Get weather information.
    
    Args:
        city: The city name.
        country: The country code (default: US).
    
    Returns:
        Weather information string.
    """
    # In a real app, you'd call a weather API
    weather_data = {
        "Tokyo": "Sunny, 22°C",
        "London": "Cloudy, 15°C",
        "New York": "Rainy, 18°C",
        "Paris": "Partly cloudy, 20°C",
    }
    weather = weather_data.get(city, "Unknown")
    return f"Weather in {city}, {country}: {weather}"


@define_tool(
    name="calculate",
    description="Perform a mathematical calculation",
)
def calculate(expression: str) -> str:
    """Evaluate a math expression safely.
    
    Args:
        expression: The math expression to evaluate.
    
    Returns:
        The result of the calculation.
    """
    # Use a safer eval with limited builtins
    allowed_names = {"abs": abs, "min": min, "max": max, "round": round}
    try:
        # Only allow numbers and basic operators
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"Result: {result}"
    except Exception as e:
        return f"Error calculating: {e}"


# Create a tool programmatically
search_tool = create_tool(
    name="search",
    description="Search for information on a topic",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 5)",
            },
        },
        "required": ["query"],
    },
    handler=lambda inv: {
        "text_result_for_llm": f"Search results for '{inv['arguments']['query']}': "
        f"Found {inv['arguments'].get('max_results', 5)} results about the topic."
    },
)


async def main():
    """Run the tool example."""
    print("=== Tool Calling Example ===\n")
    
    async with GeminiClient() as client:
        session = await client.create_session({
            "model": "gemini-2.5-pro",
            "tools": [get_weather, calculate, search_tool],
        })
        
        # Subscribe to tool events
        def on_event(event):
            if event.type == EventType.TOOL_CALL:
                print(f"\n[Tool Call] {event.data['name']}")
                print(f"  Arguments: {event.data['arguments']}")
            elif event.type == EventType.TOOL_RESULT:
                print(f"[Tool Result] {event.data['result']}")
            elif event.type == EventType.ASSISTANT_MESSAGE_DELTA:
                print(event.data["delta_content"], end="", flush=True)
            elif event.type == EventType.ASSISTANT_MESSAGE:
                print("\n")
        
        session.on(on_event)
        
        # Ask a question that requires tool use
        print("User: What's the weather in Tokyo and what is 15 * 23?\n")
        print("Assistant: ", end="")
        
        await session.send({
            "prompt": "What's the weather in Tokyo and what is 15 * 23?",
        })


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you've authenticated with Gemini CLI:")
        print("  npm install -g @google/gemini-cli")
        print("  gemini auth login")
