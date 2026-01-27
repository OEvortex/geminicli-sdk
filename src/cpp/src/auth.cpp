/**
 * @file auth.cpp
 * @brief OAuth authentication implementation for GeminiSDK C++
 */

#include "geminisdk/auth.hpp"
#include "geminisdk/errors.hpp"
#include <fstream>
#include <sstream>
#include <curl/curl.h>
#include <ctime>

namespace geminisdk {

static size_t write_callback(void* contents, size_t size, size_t nmemb, std::string* userp) {
    userp->append((char*)contents, size * nmemb);
    return size * nmemb;
}

static int64_t current_time_ms() {
    auto now = std::chrono::system_clock::now();
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()
    ).count();
}

OAuthManager::OAuthManager(
    const std::optional<std::string>& oauth_path,
    const std::optional<std::string>& client_id,
    const std::optional<std::string>& client_secret
) : oauth_path_(oauth_path),
    client_id_(client_id.value_or(GEMINI_OAUTH_CLIENT_ID)),
    client_secret_(client_secret.value_or(GEMINI_OAUTH_CLIENT_SECRET)) {
    curl_global_init(CURL_GLOBAL_DEFAULT);
}

OAuthManager::~OAuthManager() {
    curl_global_cleanup();
}

std::string OAuthManager::get_credential_path() const {
    return get_gemini_credential_path(oauth_path_);
}

GeminiOAuthCredentials OAuthManager::load_cached_credentials() {
    std::string key_file = get_credential_path();
    
    std::ifstream file(key_file);
    if (!file.is_open()) {
        throw CredentialsNotFoundError(key_file);
    }
    
    std::stringstream buffer;
    buffer << file.rdbuf();
    
    json j = json::parse(buffer.str());
    return GeminiOAuthCredentials::from_json(j);
}

void OAuthManager::save_credentials(const GeminiOAuthCredentials& credentials) {
    std::string key_file = get_credential_path();
    
    std::ofstream file(key_file);
    if (file.is_open()) {
        file << credentials.to_json().dump(2);
    }
}

GeminiOAuthCredentials OAuthManager::refresh_access_token(const GeminiOAuthCredentials& credentials) {
    if (credentials.refresh_token.empty()) {
        throw TokenRefreshError("No refresh token available in credentials.");
    }
    
    CURL* curl = curl_easy_init();
    if (!curl) {
        throw TokenRefreshError("Failed to initialize CURL");
    }
    
    std::string scope;
    for (size_t i = 0; i < GEMINI_OAUTH_SCOPES.size(); i++) {
        if (i > 0) scope += " ";
        scope += GEMINI_OAUTH_SCOPES[i];
    }
    
    std::string post_fields = 
        "grant_type=refresh_token"
        "&refresh_token=" + credentials.refresh_token +
        "&client_id=" + client_id_ +
        "&client_secret=" + client_secret_ +
        "&scope=" + curl_easy_escape(curl, scope.c_str(), scope.length());
    
    std::string response;
    
    curl_easy_setopt(curl, CURLOPT_URL, GEMINI_OAUTH_TOKEN_ENDPOINT);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post_fields.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/x-www-form-urlencoded");
    headers = curl_slist_append(headers, "Accept: application/json");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    
    CURLcode res = curl_easy_perform(curl);
    
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    
    if (res != CURLE_OK) {
        throw TokenRefreshError("CURL error: " + std::string(curl_easy_strerror(res)));
    }
    
    if (http_code != 200) {
        throw TokenRefreshError(
            "Token refresh failed: " + std::to_string(http_code),
            static_cast<int>(http_code),
            response
        );
    }
    
    json token_data = json::parse(response);
    
    if (token_data.contains("error")) {
        std::string error = token_data.value("error", "Unknown error");
        std::string error_desc = token_data.value("error_description", "");
        throw TokenRefreshError(error + ": " + error_desc);
    }
    
    GeminiOAuthCredentials new_credentials;
    new_credentials.access_token = token_data.value("access_token", "");
    new_credentials.refresh_token = token_data.value("refresh_token", credentials.refresh_token);
    new_credentials.token_type = token_data.value("token_type", "Bearer");
    
    int64_t expires_in = token_data.value("expires_in", 3600);
    new_credentials.expiry_date = current_time_ms() + expires_in * 1000;
    
    save_credentials(new_credentials);
    
    return new_credentials;
}

bool OAuthManager::is_token_valid(const GeminiOAuthCredentials& credentials) const {
    if (credentials.expiry_date == 0) {
        return false;
    }
    return current_time_ms() < credentials.expiry_date - TOKEN_REFRESH_BUFFER_MS;
}

void OAuthManager::invalidate_credentials() {
    std::lock_guard<std::mutex> lock(mutex_);
    credentials_.reset();
}

std::string OAuthManager::ensure_authenticated(bool force_refresh) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    if (!credentials_.has_value()) {
        credentials_ = load_cached_credentials();
    }
    
    if (force_refresh || !is_token_valid(*credentials_)) {
        credentials_ = refresh_access_token(*credentials_);
    }
    
    return credentials_->access_token;
}

GeminiOAuthCredentials OAuthManager::get_credentials() {
    ensure_authenticated(false);
    std::lock_guard<std::mutex> lock(mutex_);
    return *credentials_;
}

std::string OAuthManager::get_api_endpoint() const {
    return std::string(GEMINI_CODE_ASSIST_ENDPOINT) + "/" + GEMINI_CODE_ASSIST_API_VERSION;
}

std::string OAuthManager::get_project_id() const {
    // Check environment variable
    const char* env_project = getenv("GOOGLE_CLOUD_PROJECT");
    if (env_project) {
        return std::string(env_project);
    }
    
    // Check .env file
    std::string env_file = get_gemini_env_path(std::nullopt);
    std::ifstream file(env_file);
    if (file.is_open()) {
        std::string line;
        while (std::getline(file, line)) {
            if (line.find("GOOGLE_CLOUD_PROJECT=") == 0) {
                std::string value = line.substr(21);
                // Remove quotes
                if (!value.empty() && (value.front() == '"' || value.front() == '\'')) {
                    value = value.substr(1);
                }
                if (!value.empty() && (value.back() == '"' || value.back() == '\'')) {
                    value.pop_back();
                }
                return value;
            }
        }
    }
    
    std::lock_guard<std::mutex> lock(mutex_);
    return project_id_;
}

void OAuthManager::set_project_id(const std::string& project_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    project_id_ = project_id;
}

} // namespace geminisdk
