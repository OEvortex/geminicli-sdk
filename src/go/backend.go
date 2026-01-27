package geminisdk

import (
	"bufio"
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
)

const (
	onboardMaxRetries  = 30
	onboardSleepSeconds = 2
)

// BackendOptions configures the backend
type BackendOptions struct {
	Timeout      time.Duration
	OAuthPath    string
	ClientID     string
	ClientSecret string
}

// Backend handles API communication
type Backend struct {
	timeout      time.Duration
	oauthManager *OAuthManager
	projectID    string
	httpClient   *http.Client
	mu           sync.RWMutex
}

// NewBackend creates a new backend
func NewBackend(opts *BackendOptions) *Backend {
	if opts == nil {
		opts = &BackendOptions{}
	}

	timeout := opts.Timeout
	if timeout == 0 {
		timeout = 720 * time.Second
	}

	return &Backend{
		timeout:      timeout,
		oauthManager: NewOAuthManager(opts.OAuthPath, opts.ClientID, opts.ClientSecret),
		httpClient: &http.Client{
			Timeout: timeout,
		},
	}
}

func (b *Backend) getAuthHeaders(forceRefresh bool) (map[string]string, error) {
	accessToken, err := b.oauthManager.EnsureAuthenticated(forceRefresh)
	if err != nil {
		return nil, err
	}

	return map[string]string{
		"Content-Type":  "application/json",
		"Authorization": fmt.Sprintf("Bearer %s", accessToken),
	}, nil
}

func (b *Backend) prepareMessages(messages []Message) []map[string]interface{} {
	var result []map[string]interface{}

	for _, msg := range messages {
		role := "user"
		if msg.Role == RoleAssistant {
			role = "model"
		}

		var contentParts []map[string]interface{}

		if msg.Content != "" {
			contentParts = append(contentParts, map[string]interface{}{
				"text": msg.Content,
			})
		}

		for _, part := range msg.Parts {
			if part.Text != "" {
				contentParts = append(contentParts, map[string]interface{}{
					"text": part.Text,
				})
			}
			if len(part.ImageData) > 0 && part.ImageMimeType != "" {
				b64Data := base64.StdEncoding.EncodeToString(part.ImageData)
				contentParts = append(contentParts, map[string]interface{}{
					"inlineData": map[string]interface{}{
						"mimeType": part.ImageMimeType,
						"data":     b64Data,
					},
				})
			}
		}

		for _, tc := range msg.ToolCalls {
			var args interface{}
			if err := json.Unmarshal(tc.Function.Arguments, &args); err != nil {
				args = map[string]interface{}{}
			}
			contentParts = append(contentParts, map[string]interface{}{
				"functionCall": map[string]interface{}{
					"name": tc.Function.Name,
					"args": args,
				},
			})
		}

		if msg.ToolCallID != "" {
			contentParts = append(contentParts, map[string]interface{}{
				"functionResponse": map[string]interface{}{
					"name": msg.Name,
					"response": map[string]interface{}{
						"result": msg.Content,
					},
				},
			})
		}

		if len(contentParts) > 0 {
			result = append(result, map[string]interface{}{
				"role":  role,
				"parts": contentParts,
			})
		}
	}

	return result
}

func (b *Backend) prepareTools(tools []Tool) []map[string]interface{} {
	if len(tools) == 0 {
		return nil
	}

	var funcDecls []map[string]interface{}
	for _, tool := range tools {
		funcDef := map[string]interface{}{
			"name":        tool.Name,
			"description": tool.Description,
		}

		if len(tool.Parameters) > 0 {
			var params map[string]interface{}
			if err := json.Unmarshal(tool.Parameters, &params); err == nil {
				funcDef["parameters"] = map[string]interface{}{
					"type":       "object",
					"properties": params["properties"],
					"required":   params["required"],
				}
			}
		}

		funcDecls = append(funcDecls, funcDef)
	}

	return []map[string]interface{}{
		{"functionDeclarations": funcDecls},
	}
}

func (b *Backend) ensureProjectID(ctx context.Context, accessToken string) (string, error) {
	b.mu.RLock()
	if b.projectID != "" {
		pid := b.projectID
		b.mu.RUnlock()
		return pid, nil
	}
	b.mu.RUnlock()

	envProjectID := b.oauthManager.GetProjectID()

	clientMetadata := map[string]interface{}{
		"ideType":     "IDE_UNSPECIFIED",
		"platform":    "PLATFORM_UNSPECIFIED",
		"pluginType":  "GEMINI",
		"duetProject": envProjectID,
	}

	loadRequest := map[string]interface{}{
		"cloudaicompanionProject": envProjectID,
		"metadata":                clientMetadata,
	}

	reqBody, _ := json.Marshal(loadRequest)
	url := fmt.Sprintf("%s:loadCodeAssist", b.oauthManager.GetAPIEndpoint())

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", accessToken))
	req.Header.Set("Content-Type", "application/json")

	resp, err := b.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode != http.StatusOK {
		return "", NewAPIError(
			fmt.Sprintf("Gemini Code Assist access denied: %s", string(body)),
			resp.StatusCode, url,
		)
	}

	var data map[string]interface{}
	if err := json.Unmarshal(body, &data); err != nil {
		return "", err
	}

	if _, ok := data["currentTier"]; ok {
		projectID := envProjectID
		if pid, ok := data["cloudaicompanionProject"].(string); ok && pid != "" {
			projectID = pid
		}
		b.mu.Lock()
		b.projectID = projectID
		b.mu.Unlock()
		return projectID, nil
	}

	// Need to onboard
	tierID := "free-tier"
	if tiers, ok := data["allowedTiers"].([]interface{}); ok {
		for _, t := range tiers {
			if tier, ok := t.(map[string]interface{}); ok {
				if isDefault, ok := tier["isDefault"].(bool); ok && isDefault {
					if id, ok := tier["id"].(string); ok {
						tierID = id
					}
					break
				}
			}
		}
	}

	return b.onboardForProject(ctx, accessToken, envProjectID, tierID)
}

func (b *Backend) onboardForProject(ctx context.Context, accessToken, envProjectID, tierID string) (string, error) {
	clientMetadata := map[string]interface{}{
		"ideType":     "IDE_UNSPECIFIED",
		"platform":    "PLATFORM_UNSPECIFIED",
		"pluginType":  "GEMINI",
		"duetProject": envProjectID,
	}

	onboardRequest := map[string]interface{}{
		"tierId":   tierID,
		"metadata": clientMetadata,
	}
	if tierID != "free-tier" {
		onboardRequest["cloudaicompanionProject"] = envProjectID
	}

	url := fmt.Sprintf("%s:onboardUser", b.oauthManager.GetAPIEndpoint())

	for i := 0; i < onboardMaxRetries; i++ {
		reqBody, _ := json.Marshal(onboardRequest)
		req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
		if err != nil {
			return "", err
		}
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", accessToken))
		req.Header.Set("Content-Type", "application/json")

		resp, err := b.httpClient.Do(req)
		if err != nil {
			return "", err
		}

		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			return "", NewOnboardingError("Onboard request failed", tierID)
		}

		var lroData map[string]interface{}
		if err := json.Unmarshal(body, &lroData); err != nil {
			return "", err
		}

		if done, ok := lroData["done"].(bool); ok && done {
			if response, ok := lroData["response"].(map[string]interface{}); ok {
				if project, ok := response["cloudaicompanionProject"].(map[string]interface{}); ok {
					if id, ok := project["id"].(string); ok {
						b.mu.Lock()
						b.projectID = id
						b.mu.Unlock()
						return id, nil
					}
				}
			}
			break
		}

		time.Sleep(onboardSleepSeconds * time.Second)
	}

	if tierID == "free-tier" {
		b.mu.Lock()
		b.projectID = ""
		b.mu.Unlock()
		return "", nil
	}

	return "", NewOnboardingError("Failed to complete onboarding", tierID)
}

func (b *Backend) buildRequestPayload(
	model string,
	messages []Message,
	generationConfig *GenerationConfig,
	thinkingConfig *ThinkingConfig,
	tools []Tool,
	projectID string,
) map[string]interface{} {
	genConfig := map[string]interface{}{
		"temperature": 0.7,
	}
	if generationConfig != nil {
		if generationConfig.Temperature != 0 {
			genConfig["temperature"] = generationConfig.Temperature
		}
		if generationConfig.MaxOutputTokens > 0 {
			genConfig["maxOutputTokens"] = generationConfig.MaxOutputTokens
		}
		if generationConfig.TopP > 0 {
			genConfig["topP"] = generationConfig.TopP
		}
		if generationConfig.TopK > 0 {
			genConfig["topK"] = generationConfig.TopK
		}
		if len(generationConfig.StopSequences) > 0 {
			genConfig["stopSequences"] = generationConfig.StopSequences
		}
	}

	if thinkingConfig != nil && thinkingConfig.IncludeThoughts {
		thinkingCfg := map[string]interface{}{
			"includeThoughts": true,
		}
		if thinkingConfig.ThinkingBudget > 0 {
			thinkingCfg["thinkingBudget"] = thinkingConfig.ThinkingBudget
		}
		genConfig["thinkingConfig"] = thinkingCfg
	}

	requestBody := map[string]interface{}{
		"contents":         b.prepareMessages(messages),
		"generationConfig": genConfig,
	}

	if preparedTools := b.prepareTools(tools); preparedTools != nil {
		requestBody["tools"] = preparedTools
	}

	payload := map[string]interface{}{
		"model":   model,
		"request": requestBody,
	}

	if projectID != "" {
		payload["project"] = projectID
	}

	return payload
}

func (b *Backend) parseCompletionResponse(data map[string]interface{}) *LLMChunk {
	responseData := data
	if resp, ok := data["response"].(map[string]interface{}); ok {
		responseData = resp
	}

	candidates, _ := responseData["candidates"].([]interface{})
	if len(candidates) == 0 {
		return &LLMChunk{}
	}

	candidate, _ := candidates[0].(map[string]interface{})
	content, _ := candidate["content"].(map[string]interface{})
	parts, _ := content["parts"].([]interface{})

	var textContent string
	var reasoningContent string
	var toolCalls []ToolCall

	for _, p := range parts {
		part, ok := p.(map[string]interface{})
		if !ok {
			continue
		}

		if text, ok := part["text"].(string); ok {
			textContent += text
		}
		if thought, ok := part["thought"].(string); ok {
			reasoningContent = thought
		}
		if fc, ok := part["functionCall"].(map[string]interface{}); ok {
			name, _ := fc["name"].(string)
			args := fc["args"]
			if args == nil {
				args = fc["arguments"]
			}
			argsJSON, _ := json.Marshal(args)

			toolCalls = append(toolCalls, ToolCall{
				ID:   uuid.New().String(),
				Type: "function",
				Function: FunctionCall{
					Name:      name,
					Arguments: argsJSON,
				},
			})
		}
	}

	var usage *LLMUsage
	usageData := data["usageMetadata"]
	if usageData == nil {
		usageData = responseData["usageMetadata"]
	}
	if u, ok := usageData.(map[string]interface{}); ok {
		usage = &LLMUsage{
			PromptTokens:     int64(getFloat(u, "promptTokenCount")),
			CompletionTokens: int64(getFloat(u, "candidatesTokenCount")),
			TotalTokens:      int64(getFloat(u, "totalTokenCount")),
		}
	}

	finishReason, _ := candidate["finishReason"].(string)

	return &LLMChunk{
		Content:          textContent,
		ReasoningContent: reasoningContent,
		ToolCalls:        toolCalls,
		Usage:            usage,
		FinishReason:     finishReason,
	}
}

func getFloat(m map[string]interface{}, key string) float64 {
	if v, ok := m[key].(float64); ok {
		return v
	}
	if v, ok := m[key].(int); ok {
		return float64(v)
	}
	return 0
}

// Complete performs a non-streaming completion
func (b *Backend) Complete(
	ctx context.Context,
	model string,
	messages []Message,
	generationConfig *GenerationConfig,
	thinkingConfig *ThinkingConfig,
	tools []Tool,
) (*LLMChunk, error) {
	return b.completeWithRetry(ctx, model, messages, generationConfig, thinkingConfig, tools, 0)
}

func (b *Backend) completeWithRetry(
	ctx context.Context,
	model string,
	messages []Message,
	generationConfig *GenerationConfig,
	thinkingConfig *ThinkingConfig,
	tools []Tool,
	retryCount int,
) (*LLMChunk, error) {
	headers, err := b.getAuthHeaders(retryCount > 0)
	if err != nil {
		return nil, err
	}

	accessToken := strings.TrimPrefix(headers["Authorization"], "Bearer ")
	projectID, err := b.ensureProjectID(ctx, accessToken)
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf("%s:generateContent", b.oauthManager.GetAPIEndpoint())
	payload := b.buildRequestPayload(model, messages, generationConfig, thinkingConfig, tools, projectID)

	reqBody, _ := json.Marshal(payload)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, err
	}

	for k, v := range headers {
		req.Header.Set(k, v)
	}

	resp, err := b.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	if (resp.StatusCode == 401 || resp.StatusCode == 403) && retryCount == 0 {
		b.oauthManager.InvalidateCredentials()
		return b.completeWithRetry(ctx, model, messages, generationConfig, thinkingConfig, tools, 1)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, b.handleHTTPError(resp.StatusCode, string(body))
	}

	var data map[string]interface{}
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, err
	}

	return b.parseCompletionResponse(data), nil
}

// ChunkChannel is used for streaming responses
type ChunkChannel <-chan StreamResult

// StreamResult contains either a chunk or an error
type StreamResult struct {
	Chunk *LLMChunk
	Error error
}

// CompleteStreaming performs a streaming completion
func (b *Backend) CompleteStreaming(
	ctx context.Context,
	model string,
	messages []Message,
	generationConfig *GenerationConfig,
	thinkingConfig *ThinkingConfig,
	tools []Tool,
) (ChunkChannel, error) {
	return b.completeStreamingWithRetry(ctx, model, messages, generationConfig, thinkingConfig, tools, 0)
}

func (b *Backend) completeStreamingWithRetry(
	ctx context.Context,
	model string,
	messages []Message,
	generationConfig *GenerationConfig,
	thinkingConfig *ThinkingConfig,
	tools []Tool,
	retryCount int,
) (ChunkChannel, error) {
	headers, err := b.getAuthHeaders(retryCount > 0)
	if err != nil {
		return nil, err
	}

	accessToken := strings.TrimPrefix(headers["Authorization"], "Bearer ")
	projectID, err := b.ensureProjectID(ctx, accessToken)
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf("%s:streamGenerateContent?alt=sse", b.oauthManager.GetAPIEndpoint())
	payload := b.buildRequestPayload(model, messages, generationConfig, thinkingConfig, tools, projectID)

	reqBody, _ := json.Marshal(payload)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, err
	}

	for k, v := range headers {
		req.Header.Set(k, v)
	}

	resp, err := b.httpClient.Do(req)
	if err != nil {
		return nil, err
	}

	if (resp.StatusCode == 401 || resp.StatusCode == 403) && retryCount == 0 {
		resp.Body.Close()
		b.oauthManager.InvalidateCredentials()
		return b.completeStreamingWithRetry(ctx, model, messages, generationConfig, thinkingConfig, tools, 1)
	}

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		return nil, b.handleHTTPError(resp.StatusCode, string(body))
	}

	ch := make(chan StreamResult, 100)

	go func() {
		defer close(ch)
		defer resp.Body.Close()

		scanner := bufio.NewScanner(resp.Body)
		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if line == "" || strings.HasPrefix(line, ":") {
				continue
			}

			if strings.HasPrefix(line, "data:") {
				data := strings.TrimSpace(strings.TrimPrefix(line, "data:"))
				if data == "[DONE]" {
					continue
				}

				var parsed map[string]interface{}
				if err := json.Unmarshal([]byte(data), &parsed); err != nil {
					continue
				}

				chunk := b.parseCompletionResponse(parsed)
				ch <- StreamResult{Chunk: chunk}
			}
		}

		if err := scanner.Err(); err != nil {
			ch <- StreamResult{Error: NewStreamError(err.Error())}
		}
	}()

	return ch, nil
}

func (b *Backend) handleHTTPError(statusCode int, body string) error {
	var errorMsg string
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(body), &data); err == nil {
		if errObj, ok := data["error"].(map[string]interface{}); ok {
			if msg, ok := errObj["message"].(string); ok {
				errorMsg = msg
			}
		}
	}
	if errorMsg == "" {
		errorMsg = body
	}

	switch statusCode {
	case 429:
		return NewRateLimitError(fmt.Sprintf("Rate limit exceeded: %s", errorMsg), 0)
	case 403:
		return &PermissionDeniedError{
			APIError: APIError{
				GeminiSDKError: GeminiSDKError{
					Message: fmt.Sprintf("Permission denied: %s", errorMsg),
					Code:    "PERMISSION_DENIED",
				},
				StatusCode: statusCode,
			},
		}
	default:
		return NewAPIError(fmt.Sprintf("API error: %s", errorMsg), statusCode, "")
	}
}

// ListModels returns available models
func (b *Backend) ListModels() []string {
	models := GetGeminiCLIModels()
	var names []string
	for name := range models {
		names = append(names, name)
	}
	return names
}

// GetOAuthManager returns the OAuth manager
func (b *Backend) GetOAuthManager() *OAuthManager {
	return b.oauthManager
}
