//! Basic usage example for GeminiSDK Rust

use geminisdk::{GeminiClient, GeminiClientOptions, MessageOptions, SessionConfig};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    env_logger::init();

    println!("GeminiSDK Rust - Basic Usage Example\n");

    // Create client with default options
    let client = GeminiClient::new(GeminiClientOptions::default());

    // Start the client (authenticates with Gemini CLI credentials)
    println!("Starting client...");
    client.start().await?;
    println!("Client started and authenticated!\n");

    // List available models
    println!("Available models:");
    for model in client.list_models().await {
        println!("  - {} ({})", model.name, model.id);
    }
    println!();

    // Create a session
    println!("Creating session...");
    let session = client
        .create_session(SessionConfig {
            model: Some("gemini-2.5-flash".to_string()),
            streaming: Some(false), // Non-streaming for simplicity
            system_message: Some("You are a helpful assistant.".to_string()),
            ..Default::default()
        })
        .await?;

    println!("Session created: {}\n", session.session_id());

    // Send a message and wait for response
    println!("Sending message...");
    let response = session
        .send_and_wait(MessageOptions {
            prompt: "What are three interesting facts about the Rust programming language?"
                .to_string(),
            attachments: None,
            context: None,
        })
        .await?;

    println!("Response received:");
    println!("Event type: {:?}", response.event_type);
    if let Some(content) = response.data.get("content") {
        println!("Content: {}", content);
    }

    // Clean up
    println!("\nClosing client...");
    client.close().await?;
    println!("Done!");

    Ok(())
}
