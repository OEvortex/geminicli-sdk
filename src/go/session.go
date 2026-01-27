package geminisdk

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// ToolHandler is a function that handles tool invocations
type ToolHandler func(ctx context.Context, invocation ToolInvocation) ToolResult

// EventHandler is a function that handles session events
type EventHandler func(event SessionEvent)

// Session represents a conversation session
type Session struct {
	sessionID        string
	model            string
	backend          *Backend
	tools            []Tool
	toolHandlers     map[string]ToolHandler
	systemMessage    string
	generationConfig *GenerationConfig
	thinkingConfig   *ThinkingConfig
	streaming        bool

	messages      []Message
	eventHandlers []EventHandler
	closed        bool
	startTime     time.Time
	modifiedTime  time.Time
	mu            sync.RWMutex
}

// NewSession creates a new session
func NewSession(
	sessionID string,
	model string,
	backend *Backend,
	tools []Tool,
	systemMessage string,
	generationConfig *GenerationConfig,
	thinkingConfig *ThinkingConfig,
	streaming bool,
) *Session {
	now := time.Now()
	s := &Session{
		sessionID:        sessionID,
		model:            model,
		backend:          backend,
		tools:            tools,
		toolHandlers:     make(map[string]ToolHandler),
		systemMessage:    systemMessage,
		generationConfig: generationConfig,
		thinkingConfig:   thinkingConfig,
		streaming:        streaming,
		messages:         make([]Message, 0),
		eventHandlers:    make([]EventHandler, 0),
		closed:           false,
		startTime:        now,
		modifiedTime:     now,
	}

	if systemMessage != "" {
		s.messages = append(s.messages, Message{
			Role:    RoleSystem,
			Content: systemMessage,
		})
	}

	return s
}

// SessionID returns the session ID
func (s *Session) SessionID() string {
	return s.sessionID
}

// Model returns the model name
func (s *Session) Model() string {
	return s.model
}

// StartTime returns when the session started
func (s *Session) StartTime() time.Time {
	return s.startTime
}

// ModifiedTime returns when the session was last modified
func (s *Session) ModifiedTime() time.Time {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.modifiedTime
}

// Messages returns the conversation history
func (s *Session) Messages() []Message {
	s.mu.RLock()
	defer s.mu.RUnlock()
	result := make([]Message, len(s.messages))
	copy(result, s.messages)
	return result
}

// RegisterToolHandler registers a handler for a tool
func (s *Session) RegisterToolHandler(name string, handler ToolHandler) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.toolHandlers[name] = handler
}

// On registers an event handler
func (s *Session) On(handler EventHandler) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.eventHandlers = append(s.eventHandlers, handler)
}

func (s *Session) emit(eventType EventType, data map[string]interface{}) {
	event := SessionEvent{
		EventType: eventType,
		Data:      data,
		SessionID: s.sessionID,
	}

	s.mu.RLock()
	handlers := make([]EventHandler, len(s.eventHandlers))
	copy(handlers, s.eventHandlers)
	s.mu.RUnlock()

	for _, handler := range handlers {
		handler(event)
	}
}

// Send sends a message to the session
func (s *Session) Send(ctx context.Context, options *MessageOptions) error {
	s.mu.RLock()
	if s.closed {
		s.mu.RUnlock()
		return NewSessionClosedError(s.sessionID)
	}
	s.mu.RUnlock()

	content := options.Prompt
	if options.Context != "" {
		content = options.Context + "\n\n" + content
	}

	userMessage := Message{
		Role:    RoleUser,
		Content: content,
	}

	s.mu.Lock()
	s.messages = append(s.messages, userMessage)
	s.modifiedTime = time.Now()
	s.mu.Unlock()

	var err error
	if s.streaming {
		err = s.streamResponse(ctx)
	} else {
		err = s.getResponse(ctx)
	}

	if err != nil {
		s.emit(EventSessionError, map[string]interface{}{"error": err.Error()})
	}

	return err
}

// SendAndWait sends a message and waits for the response
func (s *Session) SendAndWait(ctx context.Context, options *MessageOptions) (*SessionEvent, error) {
	resultCh := make(chan *SessionEvent, 1)
	errCh := make(chan error, 1)

	handler := func(event SessionEvent) {
		switch event.EventType {
		case EventAssistantMessage, EventSessionIdle, EventSessionError:
			select {
			case resultCh <- &event:
			default:
			}
		}
	}

	s.On(handler)

	if err := s.Send(ctx, options); err != nil {
		return nil, err
	}

	select {
	case event := <-resultCh:
		return event, nil
	case err := <-errCh:
		return nil, err
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

func (s *Session) streamResponse(ctx context.Context) error {
	var fullContent string
	var fullReasoning string
	var allToolCalls []ToolCall
	var finalUsage *LLMUsage

	s.mu.RLock()
	messages := make([]Message, len(s.messages))
	copy(messages, s.messages)
	tools := s.tools
	s.mu.RUnlock()

	stream, err := s.backend.CompleteStreaming(
		ctx,
		s.model,
		messages,
		s.generationConfig,
		s.thinkingConfig,
		tools,
	)
	if err != nil {
		return err
	}

	for result := range stream {
		if result.Error != nil {
			return result.Error
		}

		chunk := result.Chunk
		if chunk.Content != "" {
			fullContent += chunk.Content
			s.emit(EventAssistantMessageDelta, map[string]interface{}{
				"deltaContent": chunk.Content,
				"content":      fullContent,
			})
		}

		if chunk.ReasoningContent != "" {
			fullReasoning += chunk.ReasoningContent
			s.emit(EventAssistantReasoningDelta, map[string]interface{}{
				"deltaContent": chunk.ReasoningContent,
				"content":      fullReasoning,
			})
		}

		if len(chunk.ToolCalls) > 0 {
			allToolCalls = append(allToolCalls, chunk.ToolCalls...)
		}

		if chunk.Usage != nil {
			finalUsage = chunk.Usage
		}
	}

	if len(allToolCalls) > 0 {
		if err := s.handleToolCalls(ctx, allToolCalls); err != nil {
			return err
		}
	}

	assistantMessage := Message{
		Role:      RoleAssistant,
		Content:   fullContent,
		ToolCalls: allToolCalls,
	}

	s.mu.Lock()
	s.messages = append(s.messages, assistantMessage)
	s.mu.Unlock()

	if fullReasoning != "" {
		s.emit(EventAssistantReasoning, map[string]interface{}{
			"content": fullReasoning,
		})
	}

	s.emit(EventAssistantMessage, map[string]interface{}{
		"content":   fullContent,
		"toolCalls": allToolCalls,
		"usage":     finalUsage,
	})

	s.emit(EventSessionIdle, map[string]interface{}{})

	return nil
}

func (s *Session) getResponse(ctx context.Context) error {
	s.mu.RLock()
	messages := make([]Message, len(s.messages))
	copy(messages, s.messages)
	tools := s.tools
	s.mu.RUnlock()

	chunk, err := s.backend.Complete(
		ctx,
		s.model,
		messages,
		s.generationConfig,
		s.thinkingConfig,
		tools,
	)
	if err != nil {
		return err
	}

	if len(chunk.ToolCalls) > 0 {
		if err := s.handleToolCalls(ctx, chunk.ToolCalls); err != nil {
			return err
		}
	}

	assistantMessage := Message{
		Role:      RoleAssistant,
		Content:   chunk.Content,
		ToolCalls: chunk.ToolCalls,
	}

	s.mu.Lock()
	s.messages = append(s.messages, assistantMessage)
	s.mu.Unlock()

	if chunk.ReasoningContent != "" {
		s.emit(EventAssistantReasoning, map[string]interface{}{
			"content": chunk.ReasoningContent,
		})
	}

	s.emit(EventAssistantMessage, map[string]interface{}{
		"content":   chunk.Content,
		"toolCalls": chunk.ToolCalls,
		"usage":     chunk.Usage,
	})

	s.emit(EventSessionIdle, map[string]interface{}{})

	return nil
}

func (s *Session) handleToolCalls(ctx context.Context, toolCalls []ToolCall) error {
	for _, tc := range toolCalls {
		toolName := tc.Function.Name

		s.emit(EventToolCall, map[string]interface{}{
			"name":      toolName,
			"arguments": json.RawMessage(tc.Function.Arguments),
			"callId":    tc.ID,
		})

		s.mu.RLock()
		handler, ok := s.toolHandlers[toolName]
		s.mu.RUnlock()

		if !ok {
			fmt.Printf("Warning: No handler for tool: %s\n", toolName)
			s.mu.Lock()
			s.messages = append(s.messages, Message{
				Role:       RoleUser,
				Content:    fmt.Sprintf("Error: Tool '%s' not found", toolName),
				Name:       toolName,
				ToolCallID: tc.ID,
			})
			s.mu.Unlock()
			continue
		}

		var args map[string]interface{}
		if err := json.Unmarshal(tc.Function.Arguments, &args); err != nil {
			args = make(map[string]interface{})
		}

		invocation := ToolInvocation{
			Name:      toolName,
			Arguments: args,
			CallID:    tc.ID,
		}

		result := handler(ctx, invocation)
		resultText := result.TextResultForLLM
		if resultText == "" {
			resultText = "Success"
		}

		s.emit(EventToolResult, map[string]interface{}{
			"name":   toolName,
			"callId": tc.ID,
			"result": resultText,
		})

		s.mu.Lock()
		s.messages = append(s.messages, Message{
			Role:       RoleUser,
			Content:    resultText,
			Name:       toolName,
			ToolCallID: tc.ID,
		})
		s.mu.Unlock()
	}

	return nil
}

// AddTool adds a tool to the session
func (s *Session) AddTool(tool Tool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.tools = append(s.tools, tool)
}

// RemoveTool removes a tool from the session
func (s *Session) RemoveTool(toolName string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	newTools := make([]Tool, 0, len(s.tools))
	for _, t := range s.tools {
		if t.Name != toolName {
			newTools = append(newTools, t)
		}
	}
	s.tools = newTools
	delete(s.toolHandlers, toolName)
}

// ClearHistory clears the conversation history
func (s *Session) ClearHistory() {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.messages = make([]Message, 0)
	if s.systemMessage != "" {
		s.messages = append(s.messages, Message{
			Role:    RoleSystem,
			Content: s.systemMessage,
		})
	}
	s.modifiedTime = time.Now()
}

// Destroy closes and cleans up the session
func (s *Session) Destroy() {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.closed = true
	s.eventHandlers = nil
	s.messages = nil
}

// CreateTool helper function to create a tool
func CreateTool(name, description string, parameters map[string]interface{}) Tool {
	var paramsJSON json.RawMessage
	if parameters != nil {
		paramsJSON, _ = json.Marshal(parameters)
	}
	return Tool{
		Name:        name,
		Description: description,
		Parameters:  paramsJSON,
	}
}

// SuccessResult creates a success tool result
func SuccessResult(text string) ToolResult {
	return ToolResult{
		ResultType:       ToolResultSuccess,
		TextResultForLLM: text,
	}
}

// FailureResult creates a failure tool result
func FailureResult(text string) ToolResult {
	return ToolResult{
		ResultType:       ToolResultFailure,
		TextResultForLLM: text,
	}
}

// RejectedResult creates a rejected tool result
func RejectedResult(text string) ToolResult {
	return ToolResult{
		ResultType:       ToolResultRejected,
		TextResultForLLM: text,
	}
}

// GenerateSessionID generates a new session ID
func GenerateSessionID() string {
	return uuid.New().String()
}
