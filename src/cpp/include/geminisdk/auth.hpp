/**
 * @file auth.hpp
 * @brief OAuth authentication for GeminiSDK C++
 */

#ifndef GEMINISDK_AUTH_HPP
#define GEMINISDK_AUTH_HPP

#include "types.hpp"
#include <memory>
#include <mutex>

namespace geminisdk {

/**
 * OAuth manager for Gemini CLI / Code Assist API
 */
class OAuthManager {
public:
    /**
     * Create an OAuth manager
     * @param oauth_path Custom path to credentials file
     * @param client_id OAuth client ID
     * @param client_secret OAuth client secret
     */
    OAuthManager(
        const std::optional<std::string>& oauth_path = std::nullopt,
        const std::optional<std::string>& client_id = std::nullopt,
        const std::optional<std::string>& client_secret = std::nullopt
    );
    
    ~OAuthManager();
    
    /**
     * Ensure we have a valid access token
     * @param force_refresh Force refresh even if token is valid
     * @return Access token
     */
    std::string ensure_authenticated(bool force_refresh = false);
    
    /**
     * Get current credentials
     * @return OAuth credentials
     */
    GeminiOAuthCredentials get_credentials();
    
    /**
     * Invalidate cached credentials
     */
    void invalidate_credentials();
    
    /**
     * Get API endpoint URL
     * @return Endpoint URL
     */
    std::string get_api_endpoint() const;
    
    /**
     * Get project ID
     * @return Project ID or empty string
     */
    std::string get_project_id() const;
    
    /**
     * Set project ID
     * @param project_id Project ID
     */
    void set_project_id(const std::string& project_id);
    
private:
    std::string get_credential_path() const;
    GeminiOAuthCredentials load_cached_credentials();
    void save_credentials(const GeminiOAuthCredentials& credentials);
    GeminiOAuthCredentials refresh_access_token(const GeminiOAuthCredentials& credentials);
    bool is_token_valid(const GeminiOAuthCredentials& credentials) const;
    
    std::optional<std::string> oauth_path_;
    std::string client_id_;
    std::string client_secret_;
    std::optional<GeminiOAuthCredentials> credentials_;
    std::string project_id_;
    mutable std::mutex mutex_;
};

} // namespace geminisdk

#endif // GEMINISDK_AUTH_HPP
