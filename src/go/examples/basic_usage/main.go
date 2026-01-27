// Example: Basic usage of GeminiSDK Go
package main

import (
	"context"
	"fmt"
	"log"

	geminisdk "github.com/OEvortex/geminicli-sdk/go"
)

func main() {
	fmt.Println("GeminiSDK Go - Basic Usage Example\n")

	ctx := context.Background()

	// Create client with default options
	client := geminisdk.NewClient(nil)

	// Start the client (authenticates with Gemini CLI credentials)
	fmt.Println("Starting client...")
	if err := client.Start(ctx); err != nil {
		log.Fatalf("Failed to start client: %v", err)
	}
	defer client.Close()
	fmt.Println("Client started and authenticated!\n")

	// List available models
	fmt.Println("Available models:")
	for _, model := range client.ListModels() {
		fmt.Printf("  - %s (%s)\n", model.Name, model.ID)
	}
	fmt.Println()

	// Create a session
	fmt.Println("Creating session...")
	session, err := client.CreateSession(ctx, &geminisdk.SessionConfig{
		Model:         "gemini-2.5-flash",
		Streaming:     false, // Non-streaming for simplicity
		SystemMessage: "You are a helpful assistant.",
	})
	if err != nil {
		log.Fatalf("Failed to create session: %v", err)
	}
	fmt.Printf("Session created: %s\n\n", session.SessionID())

	// Send a message and wait for response
	fmt.Println("Sending message...")
	response, err := session.SendAndWait(ctx, &geminisdk.MessageOptions{
		Prompt: "What are three interesting facts about the Go programming language?",
	})
	if err != nil {
		log.Fatalf("Failed to send message: %v", err)
	}

	fmt.Println("Response received:")
	fmt.Printf("Event type: %s\n", response.EventType)
	if content, ok := response.Data["content"].(string); ok {
		fmt.Printf("Content: %s\n", content)
	}

	fmt.Println("\nDone!")
}
