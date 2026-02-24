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
 * Normalize tool specifications into Tool objects.
 *
 * Accepts fully-formed Tool objects and declarative dict-style specs used by
 * gemini-cli built-in tools (e.g. `{ googleSearch: {} }`). Dict entries are
 * converted into Tool objects with no handler; the tool name is used as the
 * key and the value (if a non-empty object) is stored as the parameters schema.
 *
 * @param specs Array of Tool objects or declarative dict specs.
 * @returns Array of normalized Tool objects.
 */
export function normalizeTools(specs: Array<Tool | Record<string, unknown>>): Tool[] {
  return specs.flatMap((spec) => {
    if (typeof (spec as Tool).name === 'string' && typeof (spec as Tool).description === 'string') {
      return [spec as Tool];
    }
    return Object.entries(spec).map(([name, params]) =>
      createTool(
        name,
        `Tool: ${name}`,
        typeof params === 'object' && params !== null
          ? (params as Record<string, unknown>)
          : {},
      )
    );
  });
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
