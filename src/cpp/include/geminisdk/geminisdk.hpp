/**
 * @file geminisdk.hpp
 * @brief Main header for GeminiSDK C++
 * 
 * C++ SDK for Google Gemini CLI / Code Assist API.
 * Provides full-featured client with OAuth authentication, streaming,
 * sessions, and tool calling.
 */

#ifndef GEMINISDK_HPP
#define GEMINISDK_HPP

#include "geminisdk/types.hpp"
#include "geminisdk/errors.hpp"
#include "geminisdk/auth.hpp"
#include "geminisdk/backend.hpp"
#include "geminisdk/session.hpp"
#include "geminisdk/client.hpp"
#include "geminisdk/tools.hpp"

namespace geminisdk {

/// SDK version
constexpr const char* VERSION = "0.1.0";

} // namespace geminisdk

#endif // GEMINISDK_HPP
