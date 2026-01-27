/**
 * @file streaming.cpp
 * @brief Streaming example for GeminiSDK C++
 */

#include <geminisdk/geminisdk.hpp>
#include <iostream>

using namespace geminisdk;

int main() {
    std::cout << "GeminiSDK C++ - Streaming Example\n\n";
    
    try {
        Client client;
        client.start();
        
        SessionConfig config;
        config.model = "gemini-2.5-flash";
        config.streaming = true;
        
        auto session = client.create_session(config);
        
        // Register event handler for streaming
        session->on([](const SessionEvent& event) {
            switch (event.event_type) {
                case EventType::AssistantMessageDelta:
                    if (event.data.contains("deltaContent")) {
                        std::cout << event.data["deltaContent"].get<std::string>() << std::flush;
                    }
                    break;
                case EventType::AssistantMessage:
                    std::cout << "\n--- Complete ---\n";
                    break;
                default:
                    break;
            }
        });
        
        MessageOptions options;
        options.prompt = "Write a haiku about C++ programming";
        
        session->send(options);
        
        client.close();
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }
    
    return 0;
}
