/**
 * @file tool_calling.cpp
 * @brief Tool calling example for GeminiSDK C++
 */

#include <geminisdk/geminisdk.hpp>
#include <iostream>

using namespace geminisdk;

int main() {
    std::cout << "GeminiSDK C++ - Tool Calling Example\n\n";
    
    try {
        Client client;
        client.start();
        
        // Create tool
        auto weather_tool = define_tool(
            "get_weather",
            "Get current weather for a city",
            ToolParametersBuilder()
                .add_string("city", "The city name")
                .required({"city"})
        );
        
        SessionConfig config;
        config.model = "gemini-2.5-pro";
        config.tools = {weather_tool};
        config.streaming = false;
        
        auto session = client.create_session(config);
        
        // Register tool handler
        session->register_tool_handler("get_weather", [](const ToolInvocation& inv) {
            std::string city = "Unknown";
            if (inv.arguments.count("city")) {
                city = inv.arguments.at("city").get<std::string>();
            }
            return success_result("Weather in " + city + ": 72°F, Sunny");
        });
        
        // Register event handler
        session->on([](const SessionEvent& event) {
            if (event.event_type == EventType::ToolCall) {
                std::cout << "Tool called: " << event.data["name"].get<std::string>() << "\n";
            } else if (event.event_type == EventType::ToolResult) {
                std::cout << "Tool result: " << event.data["result"].get<std::string>() << "\n";
            }
        });
        
        MessageOptions options;
        options.prompt = "What's the weather in Tokyo?";
        
        auto response = session->send_and_wait(options);
        
        if (response.data.contains("content")) {
            std::cout << "\nFinal response: " << response.data["content"].get<std::string>() << "\n";
        }
        
        client.close();
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }
    
    return 0;
}
