/**
 * @file types.hpp
 * @brief Type definitions for GeminiSDK C++
 */

#ifndef GEMINISDK_TYPES_HPP
#define GEMINISDK_TYPES_HPP

#include <string>
#include <vector>
#include <map>
#include <optional>
#include <functional>
#include <chrono>
#include <nlohmann/json.hpp>

namespace geminisdk {

using json = nlohmann::json;

// =============================================================================
// Constants
// =============================================================================

constexpr const char* GEMINI_OAUTH_REDIRECT_URI = "http://localhost:45289";
constexpr const char* GEMINI_OAUTH_BASE_URL = "https://accounts.google.com";
constexpr const char* GEMINI_OAUTH_TOKEN_ENDPOINT = "https://accounts.google.com/o/oauth2/token";
constexpr const char* GEMINI_OAUTH_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth";
constexpr const char* GEMINI_OAUTH_CLIENT_ID = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com";
constexpr const char* GEMINI_OAUTH_CLIENT_SECRET = "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";
constexpr const char* GEMINI_CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com";
constexpr const char* GEMINI_CODE_ASSIST_API_VERSION = "v1internal";
constexpr const char* GEMINI_DIR = ".gemini";
constexpr const char* GEMINI_CREDENTIAL_FILENAME = "oauth_creds.json";
constexpr const char* GEMINI_ENV_FILENAME = ".env";
constexpr int64_t TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000;

const std::vector<std::string> GEMINI_OAUTH_SCOPES = {
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
};

// =============================================================================
// Enums
// =============================================================================

enum class ConnectionState {
    Disconnected,
    Connecting,
    Connected,
    Error
};

enum class LogLevel {
    None,
    Error,
    Warning,
    Info,
    Debug,
    All
};

enum class Role {
    User,
    Assistant,
    System
};

enum class EventType {
    SessionCreated,
    SessionIdle,
    SessionError,
    AssistantMessage,
    AssistantMessageDelta,
    AssistantReasoning,
    AssistantReasoningDelta,
    ToolCall,
    ToolResult
};

enum class ToolResultType {
    Success,
    Failure,
    Rejected,
    Denied
};

// =============================================================================
// Utility Functions
// =============================================================================

std::string role_to_string(Role role);
Role string_to_role(const std::string& str);
std::string event_type_to_string(EventType type);

// =============================================================================
// OAuth Types
// =============================================================================

struct GeminiOAuthCredentials {
    std::string access_token;
    std::string refresh_token;
    std::string token_type = "Bearer";
    int64_t expiry_date = 0;
    
    static GeminiOAuthCredentials from_json(const json& j);
    json to_json() const;
};

// =============================================================================
// Model Types
// =============================================================================

struct GeminiModelInfo {
    std::string id;
    std::string name;
    int64_t context_window = 1048576;
    int64_t max_output = 32768;
    double input_price = 0.0;
    double output_price = 0.0;
    bool supports_native_tools = true;
    bool supports_thinking = true;
};

struct ModelVisionLimits {
    std::vector<std::string> supported_media_types;
    std::optional<int> max_prompt_images;
    std::optional<int64_t> max_prompt_image_size;
};

struct ModelLimits {
    std::optional<int64_t> max_prompt_tokens;
    std::optional<int64_t> max_context_window_tokens;
    std::optional<ModelVisionLimits> vision;
};

struct ModelSupports {
    bool vision = false;
    bool tools = true;
    bool thinking = true;
};

struct ModelCapabilities {
    ModelSupports supports;
    ModelLimits limits;
};

struct ModelInfo {
    std::string id;
    std::string name;
    ModelCapabilities capabilities;
};

// =============================================================================
// Content Types
// =============================================================================

struct ContentPart {
    std::optional<std::string> text;
    std::optional<std::string> image_url;
    std::optional<std::vector<uint8_t>> image_data;
    std::optional<std::string> image_mime_type;
};

struct FunctionCall {
    std::string name;
    json arguments;
};

struct ToolCall {
    std::string id;
    std::string type = "function";
    FunctionCall function;
};

struct Message {
    Role role;
    std::string content;
    std::vector<ContentPart> parts;
    std::optional<std::string> name;
    std::vector<ToolCall> tool_calls;
    std::optional<std::string> tool_call_id;
};

struct Attachment {
    std::string type;
    std::optional<std::string> path;
    std::optional<std::string> url;
    std::optional<std::string> data;
    std::optional<std::string> mime_type;
};

// =============================================================================
// Tool Types
// =============================================================================

struct ToolInvocation {
    std::string name;
    std::map<std::string, json> arguments;
    std::string call_id;
};

struct ToolResult {
    std::optional<ToolResultType> result_type = ToolResultType::Success;
    std::optional<std::string> text_result_for_llm;
    std::optional<std::vector<uint8_t>> binary_result;
    std::optional<std::string> session_log;
};

struct Tool {
    std::string name;
    std::string description;
    std::optional<json> parameters;
};

// =============================================================================
// Configuration Types
// =============================================================================

struct GenerationConfig {
    double temperature = 0.7;
    std::optional<int> max_output_tokens;
    std::optional<double> top_p;
    std::optional<int> top_k;
    std::optional<std::vector<std::string>> stop_sequences;
};

struct ThinkingConfig {
    bool include_thoughts = true;
    std::optional<int> thinking_budget;
};

struct MessageOptions {
    std::string prompt;
    std::vector<Attachment> attachments;
    std::optional<std::string> context;
};

// =============================================================================
// Response Types
// =============================================================================

struct LLMUsage {
    int64_t prompt_tokens = 0;
    int64_t completion_tokens = 0;
    int64_t total_tokens = 0;
};

struct LLMChunk {
    std::string content;
    std::optional<std::string> reasoning_content;
    std::vector<ToolCall> tool_calls;
    std::optional<LLMUsage> usage;
    std::optional<std::string> finish_reason;
};

// =============================================================================
// Session Types
// =============================================================================

struct SessionConfig {
    std::optional<std::string> session_id;
    std::optional<std::string> model;
    std::vector<Tool> tools;
    std::optional<std::string> system_message;
    std::optional<GenerationConfig> generation_config;
    std::optional<ThinkingConfig> thinking_config;
    bool streaming = true;
};

struct SessionMetadata {
    std::string session_id;
    std::string start_time;
    std::string modified_time;
    std::optional<std::string> summary;
    std::string model;
};

struct SessionEvent {
    EventType event_type;
    json data;
    std::string session_id;
};

// =============================================================================
// Client Types
// =============================================================================

struct ClientOptions {
    std::optional<std::string> oauth_path;
    std::optional<std::string> client_id;
    std::optional<std::string> client_secret;
    std::optional<std::string> base_url;
    std::optional<double> timeout;
    LogLevel log_level = LogLevel::None;
    bool auto_refresh = true;
};

// =============================================================================
// Callback Types
// =============================================================================

using ToolHandler = std::function<ToolResult(const ToolInvocation&)>;
using EventHandler = std::function<void(const SessionEvent&)>;
using StreamCallback = std::function<void(const LLMChunk&)>;

// =============================================================================
// Utility Functions
// =============================================================================

std::string get_gemini_credential_path(const std::optional<std::string>& custom_path = std::nullopt);
std::string get_gemini_env_path(const std::optional<std::string>& custom_path = std::nullopt);
std::map<std::string, GeminiModelInfo> get_gemini_cli_models();
std::string generate_uuid();
std::string get_current_timestamp();

} // namespace geminisdk

#endif // GEMINISDK_TYPES_HPP
