/**
 * @file tools.hpp
 * @brief Tool utilities for GeminiSDK C++
 */

#ifndef GEMINISDK_TOOLS_HPP
#define GEMINISDK_TOOLS_HPP

#include "types.hpp"
#include <map>
#include <mutex>

namespace geminisdk {

/**
 * Tool parameter builder
 */
class ToolParametersBuilder {
public:
    ToolParametersBuilder() = default;
    
    /**
     * Add a string parameter
     * @param name Parameter name
     * @param description Parameter description
     * @return Reference to this builder
     */
    ToolParametersBuilder& add_string(const std::string& name, const std::string& description);
    
    /**
     * Add a number parameter
     * @param name Parameter name
     * @param description Parameter description
     * @return Reference to this builder
     */
    ToolParametersBuilder& add_number(const std::string& name, const std::string& description);
    
    /**
     * Add an integer parameter
     * @param name Parameter name
     * @param description Parameter description
     * @return Reference to this builder
     */
    ToolParametersBuilder& add_integer(const std::string& name, const std::string& description);
    
    /**
     * Add a boolean parameter
     * @param name Parameter name
     * @param description Parameter description
     * @return Reference to this builder
     */
    ToolParametersBuilder& add_boolean(const std::string& name, const std::string& description);
    
    /**
     * Add an enum parameter
     * @param name Parameter name
     * @param description Parameter description
     * @param values Allowed values
     * @return Reference to this builder
     */
    ToolParametersBuilder& add_enum(
        const std::string& name,
        const std::string& description,
        const std::vector<std::string>& values
    );
    
    /**
     * Mark parameters as required
     * @param fields Required field names
     * @return Reference to this builder
     */
    ToolParametersBuilder& required(const std::vector<std::string>& fields);
    
    /**
     * Build the parameters JSON
     * @return JSON object
     */
    json build() const;
    
private:
    std::map<std::string, json> properties_;
    std::vector<std::string> required_;
};

/**
 * Create a tool definition
 * @param name Tool name
 * @param description Tool description
 * @param parameters Parameters JSON (optional)
 * @return Tool definition
 */
Tool create_tool(
    const std::string& name,
    const std::string& description,
    const std::optional<json>& parameters = std::nullopt
);

/**
 * Create a tool with parameter builder
 * @param name Tool name
 * @param description Tool description
 * @param builder Parameter builder
 * @return Tool definition
 */
Tool define_tool(
    const std::string& name,
    const std::string& description,
    const ToolParametersBuilder& builder
);

/**
 * Create a success tool result
 * @param text Result text
 * @return Tool result
 */
ToolResult success_result(const std::string& text);

/**
 * Create a failure tool result
 * @param text Error text
 * @return Tool result
 */
ToolResult failure_result(const std::string& text);

/**
 * Create a rejected tool result
 * @param text Rejection text
 * @return Tool result
 */
ToolResult rejected_result(const std::string& text);

/**
 * Tool registry for managing multiple tools
 */
class ToolRegistry {
public:
    ToolRegistry() = default;
    
    /**
     * Register a tool with handler
     * @param tool Tool definition
     * @param handler Tool handler
     */
    void register_tool(const Tool& tool, ToolHandler handler);
    
    /**
     * Get all registered tools
     * @return Tool list
     */
    std::vector<Tool> tools() const;
    
    /**
     * Get a tool by name
     * @param name Tool name
     * @return Tool or nullopt
     */
    std::optional<Tool> get_tool(const std::string& name) const;
    
    /**
     * Get a handler by name
     * @param name Tool name
     * @return Handler or nullptr
     */
    ToolHandler get_handler(const std::string& name) const;
    
    /**
     * Execute a tool invocation
     * @param invocation Tool invocation
     * @return Tool result
     */
    ToolResult execute(const ToolInvocation& invocation);
    
    /**
     * Unregister a tool
     * @param name Tool name
     */
    void unregister(const std::string& name);
    
    /**
     * Check if a tool is registered
     * @param name Tool name
     * @return true if registered
     */
    bool has(const std::string& name) const;
    
    /**
     * Get all tool names
     * @return Tool name list
     */
    std::vector<std::string> names() const;
    
private:
    std::map<std::string, Tool> tools_;
    std::map<std::string, ToolHandler> handlers_;
    mutable std::mutex mutex_;
};

} // namespace geminisdk

#endif // GEMINISDK_TOOLS_HPP
