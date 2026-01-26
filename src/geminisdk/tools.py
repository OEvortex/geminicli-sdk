"""
GeminiSDK Tools - Tool definition utilities.

This module provides utilities for defining tools that can be used
with Gemini models. It follows a similar pattern to the @define_tool
decorator in the GitHub Copilot SDK.

Example:
    >>> from geminisdk.tools import define_tool, Tool
    >>>
    >>> @define_tool(
    ...     name="get_weather",
    ...     description="Get current weather for a location",
    ... )
    >>> def get_weather(city: str, country: str = "US") -> str:
    ...     return f"Weather in {city}, {country}: Sunny, 72°F"
    >>>
    >>> # Use with session
    >>> session = await client.create_session({
    ...     "model": "gemini-2.5-pro",
    ...     "tools": [get_weather],
    ... })
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any, get_type_hints

from .types import Tool, ToolInvocation, ToolResult

logger = logging.getLogger(__name__)


# Python type to JSON Schema type mapping
_TYPE_MAPPING: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}


def _get_json_type(python_type: type | None) -> str:
    """Convert a Python type to JSON Schema type."""
    if python_type is None:
        return "string"

    # Handle Optional[X] and Union types
    origin = getattr(python_type, "__origin__", None)
    if origin is not None:
        # Handle list[X]
        if origin is list:
            return "array"
        # Handle dict[K, V]
        if origin is dict:
            return "object"
        # Handle Optional[X] (Union[X, None])
        args = getattr(python_type, "__args__", ())
        if type(None) in args:
            # Get the non-None type
            non_none_types = [t for t in args if t is not type(None)]
            if non_none_types:
                return _get_json_type(non_none_types[0])
        # Handle Union with first type
        if args:
            return _get_json_type(args[0])

    return _TYPE_MAPPING.get(python_type, "string")


def _parse_docstring(docstring: str | None) -> dict[str, str]:
    """Parse a docstring to extract parameter descriptions.

    Supports Google-style and numpy-style docstrings.
    """
    if not docstring:
        return {}

    result: dict[str, str] = {}
    lines = docstring.strip().split("\n")

    in_params = False
    current_param = ""
    current_desc = ""

    for line in lines:
        stripped = line.strip()

        # Check for params section
        if stripped.lower() in ("args:", "arguments:", "parameters:", "params:"):
            in_params = True
            continue

        if in_params:
            # Check for end of params section
            if stripped.lower() in (
                "returns:",
                "return:",
                "raises:",
                "yields:",
                "example:",
                "examples:",
                "note:",
                "notes:",
            ):
                if current_param:
                    result[current_param] = current_desc.strip()
                break

            # Check for new parameter
            if ":" in stripped and not stripped.startswith(" "):
                if current_param:
                    result[current_param] = current_desc.strip()

                parts = stripped.split(":", 1)
                param_part = parts[0].strip()
                desc_part = parts[1].strip() if len(parts) > 1 else ""

                # Handle "param_name (type): description" format
                if "(" in param_part:
                    current_param = param_part.split("(")[0].strip()
                else:
                    current_param = param_part

                current_desc = desc_part
            elif current_param and stripped:
                # Continuation of description
                current_desc += " " + stripped

    if current_param:
        result[current_param] = current_desc.strip()

    return result


def _infer_schema_from_function(func: Callable[..., Any]) -> dict[str, Any]:
    """Infer JSON Schema from function signature.

    Examines the function's parameters and type hints to generate
    a JSON Schema for the tool's parameters.
    """
    sig = inspect.signature(func)

    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    # Parse docstring for parameter descriptions
    param_docs = _parse_docstring(func.__doc__)

    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        # Skip 'self' and special parameters
        if name in ("self", "cls"):
            continue

        # Skip ToolInvocation parameter (first param for decorated handlers)
        param_type = hints.get(name)
        if param_type is ToolInvocation or name == "invocation":
            continue

        # Determine JSON type
        json_type = _get_json_type(param_type)

        prop: dict[str, Any] = {"type": json_type}

        # Add description from docstring
        if name in param_docs:
            prop["description"] = param_docs[name]

        # Check if required
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            # Add default value
            if param.default is not None:
                prop["default"] = param.default

        properties[name] = prop

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }

    if required:
        schema["required"] = required

    return schema


def define_tool(
    name: str | None = None,
    description: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Tool]:
    """
    Decorator to define a tool for use with Gemini models.

    This decorator converts a Python function into a Tool object that
    can be registered with a GeminiSession. The function's type hints
    and docstring are used to generate the tool's parameter schema.

    Args:
        name: The tool name. If not provided, uses the function name.
        description: Tool description. If not provided, uses the function's
            docstring first line.
        parameters: JSON Schema for parameters. If not provided, inferred
            from function signature.

    Returns:
        A decorator that creates a Tool from a function.

    Example:
        >>> @define_tool(
        ...     name="search",
        ...     description="Search the web for information",
        ... )
        ... async def search(query: str, max_results: int = 5) -> str:
        ...     '''Search the web.
        ...
        ...     Args:
        ...         query: The search query.
        ...         max_results: Maximum number of results to return.
        ...     '''
        ...     # Implementation
        ...     return f"Results for: {query}"

        >>> # The tool can now be used with a session
        >>> session = await client.create_session({
        ...     "tools": [search],
        ... })
    """

    def decorator(func: Callable[..., Any]) -> Tool:
        # Determine tool name
        tool_name = name or getattr(func, "__name__", "unnamed_tool")

        # Determine description
        tool_description = description
        if not tool_description and func.__doc__:
            # Use first line of docstring
            first_line = func.__doc__.strip().split("\n")[0]
            tool_description = first_line
        tool_description = tool_description or f"Tool: {tool_name}"

        # Determine parameters schema
        tool_params = parameters
        if tool_params is None:
            tool_params = _infer_schema_from_function(func)

        # Create a wrapper that handles ToolInvocation
        @functools.wraps(func)
        async def async_handler(invocation: ToolInvocation) -> ToolResult:
            args = invocation.get("arguments", {})

            # Call the original function
            if asyncio.iscoroutinefunction(func):
                result = await func(**args)
            else:
                result = func(**args)

            # Convert result to ToolResult
            if isinstance(result, dict):
                return result
            return {"text_result_for_llm": str(result)}

        @functools.wraps(func)
        def sync_handler(invocation: ToolInvocation) -> ToolResult:
            args = invocation.get("arguments", {})
            result = func(**args)

            if isinstance(result, dict):
                return result
            return {"text_result_for_llm": str(result)}

        # Choose appropriate handler
        handler = async_handler if asyncio.iscoroutinefunction(func) else sync_handler

        # Create Tool object
        tool = Tool(
            name=tool_name,
            description=tool_description,
            parameters=tool_params,
            handler=handler,
        )

        # Store original function for reference
        tool._original_func = func  # type: ignore

        return tool

    return decorator


def create_tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    handler: Callable[[ToolInvocation], Any] | None = None,
) -> Tool:
    """
    Create a tool programmatically.

    This is an alternative to the @define_tool decorator for when
    you need to create tools dynamically.

    Args:
        name: The tool name.
        description: Tool description.
        parameters: JSON Schema for parameters.
        handler: Optional handler function.

    Returns:
        A Tool object.

    Example:
        >>> tool = create_tool(
        ...     name="calculator",
        ...     description="Perform calculations",
        ...     parameters={
        ...         "type": "object",
        ...         "properties": {
        ...             "expression": {
        ...                 "type": "string",
        ...                 "description": "Math expression to evaluate",
        ...             }
        ...         },
        ...         "required": ["expression"],
        ...     },
        ...     handler=lambda inv: {"text_result_for_llm": str(eval(inv["arguments"]["expression"]))},
        ... )
    """
    return Tool(
        name=name,
        description=description,
        parameters=parameters or {"type": "object", "properties": {}},
        handler=handler,
    )


class ToolRegistry:
    """
    Registry for managing tools.

    Provides a way to organize and retrieve tools by name or category.

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(search_tool)
        >>> registry.register(calculator_tool)
        >>>
        >>> # Get all tools
        >>> tools = registry.get_all()
        >>>
        >>> # Use with session
        >>> session = await client.create_session({"tools": tools})
    """

    def __init__(self) -> None:
        """Initialize the tool registry."""
        self._tools: dict[str, Tool] = {}
        self._categories: dict[str, set[str]] = {}

    def register(self, tool: Tool, category: str | None = None) -> None:
        """
        Register a tool.

        Args:
            tool: The tool to register.
            category: Optional category for organization.
        """
        self._tools[tool.name] = tool

        if category:
            if category not in self._categories:
                self._categories[category] = set()
            self._categories[category].add(tool.name)

    def unregister(self, name: str) -> None:
        """
        Unregister a tool.

        Args:
            name: The tool name.
        """
        self._tools.pop(name, None)
        for category_tools in self._categories.values():
            category_tools.discard(name)

    def get(self, name: str) -> Tool | None:
        """
        Get a tool by name.

        Args:
            name: The tool name.

        Returns:
            The tool, or None if not found.
        """
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        """
        Get all registered tools.

        Returns:
            List of all tools.
        """
        return list(self._tools.values())

    def get_by_category(self, category: str) -> list[Tool]:
        """
        Get tools in a category.

        Args:
            category: The category name.

        Returns:
            List of tools in the category.
        """
        tool_names = self._categories.get(category, set())
        return [self._tools[name] for name in tool_names if name in self._tools]

    def list_categories(self) -> list[str]:
        """
        List all categories.

        Returns:
            List of category names.
        """
        return list(self._categories.keys())


# Global default registry
_default_registry = ToolRegistry()


def get_default_registry() -> ToolRegistry:
    """Get the default tool registry."""
    return _default_registry


def register_tool(tool: Tool, category: str | None = None) -> None:
    """Register a tool with the default registry."""
    _default_registry.register(tool, category)
