/**
 * @file errors.hpp
 * @brief Exception types for GeminiSDK C++
 */

#ifndef GEMINISDK_ERRORS_HPP
#define GEMINISDK_ERRORS_HPP

#include <stdexcept>
#include <string>
#include <optional>
#include <map>

namespace geminisdk {

/**
 * Base exception class for GeminiSDK errors
 */
class GeminiSDKError : public std::runtime_error {
public:
    explicit GeminiSDKError(const std::string& message, const std::string& code = "")
        : std::runtime_error(message), code_(code) {}
    
    const std::string& code() const { return code_; }
    
protected:
    std::string code_;
};

/**
 * Authentication-related errors
 */
class AuthenticationError : public GeminiSDKError {
public:
    explicit AuthenticationError(const std::string& message)
        : GeminiSDKError(message, "AUTHENTICATION_ERROR") {}
};

/**
 * Credentials file not found
 */
class CredentialsNotFoundError : public AuthenticationError {
public:
    explicit CredentialsNotFoundError(const std::string& credential_path)
        : AuthenticationError("Credentials not found at " + credential_path),
          credential_path_(credential_path) {}
    
    const std::string& credential_path() const { return credential_path_; }
    
private:
    std::string credential_path_;
};

/**
 * Token refresh failure
 */
class TokenRefreshError : public AuthenticationError {
public:
    TokenRefreshError(
        const std::string& message,
        std::optional<int> status_code = std::nullopt,
        const std::string& response_body = ""
    ) : AuthenticationError(message),
        status_code_(status_code),
        response_body_(response_body) {}
    
    std::optional<int> status_code() const { return status_code_; }
    const std::string& response_body() const { return response_body_; }
    
private:
    std::optional<int> status_code_;
    std::string response_body_;
};

/**
 * Token has expired
 */
class TokenExpiredError : public AuthenticationError {
public:
    TokenExpiredError() : AuthenticationError("Token has expired") {}
};

/**
 * Connection errors
 */
class ConnectionError : public GeminiSDKError {
public:
    explicit ConnectionError(const std::string& message, const std::string& endpoint = "")
        : GeminiSDKError(message, "CONNECTION_ERROR"), endpoint_(endpoint) {}
    
    const std::string& endpoint() const { return endpoint_; }
    
private:
    std::string endpoint_;
};

/**
 * API errors
 */
class APIError : public GeminiSDKError {
public:
    APIError(
        const std::string& message,
        int status_code,
        const std::string& response_body = "",
        const std::string& endpoint = ""
    ) : GeminiSDKError(message, "API_ERROR"),
        status_code_(status_code),
        response_body_(response_body),
        endpoint_(endpoint) {}
    
    int status_code() const { return status_code_; }
    const std::string& response_body() const { return response_body_; }
    const std::string& endpoint() const { return endpoint_; }
    
protected:
    int status_code_;
    std::string response_body_;
    std::string endpoint_;
};

/**
 * Rate limit exceeded
 */
class RateLimitError : public APIError {
public:
    RateLimitError(
        const std::string& message,
        std::optional<int> retry_after = std::nullopt
    ) : APIError(message, 429), retry_after_(retry_after) {}
    
    std::optional<int> retry_after() const { return retry_after_; }
    
private:
    std::optional<int> retry_after_;
};

/**
 * Quota exceeded
 */
class QuotaExceededError : public APIError {
public:
    QuotaExceededError(const std::string& message, const std::string& reset_time = "")
        : APIError(message, 429), reset_time_(reset_time) {}
    
    const std::string& reset_time() const { return reset_time_; }
    
private:
    std::string reset_time_;
};

/**
 * Permission denied
 */
class PermissionDeniedError : public APIError {
public:
    explicit PermissionDeniedError(const std::string& message)
        : APIError(message, 403) {}
};

/**
 * Resource not found
 */
class NotFoundError : public APIError {
public:
    NotFoundError(const std::string& message, const std::string& resource = "")
        : APIError(message, 404), resource_(resource) {}
    
    const std::string& resource() const { return resource_; }
    
private:
    std::string resource_;
};

/**
 * Session errors
 */
class SessionError : public GeminiSDKError {
public:
    SessionError(const std::string& message, const std::string& session_id = "")
        : GeminiSDKError(message, "SESSION_ERROR"), session_id_(session_id) {}
    
    const std::string& session_id() const { return session_id_; }
    
protected:
    std::string session_id_;
};

/**
 * Session not found
 */
class SessionNotFoundError : public SessionError {
public:
    explicit SessionNotFoundError(const std::string& session_id)
        : SessionError("Session not found: " + session_id, session_id) {}
};

/**
 * Session is closed
 */
class SessionClosedError : public SessionError {
public:
    explicit SessionClosedError(const std::string& session_id = "")
        : SessionError("Session is closed", session_id) {}
};

/**
 * Tool errors
 */
class ToolError : public GeminiSDKError {
public:
    ToolError(const std::string& message, const std::string& tool_name = "")
        : GeminiSDKError(message, "TOOL_ERROR"), tool_name_(tool_name) {}
    
    const std::string& tool_name() const { return tool_name_; }
    
protected:
    std::string tool_name_;
};

/**
 * Tool not found
 */
class ToolNotFoundError : public ToolError {
public:
    explicit ToolNotFoundError(const std::string& tool_name)
        : ToolError("Tool not found: " + tool_name, tool_name) {}
};

/**
 * Tool execution error
 */
class ToolExecutionError : public ToolError {
public:
    ToolExecutionError(
        const std::string& tool_name,
        const std::string& message,
        const std::string& original_error = ""
    ) : ToolError(message, tool_name), original_error_(original_error) {}
    
    const std::string& original_error() const { return original_error_; }
    
private:
    std::string original_error_;
};

/**
 * Validation errors
 */
class ValidationError : public GeminiSDKError {
public:
    ValidationError(
        const std::string& message,
        const std::string& field = "",
        const std::string& value = ""
    ) : GeminiSDKError(message, "VALIDATION_ERROR"),
        field_(field),
        value_(value) {}
    
    const std::string& field() const { return field_; }
    const std::string& value() const { return value_; }
    
private:
    std::string field_;
    std::string value_;
};

/**
 * Configuration errors
 */
class ConfigurationError : public GeminiSDKError {
public:
    ConfigurationError(const std::string& message, const std::string& config_key = "")
        : GeminiSDKError(message, "CONFIGURATION_ERROR"), config_key_(config_key) {}
    
    const std::string& config_key() const { return config_key_; }
    
private:
    std::string config_key_;
};

/**
 * Stream errors
 */
class StreamError : public GeminiSDKError {
public:
    StreamError(const std::string& message, const std::string& partial_content = "")
        : GeminiSDKError(message, "STREAM_ERROR"), partial_content_(partial_content) {}
    
    const std::string& partial_content() const { return partial_content_; }
    
private:
    std::string partial_content_;
};

/**
 * Cancellation
 */
class CancellationError : public GeminiSDKError {
public:
    CancellationError() : GeminiSDKError("Operation cancelled", "CANCELLATION_ERROR") {}
};

/**
 * Timeout
 */
class TimeoutError : public GeminiSDKError {
public:
    TimeoutError(std::optional<double> timeout = std::nullopt)
        : GeminiSDKError("Operation timed out", "TIMEOUT_ERROR"), timeout_(timeout) {}
    
    std::optional<double> timeout() const { return timeout_; }
    
private:
    std::optional<double> timeout_;
};

/**
 * Onboarding errors
 */
class OnboardingError : public GeminiSDKError {
public:
    OnboardingError(const std::string& message, const std::string& tier_id = "")
        : GeminiSDKError(message, "ONBOARDING_ERROR"), tier_id_(tier_id) {}
    
    const std::string& tier_id() const { return tier_id_; }
    
private:
    std::string tier_id_;
};

} // namespace geminisdk

#endif // GEMINISDK_ERRORS_HPP
