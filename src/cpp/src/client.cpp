/**
 * @file client.cpp
 * @brief Client implementation for GeminiSDK C++
 */

#include "geminisdk/client.hpp"
#include "geminisdk/errors.hpp"
#include <thread>
#include <chrono>

namespace geminisdk {

Client::Client(const ClientOptions& options)
    : options_(options),
      state_(ConnectionState::Disconnected),
      started_(false) {
}

Client::~Client() {
    stop();
}

ConnectionState Client::state() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return state_;
}

void Client::start() {
    std::lock_guard<std::mutex> lock(mutex_);
    
    if (started_) {
        return;
    }
    
    state_ = ConnectionState::Connecting;
    
    try {
        oauth_manager_ = std::make_unique<OAuthManager>(
            options_.oauth_path,
            options_.client_id,
            options_.client_secret
        );
        
        BackendOptions backend_opts;
        backend_opts.timeout = options_.timeout;
        backend_opts.oauth_path = options_.oauth_path;
        backend_opts.client_id = options_.client_id;
        backend_opts.client_secret = options_.client_secret;
        
        backend_ = std::make_shared<Backend>(backend_opts);
        
        // Verify authentication
        oauth_manager_->ensure_authenticated(false);
        
        state_ = ConnectionState::Connected;
        started_ = true;
        
        if (options_.auto_refresh) {
            start_auto_refresh();
        }
    } catch (const std::exception& e) {
        state_ = ConnectionState::Error;
        throw;
    }
}

void Client::start_auto_refresh() {
    // Simple background refresh - in production you'd want proper thread management
    std::thread([this]() {
        while (true) {
            std::this_thread::sleep_for(std::chrono::seconds(30));
            
            std::lock_guard<std::mutex> lock(mutex_);
            if (!started_ || !oauth_manager_) {
                break;
            }
            
            try {
                oauth_manager_->ensure_authenticated(false);
            } catch (...) {
                // Ignore refresh errors
            }
        }
    }).detach();
}

void Client::stop() {
    std::lock_guard<std::mutex> lock(mutex_);
    
    // Destroy all sessions
    for (auto& [id, session] : sessions_) {
        session->destroy();
    }
    sessions_.clear();
    
    backend_.reset();
    oauth_manager_.reset();
    state_ = ConnectionState::Disconnected;
    started_ = false;
}

void Client::close() {
    stop();
}

std::shared_ptr<Session> Client::create_session(const SessionConfig& config) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!started_) {
            // Unlock before calling start()
        }
    }
    
    if (!started_) {
        start();
    }
    
    std::lock_guard<std::mutex> lock(mutex_);
    
    if (!backend_) {
        throw ConfigurationError("Client not connected");
    }
    
    std::string session_id = config.session_id.value_or(generate_uuid());
    std::string model = config.model.value_or("gemini-2.5-pro");
    
    auto session = std::make_shared<Session>(
        session_id,
        model,
        backend_,
        config.tools,
        config.system_message,
        config.generation_config,
        config.thinking_config,
        config.streaming
    );
    
    sessions_[session_id] = session;
    
    return session;
}

std::shared_ptr<Session> Client::get_session(const std::string& session_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    auto it = sessions_.find(session_id);
    if (it == sessions_.end()) {
        throw SessionNotFoundError(session_id);
    }
    
    return it->second;
}

std::vector<SessionMetadata> Client::list_sessions() const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    std::vector<SessionMetadata> result;
    for (const auto& [id, session] : sessions_) {
        SessionMetadata meta;
        meta.session_id = session->session_id();
        meta.model = session->model();
        
        auto start = session->start_time();
        auto modified = session->modified_time();
        
        auto to_iso = [](std::chrono::system_clock::time_point tp) {
            auto time_t_val = std::chrono::system_clock::to_time_t(tp);
            std::stringstream ss;
            ss << std::put_time(std::gmtime(&time_t_val), "%Y-%m-%dT%H:%M:%SZ");
            return ss.str();
        };
        
        meta.start_time = to_iso(start);
        meta.modified_time = to_iso(modified);
        
        result.push_back(meta);
    }
    
    return result;
}

void Client::delete_session(const std::string& session_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    auto it = sessions_.find(session_id);
    if (it != sessions_.end()) {
        it->second->destroy();
        sessions_.erase(it);
    }
}

std::map<std::string, json> Client::get_auth_status() const {
    std::map<std::string, json> status;
    
    std::lock_guard<std::mutex> lock(mutex_);
    
    if (oauth_manager_) {
        try {
            auto creds = oauth_manager_->get_credentials();
            status["authenticated"] = true;
            status["token_type"] = creds.token_type;
            status["expires_at"] = creds.expiry_date;
            return status;
        } catch (...) {}
    }
    
    status["authenticated"] = false;
    return status;
}

std::vector<ModelInfo> Client::list_models() const {
    auto models = get_gemini_cli_models();
    std::vector<ModelInfo> result;
    
    for (const auto& [id, info] : models) {
        ModelInfo model;
        model.id = id;
        model.name = info.name;
        model.capabilities.supports.vision = false;
        model.capabilities.supports.tools = info.supports_native_tools;
        model.capabilities.supports.thinking = info.supports_thinking;
        model.capabilities.limits.max_prompt_tokens = info.context_window;
        model.capabilities.limits.max_context_window_tokens = info.context_window;
        result.push_back(model);
    }
    
    return result;
}

void Client::refresh_auth() {
    std::lock_guard<std::mutex> lock(mutex_);
    
    if (oauth_manager_) {
        oauth_manager_->ensure_authenticated(true);
    }
}

} // namespace geminisdk
