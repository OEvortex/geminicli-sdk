package geminisdk

import (
	"context"
	"encoding/json"
	"sync"
)

// ToolRegistry manages tool definitions and handlers
type ToolRegistry struct {
	tools    map[string]Tool
	handlers map[string]ToolHandler
	mu       sync.RWMutex
}

// NewToolRegistry creates a new tool registry
func NewToolRegistry() *ToolRegistry {
	return &ToolRegistry{
		tools:    make(map[string]Tool),
		handlers: make(map[string]ToolHandler),
	}
}

// Register adds a tool with its handler
func (r *ToolRegistry) Register(tool Tool, handler ToolHandler) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.tools[tool.Name] = tool
	r.handlers[tool.Name] = handler
}

// Tools returns all registered tools
func (r *ToolRegistry) Tools() []Tool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	result := make([]Tool, 0, len(r.tools))
	for _, tool := range r.tools {
		result = append(result, tool)
	}
	return result
}

// GetTool returns a tool by name
func (r *ToolRegistry) GetTool(name string) (Tool, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	tool, ok := r.tools[name]
	return tool, ok
}

// GetHandler returns a handler by name
func (r *ToolRegistry) GetHandler(name string) (ToolHandler, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	handler, ok := r.handlers[name]
	return handler, ok
}

// Execute runs a tool invocation
func (r *ToolRegistry) Execute(ctx context.Context, invocation ToolInvocation) ToolResult {
	r.mu.RLock()
	handler, ok := r.handlers[invocation.Name]
	r.mu.RUnlock()

	if !ok {
		return FailureResult("Tool '" + invocation.Name + "' not found")
	}

	return handler(ctx, invocation)
}

// Unregister removes a tool
func (r *ToolRegistry) Unregister(name string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.tools, name)
	delete(r.handlers, name)
}

// Has checks if a tool is registered
func (r *ToolRegistry) Has(name string) bool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	_, ok := r.tools[name]
	return ok
}

// Names returns all tool names
func (r *ToolRegistry) Names() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	result := make([]string, 0, len(r.tools))
	for name := range r.tools {
		result = append(result, name)
	}
	return result
}

// ToolParametersBuilder helps construct tool parameters
type ToolParametersBuilder struct {
	properties map[string]map[string]interface{}
	required   []string
}

// NewToolParameters creates a new parameters builder
func NewToolParameters() *ToolParametersBuilder {
	return &ToolParametersBuilder{
		properties: make(map[string]map[string]interface{}),
		required:   make([]string, 0),
	}
}

// AddString adds a string parameter
func (b *ToolParametersBuilder) AddString(name, description string) *ToolParametersBuilder {
	b.properties[name] = map[string]interface{}{
		"type":        "string",
		"description": description,
	}
	return b
}

// AddNumber adds a number parameter
func (b *ToolParametersBuilder) AddNumber(name, description string) *ToolParametersBuilder {
	b.properties[name] = map[string]interface{}{
		"type":        "number",
		"description": description,
	}
	return b
}

// AddInteger adds an integer parameter
func (b *ToolParametersBuilder) AddInteger(name, description string) *ToolParametersBuilder {
	b.properties[name] = map[string]interface{}{
		"type":        "integer",
		"description": description,
	}
	return b
}

// AddBoolean adds a boolean parameter
func (b *ToolParametersBuilder) AddBoolean(name, description string) *ToolParametersBuilder {
	b.properties[name] = map[string]interface{}{
		"type":        "boolean",
		"description": description,
	}
	return b
}

// AddEnum adds an enum parameter
func (b *ToolParametersBuilder) AddEnum(name, description string, values []string) *ToolParametersBuilder {
	b.properties[name] = map[string]interface{}{
		"type":        "string",
		"description": description,
		"enum":        values,
	}
	return b
}

// Required marks parameters as required
func (b *ToolParametersBuilder) Required(fields ...string) *ToolParametersBuilder {
	b.required = append(b.required, fields...)
	return b
}

// Build creates the parameters JSON
func (b *ToolParametersBuilder) Build() json.RawMessage {
	result := map[string]interface{}{
		"properties": b.properties,
		"required":   b.required,
	}
	data, _ := json.Marshal(result)
	return data
}

// BuildMap returns parameters as a map
func (b *ToolParametersBuilder) BuildMap() map[string]interface{} {
	return map[string]interface{}{
		"properties": b.properties,
		"required":   b.required,
	}
}

// DefineTool is a helper to create a tool with parameters builder
func DefineTool(name, description string, params *ToolParametersBuilder) Tool {
	var paramsJSON json.RawMessage
	if params != nil {
		paramsJSON = params.Build()
	}
	return Tool{
		Name:        name,
		Description: description,
		Parameters:  paramsJSON,
	}
}
