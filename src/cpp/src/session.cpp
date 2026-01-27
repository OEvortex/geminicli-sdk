/**
 * @file session.cpp
 * @brief Session implementation for GeminiSDK C++
 */

#include "geminisdk/session.hpp"
#include "geminisdk/errors.hpp"
#include <iostream>

namespace geminisdk {

Session::Session(
    const std::string& session_id,
    const std::string& model,
    std::shared_ptr<Backend> backend,
    const std::vector<Tool>& tools,
    const std::optional<std::string>& system_message,
    const std::optional<GenerationConfig>& generation_config,
    const std::optional<ThinkingConfig>& thinking_config,
    bool streaming
) : session_id_(session_id),
    model_(model),
    backend_(backend),
    tools_(tools),
    system_message_(system_message),
    generation_config_(generation_config),
    thinking_config_(thinking_config),
    streaming_(streaming),
    closed_(false),
    start_time_(std::chrono::system_clock::now()),
    modified_time_(std::chrono::system_clock::now()) {
    
    if (system_message_.has_value()) {
        Message sys_msg;
        sys_msg.role = Role::System;
        sys_msg.content = *system_message_;
        messages_.push_back(sys_msg);
    }
}

Session::~Session() {
    destroy();
}

std::chrono::system_clock::time_point Session::modified_time() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return modified_time_;
}

std::vector<Message> Session::messages() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return messages_;
}

void Session::register_tool_handler(const std::string& name, ToolHandler handler) {
    std::lock_guard<std::mutex> lock(mutex_);
    tool_handlers_[name] = handler;
}

void Session::on(EventHandler handler) {
    std::lock_guard<std::mutex> lock(mutex_);
    event_handlers_.push_back(handler);
}

void Session::emit(EventType event_type, const json& data) {
    SessionEvent event;
    event.event_type = event_type;
    event.data = data;
    event.session_id = session_id_;
    
    std::vector<EventHandler> handlers;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        handlers = event_handlers_;
    }
    
    for (const auto& handler : handlers) {
        handler(event);
    }
}

void Session::send(const MessageOptions& options) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (closed_) {
            throw SessionClosedError(session_id_);
        }
    }
    
    std::string content = options.prompt;
    if (options.context.has_value()) {
        content = *options.context + "\n\n" + content;
    }
    
    Message user_message;
    user_message.role = Role::User;
    user_message.content = content;
    
    {
        std::lock_guard<std::mutex> lock(mutex_);
        messages_.push_back(user_message);
        modified_time_ = std::chrono::system_clock::now();
    }
    
    try {
        if (streaming_) {
            stream_response();
        } else {
            get_response();
        }
    } catch (const std::exception& e) {
        emit(EventType::SessionError, {{"error", e.what()}});
        throw;
    }
}

SessionEvent Session::send_and_wait(const MessageOptions& options) {
    SessionEvent result;
    bool received = false;
    std::mutex result_mutex;
    std::condition_variable cv;
    
    auto handler = [&](const SessionEvent& event) {
        if (event.event_type == EventType::AssistantMessage ||
            event.event_type == EventType::SessionIdle ||
            event.event_type == EventType::SessionError) {
            std::lock_guard<std::mutex> lock(result_mutex);
            if (!received) {
                result = event;
                received = true;
                cv.notify_one();
            }
        }
    };
    
    on(handler);
    send(options);
    
    std::unique_lock<std::mutex> lock(result_mutex);
    cv.wait(lock, [&] { return received; });
    
    return result;
}

void Session::stream_response() {
    std::string full_content;
    std::string full_reasoning;
    std::vector<ToolCall> all_tool_calls;
    std::optional<LLMUsage> final_usage;
    
    std::vector<Message> msgs;
    std::vector<Tool> current_tools;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        msgs = messages_;
        current_tools = tools_;
    }
    
    backend_->complete_streaming(
        model_,
        msgs,
        [&](const LLMChunk& chunk) {
            if (!chunk.content.empty()) {
                full_content += chunk.content;
                emit(EventType::AssistantMessageDelta, {
                    {"deltaContent", chunk.content},
                    {"content", full_content}
                });
            }
            
            if (chunk.reasoning_content.has_value()) {
                full_reasoning += *chunk.reasoning_content;
                emit(EventType::AssistantReasoningDelta, {
                    {"deltaContent", *chunk.reasoning_content},
                    {"content", full_reasoning}
                });
            }
            
            for (const auto& tc : chunk.tool_calls) {
                all_tool_calls.push_back(tc);
            }
            
            if (chunk.usage.has_value()) {
                final_usage = chunk.usage;
            }
        },
        generation_config_,
        thinking_config_,
        current_tools
    );
    
    if (!all_tool_calls.empty()) {
        handle_tool_calls(all_tool_calls);
    }
    
    Message assistant_message;
    assistant_message.role = Role::Assistant;
    assistant_message.content = full_content;
    assistant_message.tool_calls = all_tool_calls;
    
    {
        std::lock_guard<std::mutex> lock(mutex_);
        messages_.push_back(assistant_message);
    }
    
    if (!full_reasoning.empty()) {
        emit(EventType::AssistantReasoning, {{"content", full_reasoning}});
    }
    
    json msg_data = {{"content", full_content}};
    if (!all_tool_calls.empty()) {
        json tc_array = json::array();
        for (const auto& tc : all_tool_calls) {
            tc_array.push_back({
                {"id", tc.id},
                {"type", tc.type},
                {"function", {
                    {"name", tc.function.name},
                    {"arguments", tc.function.arguments}
                }}
            });
        }
        msg_data["toolCalls"] = tc_array;
    }
    if (final_usage.has_value()) {
        msg_data["usage"] = {
            {"promptTokens", final_usage->prompt_tokens},
            {"completionTokens", final_usage->completion_tokens},
            {"totalTokens", final_usage->total_tokens}
        };
    }
    
    emit(EventType::AssistantMessage, msg_data);
    emit(EventType::SessionIdle, {});
}

void Session::get_response() {
    std::vector<Message> msgs;
    std::vector<Tool> current_tools;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        msgs = messages_;
        current_tools = tools_;
    }
    
    LLMChunk chunk = backend_->complete(
        model_,
        msgs,
        generation_config_,
        thinking_config_,
        current_tools
    );
    
    if (!chunk.tool_calls.empty()) {
        handle_tool_calls(chunk.tool_calls);
    }
    
    Message assistant_message;
    assistant_message.role = Role::Assistant;
    assistant_message.content = chunk.content;
    assistant_message.tool_calls = chunk.tool_calls;
    
    {
        std::lock_guard<std::mutex> lock(mutex_);
        messages_.push_back(assistant_message);
    }
    
    if (chunk.reasoning_content.has_value()) {
        emit(EventType::AssistantReasoning, {{"content", *chunk.reasoning_content}});
    }
    
    json msg_data = {{"content", chunk.content}};
    if (!chunk.tool_calls.empty()) {
        json tc_array = json::array();
        for (const auto& tc : chunk.tool_calls) {
            tc_array.push_back({
                {"id", tc.id},
                {"type", tc.type},
                {"function", {
                    {"name", tc.function.name},
                    {"arguments", tc.function.arguments}
                }}
            });
        }
        msg_data["toolCalls"] = tc_array;
    }
    if (chunk.usage.has_value()) {
        msg_data["usage"] = {
            {"promptTokens", chunk.usage->prompt_tokens},
            {"completionTokens", chunk.usage->completion_tokens},
            {"totalTokens", chunk.usage->total_tokens}
        };
    }
    
    emit(EventType::AssistantMessage, msg_data);
    emit(EventType::SessionIdle, {});
}

void Session::handle_tool_calls(const std::vector<ToolCall>& tool_calls) {
    for (const auto& tc : tool_calls) {
        const std::string& tool_name = tc.function.name;
        
        emit(EventType::ToolCall, {
            {"name", tool_name},
            {"arguments", tc.function.arguments},
            {"callId", tc.id}
        });
        
        ToolHandler handler;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            auto it = tool_handlers_.find(tool_name);
            if (it == tool_handlers_.end()) {
                std::cerr << "Warning: No handler for tool: " << tool_name << std::endl;
                Message error_msg;
                error_msg.role = Role::User;
                error_msg.content = "Error: Tool '" + tool_name + "' not found";
                error_msg.name = tool_name;
                error_msg.tool_call_id = tc.id;
                messages_.push_back(error_msg);
                continue;
            }
            handler = it->second;
        }
        
        ToolInvocation invocation;
        invocation.name = tool_name;
        invocation.call_id = tc.id;
        
        if (tc.function.arguments.is_object()) {
            for (auto it = tc.function.arguments.begin(); it != tc.function.arguments.end(); ++it) {
                invocation.arguments[it.key()] = it.value();
            }
        }
        
        try {
            ToolResult result = handler(invocation);
            std::string result_text = result.text_result_for_llm.value_or("Success");
            
            emit(EventType::ToolResult, {
                {"name", tool_name},
                {"callId", tc.id},
                {"result", result_text}
            });
            
            Message result_msg;
            result_msg.role = Role::User;
            result_msg.content = result_text;
            result_msg.name = tool_name;
            result_msg.tool_call_id = tc.id;
            
            std::lock_guard<std::mutex> lock(mutex_);
            messages_.push_back(result_msg);
        } catch (const std::exception& e) {
            std::string error_msg_str = "Error executing tool '" + tool_name + "': " + e.what();
            std::cerr << error_msg_str << std::endl;
            
            emit(EventType::ToolResult, {
                {"name", tool_name},
                {"callId", tc.id},
                {"error", error_msg_str}
            });
            
            Message result_msg;
            result_msg.role = Role::User;
            result_msg.content = error_msg_str;
            result_msg.name = tool_name;
            result_msg.tool_call_id = tc.id;
            
            std::lock_guard<std::mutex> lock(mutex_);
            messages_.push_back(result_msg);
        }
    }
}

void Session::add_tool(const Tool& tool) {
    std::lock_guard<std::mutex> lock(mutex_);
    tools_.push_back(tool);
}

void Session::remove_tool(const std::string& tool_name) {
    std::lock_guard<std::mutex> lock(mutex_);
    tools_.erase(
        std::remove_if(tools_.begin(), tools_.end(),
            [&](const Tool& t) { return t.name == tool_name; }),
        tools_.end()
    );
    tool_handlers_.erase(tool_name);
}

void Session::clear_history() {
    std::lock_guard<std::mutex> lock(mutex_);
    messages_.clear();
    
    if (system_message_.has_value()) {
        Message sys_msg;
        sys_msg.role = Role::System;
        sys_msg.content = *system_message_;
        messages_.push_back(sys_msg);
    }
    
    modified_time_ = std::chrono::system_clock::now();
}

void Session::destroy() {
    std::lock_guard<std::mutex> lock(mutex_);
    closed_ = true;
    event_handlers_.clear();
    messages_.clear();
}

} // namespace geminisdk
