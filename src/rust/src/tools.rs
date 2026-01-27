//! Tool utilities for GeminiSDK Rust.

use crate::types::{Tool, ToolInvocation, ToolResult, ToolResultType};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;

pub type BoxedToolHandler =
    Arc<dyn Fn(ToolInvocation) -> Pin<Box<dyn Future<Output = ToolResult> + Send>> + Send + Sync>;

/// Creates a tool definition from a name, description, and parameters schema.
pub fn create_tool(
    name: impl Into<String>,
    description: impl Into<String>,
    parameters: Option<Value>,
) -> Tool {
    Tool {
        name: name.into(),
        description: description.into(),
        parameters,
    }
}

/// A macro-friendly helper to define tool parameters.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ToolParameters {
    #[serde(default)]
    pub properties: HashMap<String, ToolProperty>,
    #[serde(default)]
    pub required: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolProperty {
    #[serde(rename = "type")]
    pub prop_type: String,
    pub description: Option<String>,
    #[serde(rename = "enum", skip_serializing_if = "Option::is_none")]
    pub enum_values: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default: Option<Value>,
}

impl ToolParameters {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_string(mut self, name: impl Into<String>, description: impl Into<String>) -> Self {
        self.properties.insert(
            name.into(),
            ToolProperty {
                prop_type: "string".to_string(),
                description: Some(description.into()),
                enum_values: None,
                default: None,
            },
        );
        self
    }

    pub fn add_number(mut self, name: impl Into<String>, description: impl Into<String>) -> Self {
        self.properties.insert(
            name.into(),
            ToolProperty {
                prop_type: "number".to_string(),
                description: Some(description.into()),
                enum_values: None,
                default: None,
            },
        );
        self
    }

    pub fn add_integer(mut self, name: impl Into<String>, description: impl Into<String>) -> Self {
        self.properties.insert(
            name.into(),
            ToolProperty {
                prop_type: "integer".to_string(),
                description: Some(description.into()),
                enum_values: None,
                default: None,
            },
        );
        self
    }

    pub fn add_boolean(mut self, name: impl Into<String>, description: impl Into<String>) -> Self {
        self.properties.insert(
            name.into(),
            ToolProperty {
                prop_type: "boolean".to_string(),
                description: Some(description.into()),
                enum_values: None,
                default: None,
            },
        );
        self
    }

    pub fn add_enum(
        mut self,
        name: impl Into<String>,
        description: impl Into<String>,
        values: Vec<String>,
    ) -> Self {
        self.properties.insert(
            name.into(),
            ToolProperty {
                prop_type: "string".to_string(),
                description: Some(description.into()),
                enum_values: Some(values),
                default: None,
            },
        );
        self
    }

    pub fn required(mut self, fields: Vec<&str>) -> Self {
        self.required = fields.into_iter().map(String::from).collect();
        self
    }

    pub fn to_value(&self) -> Value {
        serde_json::to_value(self).unwrap_or(json!({}))
    }
}

/// Tool registry for managing multiple tools.
pub struct ToolRegistry {
    tools: HashMap<String, Tool>,
    handlers: HashMap<String, BoxedToolHandler>,
}

impl Default for ToolRegistry {
    fn default() -> Self {
        Self::new()
    }
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self {
            tools: HashMap::new(),
            handlers: HashMap::new(),
        }
    }

    /// Register a tool with its handler.
    pub fn register<F, Fut>(&mut self, tool: Tool, handler: F)
    where
        F: Fn(ToolInvocation) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = ToolResult> + Send + 'static,
    {
        let name = tool.name.clone();
        self.tools.insert(name.clone(), tool);
        self.handlers.insert(
            name,
            Arc::new(move |inv| Box::pin(handler(inv)) as Pin<Box<dyn Future<Output = ToolResult> + Send>>),
        );
    }

    /// Get all registered tools.
    pub fn tools(&self) -> Vec<Tool> {
        self.tools.values().cloned().collect()
    }

    /// Get a tool by name.
    pub fn get_tool(&self, name: &str) -> Option<&Tool> {
        self.tools.get(name)
    }

    /// Get a handler by name.
    pub fn get_handler(&self, name: &str) -> Option<&BoxedToolHandler> {
        self.handlers.get(name)
    }

    /// Execute a tool invocation.
    pub async fn execute(&self, invocation: ToolInvocation) -> ToolResult {
        if let Some(handler) = self.handlers.get(&invocation.name) {
            handler(invocation).await
        } else {
            ToolResult {
                result_type: Some(ToolResultType::Failure),
                text_result_for_llm: Some(format!("Tool '{}' not found", invocation.name)),
                binary_result: None,
                session_log: None,
            }
        }
    }

    /// Unregister a tool.
    pub fn unregister(&mut self, name: &str) {
        self.tools.remove(name);
        self.handlers.remove(name);
    }

    /// Check if a tool is registered.
    pub fn has(&self, name: &str) -> bool {
        self.tools.contains_key(name)
    }

    /// Get all tool names.
    pub fn names(&self) -> Vec<String> {
        self.tools.keys().cloned().collect()
    }
}

/// Helper to create a success result.
pub fn success_result(text: impl Into<String>) -> ToolResult {
    ToolResult {
        result_type: Some(ToolResultType::Success),
        text_result_for_llm: Some(text.into()),
        binary_result: None,
        session_log: None,
    }
}

/// Helper to create a failure result.
pub fn failure_result(text: impl Into<String>) -> ToolResult {
    ToolResult {
        result_type: Some(ToolResultType::Failure),
        text_result_for_llm: Some(text.into()),
        binary_result: None,
        session_log: None,
    }
}

/// Helper to create a rejected result.
pub fn rejected_result(text: impl Into<String>) -> ToolResult {
    ToolResult {
        result_type: Some(ToolResultType::Rejected),
        text_result_for_llm: Some(text.into()),
        binary_result: None,
        session_log: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_tool() {
        let tool = create_tool(
            "test_tool",
            "A test tool",
            Some(
                ToolParameters::new()
                    .add_string("input", "The input string")
                    .required(vec!["input"])
                    .to_value(),
            ),
        );

        assert_eq!(tool.name, "test_tool");
        assert_eq!(tool.description, "A test tool");
        assert!(tool.parameters.is_some());
    }

    #[test]
    fn test_tool_parameters() {
        let params = ToolParameters::new()
            .add_string("name", "User name")
            .add_integer("age", "User age")
            .add_boolean("active", "Is active")
            .add_enum("status", "User status", vec!["online".into(), "offline".into()])
            .required(vec!["name", "age"]);

        let value = params.to_value();
        assert!(value.get("properties").is_some());
        assert!(value.get("required").is_some());
    }
}
