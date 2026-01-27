/**
 * @file client.hpp
 * @brief Main client for GeminiSDK C++
 */

#ifndef GEMINISDK_CLIENT_HPP
#define GEMINISDK_CLIENT_HPP

#include "types.hpp"
#include "backend.hpp"
#include "session.hpp"
#include <memory>
#include <map>
#include <mutex>

namespace geminisdk {

/**
 * Main GeminiSDK client
 */
class Client {
public:
    /**
     * Create a client
     * @param options Configuration options
     */
    explicit Client(const ClientOptions& options = {});
    
    ~Client();
    
    /**
     * Get current connection state
     * @return Connection state
     */
    ConnectionState state() const;
    
    /**
     * Start the client and authenticate
     */
    void start();
    
    /**
     * Stop the client
     */
    void stop();
    
    /**
     * Close the client (alias for stop)
     */
    void close();
    
    /**
     * Create a new session
     * @param config Session configuration
     * @return Session pointer
     */
    std::shared_ptr<Session> create_session(const SessionConfig& config = {});
    
    /**
     * Get an existing session
     * @param session_id Session ID
     * @return Session pointer
     */
    std::shared_ptr<Session> get_session(const std::string& session_id);
    
    /**
     * List all sessions
     * @return Session metadata list
     */
    std::vector<SessionMetadata> list_sessions() const;
    
    /**
     * Delete a session
     * @param session_id Session ID
     */
    void delete_session(const std::string& session_id);
    
    /**
     * Get authentication status
     * @return Status map
     */
    std::map<std::string, json> get_auth_status() const;
    
    /**
     * List available models
     * @return Model info list
     */
    std::vector<ModelInfo> list_models() const;
    
    /**
     * Force refresh authentication
     */
    void refresh_auth();
    
private:
    void start_auto_refresh();
    
    ClientOptions options_;
    ConnectionState state_;
    std::shared_ptr<Backend> backend_;
    std::unique_ptr<OAuthManager> oauth_manager_;
    std::map<std::string, std::shared_ptr<Session>> sessions_;
    bool started_;
    mutable std::mutex mutex_;
};

} // namespace geminisdk

#endif // GEMINISDK_CLIENT_HPP
