/**
 * @file backend.hpp
 * @brief Backend for Gemini API communication
 */

#ifndef GEMINISDK_BACKEND_HPP
#define GEMINISDK_BACKEND_HPP

#include "types.hpp"
#include "auth.hpp"
#include <memory>
#include <functional>

namespace geminisdk {

/**
 * Backend options
 */
struct BackendOptions {
    std::optional<double> timeout;
    std::optional<std::string> oauth_path;
    std::optional<std::string> client_id;
    std::optional<std::string> client_secret;
};

/**
 * Backend for Gemini CLI / Code Assist API
 */
class Backend {
public:
    /**
     * Create a backend
     * @param options Configuration options
     */
    explicit Backend(const BackendOptions& options = {});
    
    ~Backend();
    
    /**
     * Perform a non-streaming completion
     * @param model Model name
     * @param messages Conversation messages
     * @param generation_config Generation configuration
     * @param thinking_config Thinking configuration
     * @param tools Available tools
     * @return Response chunk
     */
    LLMChunk complete(
        const std::string& model,
        const std::vector<Message>& messages,
        const std::optional<GenerationConfig>& generation_config = std::nullopt,
        const std::optional<ThinkingConfig>& thinking_config = std::nullopt,
        const std::vector<Tool>& tools = {}
    );
    
    /**
     * Perform a streaming completion
     * @param model Model name
     * @param messages Conversation messages
     * @param callback Callback for each chunk
     * @param generation_config Generation configuration
     * @param thinking_config Thinking configuration
     * @param tools Available tools
     */
    void complete_streaming(
        const std::string& model,
        const std::vector<Message>& messages,
        const StreamCallback& callback,
        const std::optional<GenerationConfig>& generation_config = std::nullopt,
        const std::optional<ThinkingConfig>& thinking_config = std::nullopt,
        const std::vector<Tool>& tools = {}
    );
    
    /**
     * Get OAuth manager
     * @return OAuth manager reference
     */
    OAuthManager& oauth_manager() { return oauth_manager_; }
    
    /**
     * List available models
     * @return List of model names
     */
    std::vector<std::string> list_models() const;
    
private:
    std::map<std::string, std::string> get_auth_headers(bool force_refresh = false);
    json prepare_messages(const std::vector<Message>& messages);
    json prepare_tools(const std::vector<Tool>& tools);
    std::string ensure_project_id(const std::string& access_token);
    std::string onboard_for_project(const std::string& access_token, const std::string& env_project_id, const std::string& tier_id);
    json build_request_payload(
        const std::string& model,
        const std::vector<Message>& messages,
        const std::optional<GenerationConfig>& generation_config,
        const std::optional<ThinkingConfig>& thinking_config,
        const std::vector<Tool>& tools,
        const std::string& project_id
    );
    LLMChunk parse_completion_response(const json& data);
    void handle_http_error(int status_code, const std::string& body);
    
    LLMChunk complete_with_retry(
        const std::string& model,
        const std::vector<Message>& messages,
        const std::optional<GenerationConfig>& generation_config,
        const std::optional<ThinkingConfig>& thinking_config,
        const std::vector<Tool>& tools,
        int retry_count
    );
    
    void complete_streaming_with_retry(
        const std::string& model,
        const std::vector<Message>& messages,
        const StreamCallback& callback,
        const std::optional<GenerationConfig>& generation_config,
        const std::optional<ThinkingConfig>& thinking_config,
        const std::vector<Tool>& tools,
        int retry_count
    );
    
    double timeout_;
    OAuthManager oauth_manager_;
    std::string project_id_;
    mutable std::mutex mutex_;
};

} // namespace geminisdk

#endif // GEMINISDK_BACKEND_HPP
