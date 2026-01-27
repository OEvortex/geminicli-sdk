/**
 * @file basic_usage.cpp
 * @brief Basic usage example for GeminiSDK C++
 */

#include <geminisdk/geminisdk.hpp>
#include <iostream>

using namespace geminisdk;

int main() {
    std::cout << "GeminiSDK C++ - Basic Usage Example\n\n";
    
    try {
        // Create client with default options
        Client client;
        
        // Start the client (authenticates with Gemini CLI credentials)
        std::cout << "Starting client...\n";
        client.start();
        std::cout << "Client started and authenticated!\n\n";
        
        // List available models
        std::cout << "Available models:\n";
        for (const auto& model : client.list_models()) {
            std::cout << "  - " << model.name << " (" << model.id << ")\n";
        }
        std::cout << "\n";
        
        // Create a session
        std::cout << "Creating session...\n";
        SessionConfig config;
        config.model = "gemini-2.5-flash";
        config.streaming = false;  // Non-streaming for simplicity
        config.system_message = "You are a helpful assistant.";
        
        auto session = client.create_session(config);
        std::cout << "Session created: " << session->session_id() << "\n\n";
        
        // Send a message and wait for response
        std::cout << "Sending message...\n";
        MessageOptions options;
        options.prompt = "What are three interesting facts about the C++ programming language?";
        
        auto response = session->send_and_wait(options);
        
        std::cout << "Response received:\n";
        std::cout << "Event type: " << event_type_to_string(response.event_type) << "\n";
        if (response.data.contains("content")) {
            std::cout << "Content: " << response.data["content"].get<std::string>() << "\n";
        }
        
        // Clean up
        std::cout << "\nClosing client...\n";
        client.close();
        std::cout << "Done!\n";
        
    } catch (const GeminiSDKError& e) {
        std::cerr << "GeminiSDK Error: " << e.what() << "\n";
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }
    
    return 0;
}
