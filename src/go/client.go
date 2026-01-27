package geminisdk

import (
	"context"
	"sync"
	"time"
)

// Client is the main entry point for the GeminiSDK
type Client struct {
	options      *ClientOptions
	state        ConnectionState
	backend      *Backend
	oauthManager *OAuthManager
	sessions     map[string]*Session
	started      bool
	mu           sync.RWMutex
}

// NewClient creates a new GeminiSDK client
func NewClient(options *ClientOptions) *Client {
	if options == nil {
		options = &ClientOptions{
			AutoRefresh: true,
		}
	}

	return &Client{
		options:  options,
		state:    StateDisconnected,
		sessions: make(map[string]*Session),
		started:  false,
	}
}

// State returns the current connection state
func (c *Client) State() ConnectionState {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.state
}

// Start initializes the client and authenticates
func (c *Client) Start(ctx context.Context) error {
	c.mu.Lock()
	if c.started {
		c.mu.Unlock()
		return nil
	}

	c.state = StateConnecting
	c.mu.Unlock()

	oauthManager := NewOAuthManager(
		c.options.OAuthPath,
		c.options.ClientID,
		c.options.ClientSecret,
	)

	timeout := 720 * time.Second
	if c.options.Timeout > 0 {
		timeout = time.Duration(c.options.Timeout * float64(time.Second))
	}

	backend := NewBackend(&BackendOptions{
		Timeout:      timeout,
		OAuthPath:    c.options.OAuthPath,
		ClientID:     c.options.ClientID,
		ClientSecret: c.options.ClientSecret,
	})

	// Verify authentication
	if _, err := oauthManager.EnsureAuthenticated(false); err != nil {
		c.mu.Lock()
		c.state = StateError
		c.mu.Unlock()
		return err
	}

	c.mu.Lock()
	c.oauthManager = oauthManager
	c.backend = backend
	c.state = StateConnected
	c.started = true
	c.mu.Unlock()

	// Start auto-refresh if enabled
	if c.options.AutoRefresh {
		go c.autoRefreshLoop(ctx)
	}

	return nil
}

func (c *Client) autoRefreshLoop(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			c.mu.RLock()
			manager := c.oauthManager
			c.mu.RUnlock()

			if manager != nil {
				manager.EnsureAuthenticated(false)
			}
		}
	}
}

// Stop shuts down the client
func (c *Client) Stop() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	// Destroy all sessions
	for _, session := range c.sessions {
		session.Destroy()
	}
	c.sessions = make(map[string]*Session)

	c.backend = nil
	c.oauthManager = nil
	c.state = StateDisconnected
	c.started = false

	return nil
}

// Close is an alias for Stop
func (c *Client) Close() error {
	return c.Stop()
}

// CreateSession creates a new conversation session
func (c *Client) CreateSession(ctx context.Context, config *SessionConfig) (*Session, error) {
	c.mu.RLock()
	started := c.started
	backend := c.backend
	c.mu.RUnlock()

	if !started {
		if err := c.Start(ctx); err != nil {
			return nil, err
		}
		c.mu.RLock()
		backend = c.backend
		c.mu.RUnlock()
	}

	if backend == nil {
		return nil, NewConfigurationError("Client not connected")
	}

	sessionID := config.SessionID
	if sessionID == "" {
		sessionID = GenerateSessionID()
	}

	model := config.Model
	if model == "" {
		model = "gemini-2.5-pro"
	}

	session := NewSession(
		sessionID,
		model,
		backend,
		config.Tools,
		config.SystemMessage,
		config.GenerationConfig,
		config.ThinkingConfig,
		config.Streaming,
	)

	c.mu.Lock()
	c.sessions[sessionID] = session
	c.mu.Unlock()

	return session, nil
}

// GetSession returns an existing session by ID
func (c *Client) GetSession(sessionID string) (*Session, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	session, ok := c.sessions[sessionID]
	if !ok {
		return nil, NewSessionNotFoundError(sessionID)
	}

	return session, nil
}

// ListSessions returns metadata for all sessions
func (c *Client) ListSessions() []SessionMetadata {
	c.mu.RLock()
	defer c.mu.RUnlock()

	var result []SessionMetadata
	for _, session := range c.sessions {
		result = append(result, SessionMetadata{
			SessionID:    session.SessionID(),
			StartTime:    session.StartTime().Format(time.RFC3339),
			ModifiedTime: session.ModifiedTime().Format(time.RFC3339),
			Model:        session.Model(),
		})
	}

	return result
}

// DeleteSession removes a session
func (c *Client) DeleteSession(sessionID string) error {
	c.mu.Lock()
	session, ok := c.sessions[sessionID]
	if ok {
		delete(c.sessions, sessionID)
	}
	c.mu.Unlock()

	if session != nil {
		session.Destroy()
	}

	return nil
}

// GetAuthStatus returns the current authentication status
func (c *Client) GetAuthStatus() map[string]interface{} {
	status := make(map[string]interface{})

	c.mu.RLock()
	manager := c.oauthManager
	c.mu.RUnlock()

	if manager != nil {
		if creds, err := manager.GetCredentials(); err == nil {
			status["authenticated"] = true
			status["token_type"] = creds.TokenType
			status["expires_at"] = creds.ExpiryDate
			return status
		}
	}

	status["authenticated"] = false
	return status
}

// ListModels returns available models
func (c *Client) ListModels() []ModelInfo {
	models := GetGeminiCLIModels()
	var result []ModelInfo

	for id, info := range models {
		result = append(result, ModelInfo{
			ID:   id,
			Name: info.Name,
			Capabilities: ModelCapabilities{
				Supports: ModelSupports{
					Vision:   false,
					Tools:    info.SupportsNativeTools,
					Thinking: info.SupportsThinking,
				},
				Limits: ModelLimits{
					MaxPromptTokens:        &info.ContextWindow,
					MaxContextWindowTokens: &info.ContextWindow,
				},
			},
		})
	}

	return result
}

// RefreshAuth forces a token refresh
func (c *Client) RefreshAuth() error {
	c.mu.RLock()
	manager := c.oauthManager
	c.mu.RUnlock()

	if manager != nil {
		_, err := manager.EnsureAuthenticated(true)
		return err
	}

	return nil
}
