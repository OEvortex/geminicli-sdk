/**
 * GeminiSDK Session - Manages individual conversation sessions.
 */

import { GeminiBackend } from './backend.js';
import { SessionClosedError } from './exceptions.js';
import {
  EventType,
  GenerationConfig,
  Message,
  MessageOptions,
  Role,
  SessionEvent,
  SessionEventHandler,
  ThinkingConfig,
  Tool,
  ToolCall,
  ToolHandler,
  ToolInvocation,
} from './types.js';

export class GeminiSession {
  private readonly _sessionId: string;
  private readonly _model: string;
  private readonly _backend: GeminiBackend;
  private _tools: Tool[];
  private readonly _toolHandlers: Map<string, ToolHandler>;
  private readonly _systemMessage?: string;
  private readonly _generationConfig?: GenerationConfig;
  private readonly _thinkingConfig?: ThinkingConfig;
  private readonly _streaming: boolean;

  private _messages: Message[] = [];
  private readonly _eventHandlers: SessionEventHandler[] = [];
  private _closed = false;
  private readonly _startTime: Date;
  private _modifiedTime: Date;

  constructor(options: {
    sessionId: string;
    model: string;
    backend: GeminiBackend;
    tools?: Tool[];
    systemMessage?: string;
    generationConfig?: GenerationConfig;
    thinkingConfig?: ThinkingConfig;
    streaming?: boolean;
  }) {
    this._sessionId = options.sessionId;
    this._model = options.model;
    this._backend = options.backend;
    this._tools = options.tools ?? [];
    this._systemMessage = options.systemMessage;
    this._generationConfig = options.generationConfig;
    this._thinkingConfig = options.thinkingConfig;
    this._streaming = options.streaming ?? true;

    this._startTime = new Date();
    this._modifiedTime = new Date();

    this._toolHandlers = new Map();
    for (const tool of this._tools) {
      if (tool.handler) {
        this._toolHandlers.set(tool.name, tool.handler);
      }
    }

    if (this._systemMessage) {
      this._messages.push({
        role: Role.SYSTEM,
        content: this._systemMessage,
      });
    }
  }

  get sessionId(): string {
    return this._sessionId;
  }

  get model(): string {
    return this._model;
  }

  get startTime(): Date {
    return this._startTime;
  }

  get modifiedTime(): Date {
    return this._modifiedTime;
  }

  get messages(): Message[] {
    return [...this._messages];
  }

  public on(handler: SessionEventHandler): () => void {
    this._eventHandlers.push(handler);
    return () => {
      const index = this._eventHandlers.indexOf(handler);
      if (index > -1) {
        this._eventHandlers.splice(index, 1);
      }
    };
  }

  private emit(eventType: EventType, data: unknown): void {
    const event: SessionEvent = {
      type: eventType,
      data,
      sessionId: this._sessionId,
    };

    for (const handler of this._eventHandlers) {
      try {
        handler(event);
      } catch (e) {
        console.warn('Event handler error:', e);
      }
    }
  }

  public async send(options: MessageOptions): Promise<void> {
    if (this._closed) {
      throw new SessionClosedError(this._sessionId);
    }

    const prompt = options.prompt;
    const context = options.context;

    let content = prompt;
    if (context) {
      content = `${context}\n\n${prompt}`;
    }

    const userMessage: Message = {
      role: Role.USER,
      content,
    };
    this._messages.push(userMessage);
    this._modifiedTime = new Date();

    try {
      if (this._streaming) {
        await this.streamResponse();
      } else {
        await this.getResponse();
      }
    } catch (e) {
      this.emit(EventType.SESSION_ERROR, { error: String(e) });
      throw e;
    }
  }

  public async sendAndWait(options: MessageOptions): Promise<SessionEvent> {
    return new Promise((resolve, reject) => {
      let responseEvent: SessionEvent | null = null;

      const unsubscribe = this.on((event) => {
        if (event.type === EventType.ASSISTANT_MESSAGE) {
          responseEvent = event;
        } else if (
          event.type === EventType.SESSION_IDLE ||
          event.type === EventType.SESSION_ERROR
        ) {
          unsubscribe();
          if (responseEvent) {
            resolve(responseEvent);
          } else if (event.type === EventType.SESSION_ERROR) {
            reject(new Error(String((event.data as Record<string, unknown>)?.['error'])));
          } else {
            reject(new Error('No response received'));
          }
        }
      });

      this.send(options).catch((e) => {
        unsubscribe();
        reject(e);
      });
    });
  }

  private async streamResponse(): Promise<void> {
    let fullContent = '';
    let fullReasoning = '';
    const allToolCalls: ToolCall[] = [];
    let finalUsage: unknown;

    for await (const chunk of this._backend.completeStreaming({
      model: this._model,
      messages: this._messages,
      generationConfig: this._generationConfig,
      thinkingConfig: this._thinkingConfig,
      tools: this._tools.length > 0 ? this._tools : undefined,
    })) {
      if (chunk.content) {
        fullContent += chunk.content;
        this.emit(EventType.ASSISTANT_MESSAGE_DELTA, {
          deltaContent: chunk.content,
          content: fullContent,
        });
      }

      if (chunk.reasoningContent) {
        fullReasoning += chunk.reasoningContent;
        this.emit(EventType.ASSISTANT_REASONING_DELTA, {
          deltaContent: chunk.reasoningContent,
          content: fullReasoning,
        });
      }

      if (chunk.toolCalls) {
        allToolCalls.push(...chunk.toolCalls);
      }

      if (chunk.usage) {
        finalUsage = chunk.usage;
      }
    }

    if (allToolCalls.length > 0) {
      await this.handleToolCalls(allToolCalls);
    }

    const assistantMessage: Message = {
      role: Role.ASSISTANT,
      content: fullContent,
      toolCalls: allToolCalls.length > 0 ? allToolCalls : undefined,
    };
    this._messages.push(assistantMessage);

    if (fullReasoning) {
      this.emit(EventType.ASSISTANT_REASONING, {
        content: fullReasoning,
      });
    }

    this.emit(EventType.ASSISTANT_MESSAGE, {
      content: fullContent,
      toolCalls: allToolCalls.length > 0 ? allToolCalls : undefined,
      usage: finalUsage,
    });

    this.emit(EventType.SESSION_IDLE, {});
  }

  private async getResponse(): Promise<void> {
    const chunk = await this._backend.complete({
      model: this._model,
      messages: this._messages,
      generationConfig: this._generationConfig,
      thinkingConfig: this._thinkingConfig,
      tools: this._tools.length > 0 ? this._tools : undefined,
    });

    if (chunk.toolCalls) {
      await this.handleToolCalls(chunk.toolCalls);
    }

    const assistantMessage: Message = {
      role: Role.ASSISTANT,
      content: chunk.content,
      toolCalls: chunk.toolCalls,
    };
    this._messages.push(assistantMessage);

    if (chunk.reasoningContent) {
      this.emit(EventType.ASSISTANT_REASONING, {
        content: chunk.reasoningContent,
      });
    }

    this.emit(EventType.ASSISTANT_MESSAGE, {
      content: chunk.content,
      toolCalls: chunk.toolCalls,
      usage: chunk.usage,
    });

    this.emit(EventType.SESSION_IDLE, {});
  }

  private async handleToolCalls(toolCalls: ToolCall[]): Promise<void> {
    for (const toolCall of toolCalls) {
      const toolName = toolCall.function.name;

      this.emit(EventType.TOOL_CALL, {
        name: toolName,
        arguments: toolCall.function.arguments,
        callId: toolCall.id,
      });

      const handler = this._toolHandlers.get(toolName);
      if (!handler) {
        console.warn(`No handler for tool: ${toolName}`);
        this._messages.push({
          role: Role.USER,
          content: `Error: Tool '${toolName}' not found`,
          toolCallId: toolCall.id,
          name: toolName,
        });
        continue;
      }

      try {
        const invocation: ToolInvocation = {
          name: toolName,
          arguments:
            typeof toolCall.function.arguments === 'object'
              ? (toolCall.function.arguments as Record<string, unknown>)
              : {},
          callId: toolCall.id,
        };

        const result = await Promise.resolve(handler(invocation));
        const resultText = result.textResultForLlm ?? JSON.stringify(result);

        this.emit(EventType.TOOL_RESULT, {
          name: toolName,
          callId: toolCall.id,
          result: resultText,
        });

        this._messages.push({
          role: Role.USER,
          content: resultText,
          toolCallId: toolCall.id,
          name: toolName,
        });
      } catch (e) {
        const errorMsg = `Error executing tool '${toolName}': ${e}`;
        console.error(errorMsg);

        this.emit(EventType.TOOL_RESULT, {
          name: toolName,
          callId: toolCall.id,
          error: String(e),
        });

        this._messages.push({
          role: Role.USER,
          content: errorMsg,
          toolCallId: toolCall.id,
          name: toolName,
        });
      }
    }
  }

  public getMessages(): Message[] {
    return [...this._messages];
  }

  public addTool(tool: Tool): void {
    this._tools.push(tool);
    if (tool.handler) {
      this._toolHandlers.set(tool.name, tool.handler);
    }
  }

  public removeTool(toolName: string): void {
    this._tools = this._tools.filter((t) => t.name !== toolName);
    this._toolHandlers.delete(toolName);
  }

  public async clearHistory(): Promise<void> {
    if (this._systemMessage) {
      this._messages = [{ role: Role.SYSTEM, content: this._systemMessage }];
    } else {
      this._messages = [];
    }
    this._modifiedTime = new Date();
  }

  public async destroy(): Promise<void> {
    this._closed = true;
    this._eventHandlers.length = 0;
    this._toolHandlers.clear();
    this._messages = [];
  }
}
