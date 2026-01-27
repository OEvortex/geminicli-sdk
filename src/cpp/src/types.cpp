/**
 * @file types.cpp
 * @brief Type implementations for GeminiSDK C++
 */

#include "geminisdk/types.hpp"
#include <random>
#include <sstream>
#include <iomanip>
#include <ctime>

#ifdef _WIN32
#include <windows.h>
#include <shlobj.h>
#else
#include <pwd.h>
#include <unistd.h>
#endif

namespace geminisdk {

std::string role_to_string(Role role) {
    switch (role) {
        case Role::User: return "user";
        case Role::Assistant: return "assistant";
        case Role::System: return "system";
        default: return "user";
    }
}

Role string_to_role(const std::string& str) {
    if (str == "assistant" || str == "model") return Role::Assistant;
    if (str == "system") return Role::System;
    return Role::User;
}

std::string event_type_to_string(EventType type) {
    switch (type) {
        case EventType::SessionCreated: return "session.created";
        case EventType::SessionIdle: return "session.idle";
        case EventType::SessionError: return "session.error";
        case EventType::AssistantMessage: return "assistant.message";
        case EventType::AssistantMessageDelta: return "assistant.message_delta";
        case EventType::AssistantReasoning: return "assistant.reasoning";
        case EventType::AssistantReasoningDelta: return "assistant.reasoning_delta";
        case EventType::ToolCall: return "tool.call";
        case EventType::ToolResult: return "tool.result";
        default: return "unknown";
    }
}

GeminiOAuthCredentials GeminiOAuthCredentials::from_json(const json& j) {
    GeminiOAuthCredentials creds;
    creds.access_token = j.value("access_token", "");
    creds.refresh_token = j.value("refresh_token", "");
    creds.token_type = j.value("token_type", "Bearer");
    creds.expiry_date = j.value("expiry_date", int64_t(0));
    return creds;
}

json GeminiOAuthCredentials::to_json() const {
    return {
        {"access_token", access_token},
        {"refresh_token", refresh_token},
        {"token_type", token_type},
        {"expiry_date", expiry_date}
    };
}

static std::string get_home_directory() {
#ifdef _WIN32
    char path[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathA(NULL, CSIDL_PROFILE, NULL, 0, path))) {
        return std::string(path);
    }
    const char* userprofile = getenv("USERPROFILE");
    if (userprofile) return std::string(userprofile);
    return "";
#else
    const char* home = getenv("HOME");
    if (home) return std::string(home);
    
    struct passwd* pw = getpwuid(getuid());
    if (pw) return std::string(pw->pw_dir);
    return "";
#endif
}

std::string get_gemini_credential_path(const std::optional<std::string>& custom_path) {
    if (custom_path.has_value()) {
        return *custom_path;
    }
    
    std::string home = get_home_directory();
    if (home.empty()) return "";
    
#ifdef _WIN32
    return home + "\\" + GEMINI_DIR + "\\" + GEMINI_CREDENTIAL_FILENAME;
#else
    return home + "/" + GEMINI_DIR + "/" + GEMINI_CREDENTIAL_FILENAME;
#endif
}

std::string get_gemini_env_path(const std::optional<std::string>& custom_path) {
    if (custom_path.has_value()) {
        return *custom_path;
    }
    
    std::string home = get_home_directory();
    if (home.empty()) return "";
    
#ifdef _WIN32
    return home + "\\" + GEMINI_DIR + "\\" + GEMINI_ENV_FILENAME;
#else
    return home + "/" + GEMINI_DIR + "/" + GEMINI_ENV_FILENAME;
#endif
}

std::map<std::string, GeminiModelInfo> get_gemini_cli_models() {
    return {
        {"gemini-3-pro-preview", {
            "gemini-3-pro-preview",
            "Gemini 3 Pro Preview",
            1000000, 65536, 0.0, 0.0, true, true
        }},
        {"gemini-3-flash-preview", {
            "gemini-3-flash-preview",
            "Gemini 3 Flash Preview",
            1000000, 65536, 0.0, 0.0, true, true
        }},
        {"gemini-2.5-pro", {
            "gemini-2.5-pro",
            "Gemini 2.5 Pro",
            1048576, 65536, 0.0, 0.0, true, true
        }},
        {"gemini-2.5-flash", {
            "gemini-2.5-flash",
            "Gemini 2.5 Flash",
            1048576, 65536, 0.0, 0.0, true, true
        }},
        {"gemini-2.5-flash-lite", {
            "gemini-2.5-flash-lite",
            "Gemini 2.5 Flash Lite",
            1000000, 32768, 0.0, 0.0, true, false
        }},
        {"auto", {
            "auto",
            "Auto (Default)",
            1048576, 65536, 0.0, 0.0, true, true
        }}
    };
}

std::string generate_uuid() {
    static std::random_device rd;
    static std::mt19937 gen(rd());
    static std::uniform_int_distribution<> dis(0, 15);
    static std::uniform_int_distribution<> dis2(8, 11);
    
    std::stringstream ss;
    ss << std::hex;
    
    for (int i = 0; i < 8; i++) ss << dis(gen);
    ss << "-";
    for (int i = 0; i < 4; i++) ss << dis(gen);
    ss << "-4";
    for (int i = 0; i < 3; i++) ss << dis(gen);
    ss << "-";
    ss << dis2(gen);
    for (int i = 0; i < 3; i++) ss << dis(gen);
    ss << "-";
    for (int i = 0; i < 12; i++) ss << dis(gen);
    
    return ss.str();
}

std::string get_current_timestamp() {
    auto now = std::chrono::system_clock::now();
    auto time_t_now = std::chrono::system_clock::to_time_t(now);
    
    std::stringstream ss;
    ss << std::put_time(std::gmtime(&time_t_now), "%Y-%m-%dT%H:%M:%SZ");
    return ss.str();
}

} // namespace geminisdk
