/**
 * @file tools.cpp
 * @brief Tool utilities for GeminiSDK C++
 */

#include "geminisdk/tools.hpp"

namespace geminisdk {

ToolParametersBuilder& ToolParametersBuilder::add_string(const std::string& name, const std::string& description) {
    properties_[name] = {
        {"type", "string"},
        {"description", description}
    };
    return *this;
}

ToolParametersBuilder& ToolParametersBuilder::add_number(const std::string& name, const std::string& description) {
    properties_[name] = {
        {"type", "number"},
        {"description", description}
    };
    return *this;
}

ToolParametersBuilder& ToolParametersBuilder::add_integer(const std::string& name, const std::string& description) {
    properties_[name] = {
        {"type", "integer"},
        {"description", description}
    };
    return *this;
}

ToolParametersBuilder& ToolParametersBuilder::add_boolean(const std::string& name, const std::string& description) {
    properties_[name] = {
        {"type", "boolean"},
        {"description", description}
    };
    return *this;
}

ToolParametersBuilder& ToolParametersBuilder::add_enum(
    const std::string& name,
    const std::string& description,
    const std::vector<std::string>& values
) {
    properties_[name] = {
        {"type", "string"},
        {"description", description},
        {"enum", values}
    };
    return *this;
}

ToolParametersBuilder& ToolParametersBuilder::required(const std::vector<std::string>& fields) {
    required_ = fields;
    return *this;
}

json ToolParametersBuilder::build() const {
    return {
        {"properties", properties_},
        {"required", required_}
    };
}

Tool create_tool(
    const std::string& name,
    const std::string& description,
    const std::optional<json>& parameters
) {
    Tool tool;
    tool.name = name;
    tool.description = description;
    tool.parameters = parameters;
    return tool;
}

Tool define_tool(
    const std::string& name,
    const std::string& description,
    const ToolParametersBuilder& builder
) {
    return create_tool(name, description, builder.build());
}

ToolResult success_result(const std::string& text) {
    ToolResult result;
    result.result_type = ToolResultType::Success;
    result.text_result_for_llm = text;
    return result;
}

ToolResult failure_result(const std::string& text) {
    ToolResult result;
    result.result_type = ToolResultType::Failure;
    result.text_result_for_llm = text;
    return result;
}

ToolResult rejected_result(const std::string& text) {
    ToolResult result;
    result.result_type = ToolResultType::Rejected;
    result.text_result_for_llm = text;
    return result;
}

void ToolRegistry::register_tool(const Tool& tool, ToolHandler handler) {
    std::lock_guard<std::mutex> lock(mutex_);
    tools_[tool.name] = tool;
    handlers_[tool.name] = handler;
}

std::vector<Tool> ToolRegistry::tools() const {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<Tool> result;
    for (const auto& [name, tool] : tools_) {
        result.push_back(tool);
    }
    return result;
}

std::optional<Tool> ToolRegistry::get_tool(const std::string& name) const {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = tools_.find(name);
    if (it != tools_.end()) {
        return it->second;
    }
    return std::nullopt;
}

ToolHandler ToolRegistry::get_handler(const std::string& name) const {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = handlers_.find(name);
    if (it != handlers_.end()) {
        return it->second;
    }
    return nullptr;
}

ToolResult ToolRegistry::execute(const ToolInvocation& invocation) {
    ToolHandler handler;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = handlers_.find(invocation.name);
        if (it == handlers_.end()) {
            return failure_result("Tool '" + invocation.name + "' not found");
        }
        handler = it->second;
    }
    return handler(invocation);
}

void ToolRegistry::unregister(const std::string& name) {
    std::lock_guard<std::mutex> lock(mutex_);
    tools_.erase(name);
    handlers_.erase(name);
}

bool ToolRegistry::has(const std::string& name) const {
    std::lock_guard<std::mutex> lock(mutex_);
    return tools_.find(name) != tools_.end();
}

std::vector<std::string> ToolRegistry::names() const {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<std::string> result;
    for (const auto& [name, _] : tools_) {
        result.push_back(name);
    }
    return result;
}

} // namespace geminisdk
