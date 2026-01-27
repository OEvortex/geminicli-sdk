/**
 * GeminiSDK Tools - Tool definition utilities.
 */

import {
  Tool,
  ToolHandler,
  ToolInvocation,
  ToolResult,
} from './types.js';

const TYPE_MAPPING: Record<string, string> = {
  string: 'string',
  number: 'number',
  boolean: 'boolean',
  object: 'object',
  array: 'array',
};

export interface ToolDefinitionOptions {
  name?: string;
  description?: string;
  parameters?: Record<string, unknown>;
}

/**
 * Define a tool for use with Gemini models.
 */
export function defineTool<T extends Record<string, unknown>>(
  options: ToolDefinitionOptions,
  handler: (args: T) => unknown | Promise<unknown>
): Tool {
  const toolName = options.name ?? handler.name ?? 'unnamed_tool';
  const description = options.description ?? `Tool: ${toolName}`;
  const parameters = options.parameters ?? { type: 'object', properties: {} };

  const wrappedHandler: ToolHandler = async (invocation: ToolInvocation): Promise<ToolResult> => {
    const result = await Promise.resolve(handler(invocation.arguments as T));

    if (typeof result === 'object' && result !== null && 'textResultForLlm' in result) {
      return result as ToolResult;
    }

    return { textResultForLlm: String(result) };
  };

  return {
    name: toolName,
    description,
    parameters,
    handler: wrappedHandler,
  };
}

/**
 * Create a tool programmatically.
 */
export function createTool(
  name: string,
  description: string,
  parameters?: Record<string, unknown>,
  handler?: ToolHandler
): Tool {
  return {
    name,
    description,
    parameters: parameters ?? { type: 'object', properties: {} },
    handler,
  };
}

/**
 * Registry for managing tools.
 */
export class ToolRegistry {
  private tools: Map<string, Tool> = new Map();
  private categories: Map<string, Set<string>> = new Map();

  public register(tool: Tool, category?: string): void {
    this.tools.set(tool.name, tool);

    if (category) {
      if (!this.categories.has(category)) {
        this.categories.set(category, new Set());
      }
      this.categories.get(category)!.add(tool.name);
    }
  }

  public unregister(name: string): void {
    this.tools.delete(name);
    for (const categoryTools of this.categories.values()) {
      categoryTools.delete(name);
    }
  }

  public get(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  public getAll(): Tool[] {
    return Array.from(this.tools.values());
  }

  public getByCategory(category: string): Tool[] {
    const toolNames = this.categories.get(category);
    if (!toolNames) return [];
    return Array.from(toolNames)
      .map((name) => this.tools.get(name))
      .filter((tool): tool is Tool => tool !== undefined);
  }

  public listCategories(): string[] {
    return Array.from(this.categories.keys());
  }
}

// Global default registry
const defaultRegistry = new ToolRegistry();

export function getDefaultRegistry(): ToolRegistry {
  return defaultRegistry;
}

export function registerTool(tool: Tool, category?: string): void {
  defaultRegistry.register(tool, category);
}
