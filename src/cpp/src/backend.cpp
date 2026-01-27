/**
 * @file backend.cpp
 * @brief Backend implementation for GeminiSDK C++
 */

#include "geminisdk/backend.hpp"
#include "geminisdk/errors.hpp"
#include <curl/curl.h>
#include <sstream>
#include <thread>
#include <chrono>

namespace geminisdk {

static constexpr int ONBOARD_MAX_RETRIES = 30;
static constexpr int ONBOARD_SLEEP_SECONDS = 2;

static size_t write_callback(void* contents, size_t size, size_t nmemb, std::string* userp) {
    userp->append((char*)contents, size * nmemb);
    return size * nmemb;
}

static std::string base64_encode(const std::vector<uint8_t>& data) {
    static const char* alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string result;
    
    size_t i = 0;
    while (i < data.size()) {
        uint32_t octet_a = i < data.size() ? data[i++] : 0;
        uint32_t octet_b = i < data.size() ? data[i++] : 0;
        uint32_t octet_c = i < data.size() ? data[i++] : 0;
        
        uint32_t triple = (octet_a << 16) + (octet_b << 8) + octet_c;
        
        result += alphabet[(triple >> 18) & 0x3F];
        result += alphabet[(triple >> 12) & 0x3F];
        result += alphabet[(triple >> 6) & 0x3F];
        result += alphabet[triple & 0x3F];
    }
    
    // Padding
    size_t mod = data.size() % 3;
    if (mod > 0) {
        for (size_t j = 0; j < 3 - mod; j++) {
            result[result.length() - 1 - j] = '=';
        }
    }
    
    return result;
}

Backend::Backend(const BackendOptions& options)
    : timeout_(options.timeout.value_or(720.0)),
      oauth_manager_(options.oauth_path, options.client_id, options.client_secret) {
}

Backend::~Backend() = default;

std::map<std::string, std::string> Backend::get_auth_headers(bool force_refresh) {
    std::string access_token = oauth_manager_.ensure_authenticated(force_refresh);
    return {
        {"Content-Type", "application/json"},
        {"Authorization", "Bearer " + access_token}
    };
}

json Backend::prepare_messages(const std::vector<Message>& messages) {
    json result = json::array();
    
    for (const auto& msg : messages) {
        std::string role = msg.role == Role::Assistant ? "model" : "user";
        json content_parts = json::array();
        
        if (!msg.content.empty()) {
            content_parts.push_back({{"text", msg.content}});
        }
        
        for (const auto& part : msg.parts) {
            if (part.text.has_value()) {
                content_parts.push_back({{"text", *part.text}});
            }
            if (part.image_data.has_value() && part.image_mime_type.has_value()) {
                std::string b64_data = base64_encode(*part.image_data);
                content_parts.push_back({
                    {"inlineData", {
                        {"mimeType", *part.image_mime_type},
                        {"data", b64_data}
                    }}
                });
            }
        }
        
        for (const auto& tc : msg.tool_calls) {
            content_parts.push_back({
                {"functionCall", {
                    {"name", tc.function.name},
                    {"args", tc.function.arguments}
                }}
            });
        }
        
        if (msg.tool_call_id.has_value()) {
            content_parts.push_back({
                {"functionResponse", {
                    {"name", msg.name.value_or("")},
                    {"response", {{"result", msg.content}}}
                }}
            });
        }
        
        if (!content_parts.empty()) {
            result.push_back({
                {"role", role},
                {"parts", content_parts}
            });
        }
    }
    
    return result;
}

json Backend::prepare_tools(const std::vector<Tool>& tools) {
    if (tools.empty()) {
        return json();
    }
    
    json func_decls = json::array();
    for (const auto& tool : tools) {
        json func_def = {
            {"name", tool.name},
            {"description", tool.description}
        };
        
        if (tool.parameters.has_value()) {
            func_def["parameters"] = {
                {"type", "object"},
                {"properties", tool.parameters->value("properties", json::object())},
                {"required", tool.parameters->value("required", json::array())}
            };
        }
        
        func_decls.push_back(func_def);
    }
    
    return json::array({{{"functionDeclarations", func_decls}}});
}

std::string Backend::ensure_project_id(const std::string& access_token) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!project_id_.empty()) {
            return project_id_;
        }
    }
    
    std::string env_project_id = oauth_manager_.get_project_id();
    
    json client_metadata = {
        {"ideType", "IDE_UNSPECIFIED"},
        {"platform", "PLATFORM_UNSPECIFIED"},
        {"pluginType", "GEMINI"},
        {"duetProject", env_project_id.empty() ? json(nullptr) : json(env_project_id)}
    };
    
    json load_request = {
        {"cloudaicompanionProject", env_project_id.empty() ? json(nullptr) : json(env_project_id)},
        {"metadata", client_metadata}
    };
    
    std::string url = oauth_manager_.get_api_endpoint() + ":loadCodeAssist";
    
    CURL* curl = curl_easy_init();
    if (!curl) {
        throw ConnectionError("Failed to initialize CURL");
    }
    
    std::string request_body = load_request.dump();
    std::string response;
    
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, request_body.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, ("Authorization: Bearer " + access_token).c_str());
    headers = curl_slist_append(headers, "Content-Type: application/json");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    
    CURLcode res = curl_easy_perform(curl);
    
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    
    if (res != CURLE_OK || http_code != 200) {
        throw APIError("Gemini Code Assist access denied: " + response, http_code);
    }
    
    json data = json::parse(response);
    
    if (data.contains("currentTier")) {
        std::string pid = data.value("cloudaicompanionProject", env_project_id);
        std::lock_guard<std::mutex> lock(mutex_);
        project_id_ = pid;
        return pid;
    }
    
    // Need to onboard
    std::string tier_id = "free-tier";
    if (data.contains("allowedTiers") && data["allowedTiers"].is_array()) {
        for (const auto& tier : data["allowedTiers"]) {
            if (tier.value("isDefault", false)) {
                tier_id = tier.value("id", "free-tier");
                break;
            }
        }
    }
    
    return onboard_for_project(access_token, env_project_id, tier_id);
}

std::string Backend::onboard_for_project(
    const std::string& access_token,
    const std::string& env_project_id,
    const std::string& tier_id
) {
    json client_metadata = {
        {"ideType", "IDE_UNSPECIFIED"},
        {"platform", "PLATFORM_UNSPECIFIED"},
        {"pluginType", "GEMINI"},
        {"duetProject", env_project_id.empty() ? json(nullptr) : json(env_project_id)}
    };
    
    json onboard_request;
    if (tier_id == "free-tier") {
        onboard_request = {
            {"tierId", tier_id},
            {"cloudaicompanionProject", nullptr},
            {"metadata", client_metadata}
        };
    } else {
        onboard_request = {
            {"tierId", tier_id},
            {"cloudaicompanionProject", env_project_id},
            {"metadata", client_metadata}
        };
    }
    
    std::string url = oauth_manager_.get_api_endpoint() + ":onboardUser";
    
    for (int i = 0; i < ONBOARD_MAX_RETRIES; i++) {
        CURL* curl = curl_easy_init();
        if (!curl) continue;
        
        std::string request_body = onboard_request.dump();
        std::string response;
        
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, request_body.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
        
        struct curl_slist* headers = nullptr;
        headers = curl_slist_append(headers, ("Authorization: Bearer " + access_token).c_str());
        headers = curl_slist_append(headers, "Content-Type: application/json");
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
        
        CURLcode res = curl_easy_perform(curl);
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);
        
        if (res != CURLE_OK || http_code != 200) {
            throw OnboardingError("Onboard request failed", tier_id);
        }
        
        json lro_data = json::parse(response);
        
        if (lro_data.value("done", false)) {
            if (lro_data.contains("response") && 
                lro_data["response"].contains("cloudaicompanionProject")) {
                std::string pid = lro_data["response"]["cloudaicompanionProject"].value("id", "");
                std::lock_guard<std::mutex> lock(mutex_);
                project_id_ = pid;
                return pid;
            }
            break;
        }
        
        std::this_thread::sleep_for(std::chrono::seconds(ONBOARD_SLEEP_SECONDS));
    }
    
    if (tier_id == "free-tier") {
        std::lock_guard<std::mutex> lock(mutex_);
        project_id_ = "";
        return "";
    }
    
    throw OnboardingError("Failed to complete onboarding", tier_id);
}

json Backend::build_request_payload(
    const std::string& model,
    const std::vector<Message>& messages,
    const std::optional<GenerationConfig>& generation_config,
    const std::optional<ThinkingConfig>& thinking_config,
    const std::vector<Tool>& tools,
    const std::string& project_id
) {
    json gen_config = {{"temperature", 0.7}};
    
    if (generation_config.has_value()) {
        gen_config["temperature"] = generation_config->temperature;
        if (generation_config->max_output_tokens.has_value()) {
            gen_config["maxOutputTokens"] = *generation_config->max_output_tokens;
        }
        if (generation_config->top_p.has_value()) {
            gen_config["topP"] = *generation_config->top_p;
        }
        if (generation_config->top_k.has_value()) {
            gen_config["topK"] = *generation_config->top_k;
        }
        if (generation_config->stop_sequences.has_value()) {
            gen_config["stopSequences"] = *generation_config->stop_sequences;
        }
    }
    
    if (thinking_config.has_value() && thinking_config->include_thoughts) {
        json thinking_cfg = {{"includeThoughts", true}};
        if (thinking_config->thinking_budget.has_value()) {
            thinking_cfg["thinkingBudget"] = *thinking_config->thinking_budget;
        }
        gen_config["thinkingConfig"] = thinking_cfg;
    }
    
    json request_body = {
        {"contents", prepare_messages(messages)},
        {"generationConfig", gen_config}
    };
    
    json prepared_tools = prepare_tools(tools);
    if (!prepared_tools.is_null() && !prepared_tools.empty()) {
        request_body["tools"] = prepared_tools;
    }
    
    json payload = {
        {"model", model},
        {"request", request_body}
    };
    
    if (!project_id.empty()) {
        payload["project"] = project_id;
    }
    
    return payload;
}

LLMChunk Backend::parse_completion_response(const json& data) {
    LLMChunk chunk;
    
    const json& response_data = data.contains("response") ? data["response"] : data;
    
    if (!response_data.contains("candidates") || response_data["candidates"].empty()) {
        return chunk;
    }
    
    const json& candidate = response_data["candidates"][0];
    const json& content = candidate.value("content", json::object());
    const json& parts = content.value("parts", json::array());
    
    for (const auto& part : parts) {
        if (part.contains("text")) {
            chunk.content += part["text"].get<std::string>();
        }
        if (part.contains("thought")) {
            chunk.reasoning_content = part["thought"].get<std::string>();
        }
        if (part.contains("functionCall")) {
            ToolCall tc;
            tc.id = generate_uuid();
            tc.type = "function";
            tc.function.name = part["functionCall"].value("name", "");
            tc.function.arguments = part["functionCall"].value("args", 
                part["functionCall"].value("arguments", json::object()));
            chunk.tool_calls.push_back(tc);
        }
    }
    
    const json* usage_data = nullptr;
    if (data.contains("usageMetadata")) {
        usage_data = &data["usageMetadata"];
    } else if (response_data.contains("usageMetadata")) {
        usage_data = &response_data["usageMetadata"];
    }
    
    if (usage_data) {
        LLMUsage usage;
        usage.prompt_tokens = usage_data->value("promptTokenCount", int64_t(0));
        usage.completion_tokens = usage_data->value("candidatesTokenCount", int64_t(0));
        usage.total_tokens = usage_data->value("totalTokenCount", int64_t(0));
        chunk.usage = usage;
    }
    
    if (candidate.contains("finishReason")) {
        chunk.finish_reason = candidate["finishReason"].get<std::string>();
    }
    
    return chunk;
}

void Backend::handle_http_error(int status_code, const std::string& body) {
    std::string error_msg = body;
    
    try {
        json data = json::parse(body);
        if (data.contains("error") && data["error"].contains("message")) {
            error_msg = data["error"]["message"].get<std::string>();
        }
    } catch (...) {}
    
    switch (status_code) {
        case 429:
            throw RateLimitError("Rate limit exceeded: " + error_msg);
        case 403:
            throw PermissionDeniedError("Permission denied: " + error_msg);
        default:
            throw APIError("API error: " + error_msg, status_code);
    }
}

LLMChunk Backend::complete(
    const std::string& model,
    const std::vector<Message>& messages,
    const std::optional<GenerationConfig>& generation_config,
    const std::optional<ThinkingConfig>& thinking_config,
    const std::vector<Tool>& tools
) {
    return complete_with_retry(model, messages, generation_config, thinking_config, tools, 0);
}

LLMChunk Backend::complete_with_retry(
    const std::string& model,
    const std::vector<Message>& messages,
    const std::optional<GenerationConfig>& generation_config,
    const std::optional<ThinkingConfig>& thinking_config,
    const std::vector<Tool>& tools,
    int retry_count
) {
    auto headers = get_auth_headers(retry_count > 0);
    std::string access_token = headers["Authorization"].substr(7); // Remove "Bearer "
    std::string project_id = ensure_project_id(access_token);
    
    std::string url = oauth_manager_.get_api_endpoint() + ":generateContent";
    json payload = build_request_payload(model, messages, generation_config, thinking_config, tools, project_id);
    
    CURL* curl = curl_easy_init();
    if (!curl) {
        throw ConnectionError("Failed to initialize CURL");
    }
    
    std::string request_body = payload.dump();
    std::string response;
    
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, request_body.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, static_cast<long>(timeout_));
    
    struct curl_slist* header_list = nullptr;
    for (const auto& [key, value] : headers) {
        header_list = curl_slist_append(header_list, (key + ": " + value).c_str());
    }
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, header_list);
    
    CURLcode res = curl_easy_perform(curl);
    
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    curl_slist_free_all(header_list);
    curl_easy_cleanup(curl);
    
    if ((http_code == 401 || http_code == 403) && retry_count == 0) {
        oauth_manager_.invalidate_credentials();
        return complete_with_retry(model, messages, generation_config, thinking_config, tools, 1);
    }
    
    if (res != CURLE_OK) {
        throw ConnectionError("CURL error: " + std::string(curl_easy_strerror(res)));
    }
    
    if (http_code != 200) {
        handle_http_error(http_code, response);
    }
    
    json data = json::parse(response);
    return parse_completion_response(data);
}

void Backend::complete_streaming(
    const std::string& model,
    const std::vector<Message>& messages,
    const StreamCallback& callback,
    const std::optional<GenerationConfig>& generation_config,
    const std::optional<ThinkingConfig>& thinking_config,
    const std::vector<Tool>& tools
) {
    complete_streaming_with_retry(model, messages, callback, generation_config, thinking_config, tools, 0);
}

void Backend::complete_streaming_with_retry(
    const std::string& model,
    const std::vector<Message>& messages,
    const StreamCallback& callback,
    const std::optional<GenerationConfig>& generation_config,
    const std::optional<ThinkingConfig>& thinking_config,
    const std::vector<Tool>& tools,
    int retry_count
) {
    auto headers = get_auth_headers(retry_count > 0);
    std::string access_token = headers["Authorization"].substr(7);
    std::string project_id = ensure_project_id(access_token);
    
    std::string url = oauth_manager_.get_api_endpoint() + ":streamGenerateContent?alt=sse";
    json payload = build_request_payload(model, messages, generation_config, thinking_config, tools, project_id);
    
    CURL* curl = curl_easy_init();
    if (!curl) {
        throw ConnectionError("Failed to initialize CURL");
    }
    
    std::string request_body = payload.dump();
    std::string buffer;
    
    // Write callback that processes SSE
    auto stream_write = [](void* contents, size_t size, size_t nmemb, void* userp) -> size_t {
        auto* ctx = static_cast<std::pair<std::string*, const StreamCallback*>*>(userp);
        std::string* buf = ctx->first;
        const StreamCallback* cb = ctx->second;
        
        buf->append((char*)contents, size * nmemb);
        
        // Process complete lines
        size_t pos;
        while ((pos = buf->find('\n')) != std::string::npos) {
            std::string line = buf->substr(0, pos);
            *buf = buf->substr(pos + 1);
            
            // Trim
            while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) {
                line.pop_back();
            }
            
            if (line.empty() || line[0] == ':') continue;
            
            if (line.find("data:") == 0) {
                std::string data = line.substr(5);
                // Trim leading whitespace
                size_t start = data.find_first_not_of(" \t");
                if (start != std::string::npos) {
                    data = data.substr(start);
                }
                
                if (data == "[DONE]") continue;
                
                try {
                    json parsed = json::parse(data);
                    
                    // Parse chunk manually here
                    LLMChunk chunk;
                    const json& response_data = parsed.contains("response") ? parsed["response"] : parsed;
                    
                    if (response_data.contains("candidates") && !response_data["candidates"].empty()) {
                        const json& candidate = response_data["candidates"][0];
                        const json& content = candidate.value("content", json::object());
                        const json& parts = content.value("parts", json::array());
                        
                        for (const auto& part : parts) {
                            if (part.contains("text")) {
                                chunk.content += part["text"].get<std::string>();
                            }
                            if (part.contains("thought")) {
                                chunk.reasoning_content = part["thought"].get<std::string>();
                            }
                            if (part.contains("functionCall")) {
                                ToolCall tc;
                                tc.id = generate_uuid();
                                tc.type = "function";
                                tc.function.name = part["functionCall"].value("name", "");
                                tc.function.arguments = part["functionCall"].value("args",
                                    part["functionCall"].value("arguments", json::object()));
                                chunk.tool_calls.push_back(tc);
                            }
                        }
                    }
                    
                    (*cb)(chunk);
                } catch (...) {}
            }
        }
        
        return size * nmemb;
    };
    
    std::pair<std::string*, const StreamCallback*> ctx(&buffer, &callback);
    
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, request_body.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, 
        static_cast<size_t(*)(void*, size_t, size_t, void*)>(stream_write));
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &ctx);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, static_cast<long>(timeout_));
    
    struct curl_slist* header_list = nullptr;
    for (const auto& [key, value] : headers) {
        header_list = curl_slist_append(header_list, (key + ": " + value).c_str());
    }
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, header_list);
    
    CURLcode res = curl_easy_perform(curl);
    
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    curl_slist_free_all(header_list);
    curl_easy_cleanup(curl);
    
    if ((http_code == 401 || http_code == 403) && retry_count == 0) {
        oauth_manager_.invalidate_credentials();
        complete_streaming_with_retry(model, messages, callback, generation_config, thinking_config, tools, 1);
        return;
    }
    
    if (res != CURLE_OK) {
        throw ConnectionError("CURL error: " + std::string(curl_easy_strerror(res)));
    }
    
    if (http_code != 200) {
        handle_http_error(http_code, buffer);
    }
}

std::vector<std::string> Backend::list_models() const {
    std::vector<std::string> names;
    for (const auto& [name, _] : get_gemini_cli_models()) {
        names.push_back(name);
    }
    return names;
}

} // namespace geminisdk
