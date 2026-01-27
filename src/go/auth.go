package geminisdk

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"
)

// OAuthManager handles OAuth authentication for Gemini CLI
type OAuthManager struct {
	oauthPath    string
	clientID     string
	clientSecret string
	credentials  *GeminiOAuthCredentials
	projectID    string
	httpClient   *http.Client
	mu           sync.RWMutex
}

// NewOAuthManager creates a new OAuth manager
func NewOAuthManager(oauthPath, clientID, clientSecret string) *OAuthManager {
	if clientID == "" {
		clientID = GeminiOAuthClientID
	}
	if clientSecret == "" {
		clientSecret = GeminiOAuthClientSecret
	}

	return &OAuthManager{
		oauthPath:    oauthPath,
		clientID:     clientID,
		clientSecret: clientSecret,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (m *OAuthManager) getCredentialPath() string {
	return GetGeminiCLICredentialPath(m.oauthPath)
}

func (m *OAuthManager) loadCachedCredentials() (*GeminiOAuthCredentials, error) {
	keyFile := m.getCredentialPath()

	data, err := os.ReadFile(keyFile)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, NewCredentialsNotFoundError(keyFile)
		}
		return nil, err
	}

	var creds GeminiOAuthCredentials
	if err := json.Unmarshal(data, &creds); err != nil {
		return nil, err
	}

	return &creds, nil
}

func (m *OAuthManager) saveCredentials(creds *GeminiOAuthCredentials) error {
	keyFile := m.getCredentialPath()

	data, err := json.MarshalIndent(creds, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(keyFile, data, 0600)
}

func (m *OAuthManager) refreshAccessToken(creds *GeminiOAuthCredentials) (*GeminiOAuthCredentials, error) {
	if creds.RefreshToken == "" {
		return nil, NewTokenRefreshError("No refresh token available", 0, "")
	}

	scope := strings.Join(GeminiOAuthScopes, " ")
	data := url.Values{}
	data.Set("grant_type", "refresh_token")
	data.Set("refresh_token", creds.RefreshToken)
	data.Set("client_id", m.clientID)
	data.Set("client_secret", m.clientSecret)
	data.Set("scope", scope)

	req, err := http.NewRequest("POST", GeminiOAuthTokenEndpoint, strings.NewReader(data.Encode()))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", GetUserAgent())

	resp, err := m.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode != http.StatusOK {
		return nil, NewTokenRefreshError(
			fmt.Sprintf("Token refresh failed: %d", resp.StatusCode),
			resp.StatusCode,
			string(body),
		)
	}

	var tokenResp struct {
		AccessToken  string `json:"access_token"`
		RefreshToken string `json:"refresh_token"`
		TokenType    string `json:"token_type"`
		ExpiresIn    int64  `json:"expires_in"`
		Error        string `json:"error"`
		ErrorDesc    string `json:"error_description"`
	}

	if err := json.Unmarshal(body, &tokenResp); err != nil {
		return nil, err
	}

	if tokenResp.Error != "" {
		return nil, NewTokenRefreshError(
			fmt.Sprintf("%s: %s", tokenResp.Error, tokenResp.ErrorDesc),
			0, "",
		)
	}

	refreshToken := tokenResp.RefreshToken
	if refreshToken == "" {
		refreshToken = creds.RefreshToken
	}

	tokenType := tokenResp.TokenType
	if tokenType == "" {
		tokenType = "Bearer"
	}

	expiresIn := tokenResp.ExpiresIn
	if expiresIn == 0 {
		expiresIn = 3600
	}

	newCreds := &GeminiOAuthCredentials{
		AccessToken:  tokenResp.AccessToken,
		RefreshToken: refreshToken,
		TokenType:    tokenType,
		ExpiryDate:   time.Now().UnixMilli() + expiresIn*1000,
	}

	if err := m.saveCredentials(newCreds); err != nil {
		// Log but don't fail
		fmt.Printf("Warning: Failed to save credentials: %v\n", err)
	}

	return newCreds, nil
}

func (m *OAuthManager) isTokenValid(creds *GeminiOAuthCredentials) bool {
	if creds.ExpiryDate == 0 {
		return false
	}
	return time.Now().UnixMilli() < creds.ExpiryDate-TokenRefreshBufferMs
}

// InvalidateCredentials clears cached credentials
func (m *OAuthManager) InvalidateCredentials() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.credentials = nil
}

// EnsureAuthenticated ensures we have a valid access token
func (m *OAuthManager) EnsureAuthenticated(forceRefresh bool) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.credentials == nil {
		creds, err := m.loadCachedCredentials()
		if err != nil {
			return "", err
		}
		m.credentials = creds
	}

	if forceRefresh || !m.isTokenValid(m.credentials) {
		newCreds, err := m.refreshAccessToken(m.credentials)
		if err != nil {
			return "", err
		}
		m.credentials = newCreds
	}

	return m.credentials.AccessToken, nil
}

// GetCredentials returns current credentials
func (m *OAuthManager) GetCredentials() (*GeminiOAuthCredentials, error) {
	if _, err := m.EnsureAuthenticated(false); err != nil {
		return nil, err
	}
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.credentials, nil
}

// GetAPIEndpoint returns the API endpoint URL
func (m *OAuthManager) GetAPIEndpoint() string {
	return fmt.Sprintf("%s/%s", GeminiCodeAssistEndpoint, GeminiCodeAssistAPIVersion)
}

// GetProjectID returns the project ID
func (m *OAuthManager) GetProjectID() string {
	// Check environment variable first
	if projectID := os.Getenv("GOOGLE_CLOUD_PROJECT"); projectID != "" {
		return projectID
	}

	// Check .env file
	envFile := GetGeminiCLIEnvPath("")
	if data, err := os.ReadFile(envFile); err == nil {
		scanner := bufio.NewScanner(bytes.NewReader(data))
		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if strings.HasPrefix(line, "GOOGLE_CLOUD_PROJECT=") {
				value := strings.TrimPrefix(line, "GOOGLE_CLOUD_PROJECT=")
				value = strings.Trim(value, "\"'")
				return value
			}
		}
	}

	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.projectID
}

// SetProjectID sets the project ID
func (m *OAuthManager) SetProjectID(projectID string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.projectID = projectID
}
