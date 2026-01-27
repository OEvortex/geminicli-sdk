/**
 * @file session.hpp
 * @brief Session management for GeminiSDK C++
 */

#ifndef GEMINISDK_SESSION_HPP
#define GEMINISDK_SESSION_HPP

#include "types.hpp"
#include "backend.hpp"
#include <memory>
#include <mutex>
#include <vector>
#include <chrono>

namespace geminisdk {

/**
 * Conversation session
 */
class Session {
public:
    /**
     * Create a session
     * @param session_id Session identifier
     * @param model Model name
     * @param backend Backend reference
     * @param tools Available tools
     * @param system_message System message
     * @param generation_config Generation configuration
     * @param thinking_config Thinking configuration
     * @param streaming Enable streaming
     */
    Session(
        const std::string& session_id,
        const std::string& model,
        std::shared_ptr<Backend> backend,
        const std::vector<Tool>& tools = {},
        const std::optional<std::string>& system_message = std::nullopt,
        const std::optional<GenerationConfig>& generation_config = std::nullopt,
        const std::optional<ThinkingConfig>& thinking_config = std::nullopt,
        bool streaming = true
    );
    
    ~Session();
    
    // Getters
    const std::string& session_id() const { return session_id_; }
    const std::string& model() const { return model_; }
    std::chrono::system_clock::time_point start_time() const { return start_time_; }
    std::chrono::system_clock::time_point modified_time() const;
    std::vector<Message> messages() const;
    
    /**
     * Register a tool handler
     * @param name Tool name
     * @param handler Handler function
     */
    void register_tool_handler(const std::string& name, ToolHandler handler);
    
    /**
     * Register an event handler
     * @param handler Event handler function
     */
    void on(EventHandler handler);
    
    /**
     * Send a message
     * @param options Message options
     */
    void send(const MessageOptions& options);
    
    /**
     * Send a message and wait for response
     * @param options Message options
     * @return Response event
     */
    SessionEvent send_and_wait(const MessageOptions& options);
    
    /**
     * Add a tool
     * @param tool Tool definition
     */
    void add_tool(const Tool& tool);
    
    /**
     * Remove a tool
     * @param tool_name Tool name
     */
    void remove_tool(const std::string& tool_name);
    
    /**
     * Clear conversation history
     */
    void clear_history();
    
    /**
     * Destroy the session
     */
    void destroy();
    
private:
    void emit(EventType event_type, const json& data);
    void stream_response();
    void get_response();
    void handle_tool_calls(const std::vector<ToolCall>& tool_calls);
    
    std::string session_id_;
    std::string model_;
    std::shared_ptr<Backend> backend_;
    std::vector<Tool> tools_;
    std::map<std::string, ToolHandler> tool_handlers_;
    std::optional<std::string> system_message_;
    std::optional<GenerationConfig> generation_config_;
    std::optional<ThinkingConfig> thinking_config_;
    bool streaming_;
    
    std::vector<Message> messages_;
    std::vector<EventHandler> event_handlers_;
    bool closed_;
    std::chrono::system_clock::time_point start_time_;
    std::chrono::system_clock::time_point modified_time_;
    mutable std::mutex mutex_;
};

} // namespace geminisdk

#endif // GEMINISDK_SESSION_HPP
