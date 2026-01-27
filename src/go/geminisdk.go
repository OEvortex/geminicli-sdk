// Package geminisdk provides a Go SDK for Google Gemini CLI / Code Assist API.
//
// This SDK enables interaction with Google's Gemini models using OAuth credentials
// from the Gemini CLI. It supports:
//   - Session-based conversations
//   - Streaming responses (SSE)
//   - Tool/function calling
//   - Thinking/reasoning mode
//
// Quick Start:
//
//	client := geminisdk.NewClient(nil)
//	if err := client.Start(context.Background()); err != nil {
//	    log.Fatal(err)
//	}
//	defer client.Close()
//
//	session, _ := client.CreateSession(&geminisdk.SessionConfig{
//	    Model: "gemini-2.5-pro",
//	})
//
//	response, _ := session.SendAndWait(context.Background(), &geminisdk.MessageOptions{
//	    Prompt: "Hello, Gemini!",
//	})
//	fmt.Println(response.Data)
package geminisdk

// Version of the SDK
const Version = "0.1.0"
