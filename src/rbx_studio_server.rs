use crate::error::Result;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::{extract::State, Json};
use color_eyre::eyre::{Error, OptionExt};
use rmcp::model::{
    CallToolResult, Content, ErrorData, Implementation, ProtocolVersion, ServerCapabilities,
    ServerInfo,
    // ToolDefinition, ToolSchema removed
};
use rmcp::tool;
use rmcp::{Error as McpError, ServerHandler};
use serde::{Deserialize, Serialize};
// serde_json::Value removed for now as a diagnostic step
use std::collections::{HashMap, VecDeque}; // HashMap might be unused now in this file's scope
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::sync::oneshot::Receiver;
use tokio::sync::{mpsc, watch, Mutex};
use tokio::time::Duration;
use uuid::Uuid;

pub const STUDIO_PLUGIN_PORT: u16 = 44755;
const LONG_POLL_DURATION: Duration = Duration::from_secs(15);

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct ToolArguments {
    args: ToolArgumentValues,
    id: Option<Uuid>,
}

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct RunCommandResponse {
    response: String,
    id: Uuid,
}

#[derive(Clone, Debug)]
pub struct DiscoveredTool {
    pub file_path: PathBuf,
    // We can add more fields later, like a description extracted from comments if possible.
}

pub struct AppState {
    process_queue: VecDeque<ToolArguments>,
    output_map: HashMap<Uuid, mpsc::UnboundedSender<Result<String>>>,
    waiter: watch::Receiver<()>,
    trigger: watch::Sender<()>,
    discovered_luau_tools: HashMap<String, DiscoveredTool>,
}
pub type PackedState = Arc<Mutex<AppState>>;

fn discover_luau_tools(tools_dir_path: &Path) -> HashMap<String, DiscoveredTool> {
    let mut tools = HashMap::new();
    tracing::info!("Attempting to discover Luau tools in: {:?}", tools_dir_path);

    if !tools_dir_path.exists() {
        tracing::warn!("Luau tools directory does not exist: {:?}", tools_dir_path);
        return tools; // Return empty map if dir doesn't exist
    }
    if !tools_dir_path.is_dir() {
        tracing::error!("Luau tools path is not a directory: {:?}", tools_dir_path);
        // In case of error, return empty map, error already logged.
        return tools;
    }

    match fs::read_dir(tools_dir_path) {
        Ok(entries) => {
            for entry in entries {
                match entry {
                    Ok(entry) => {
                        let path = entry.path();
                        if path.is_file() {
                            if let Some(extension) = path.extension() {
                                if extension == "luau" {
                                    if let Some(stem) = path.file_stem() {
                                        if let Some(tool_name) = stem.to_str() {
                                            tracing::info!("Discovered Luau tool: {} at {:?}", tool_name, path);
                                            tools.insert(
                                                tool_name.to_string(),
                                                DiscoveredTool { file_path: path.clone() },
                                            );
                                        } else {
                                            tracing::warn!("Could not convert tool name (file stem) to string for path: {:?}", path);
                                        }
                                    } else {
                                        tracing::warn!("Could not get file stem for path: {:?}", path);
                                    }
                                }
                            }
                        }
                    }
                    Err(e) => {
                        tracing::error!("Error reading directory entry in {:?}: {}", tools_dir_path, e);
                    }
                }
            }
        }
        Err(e) => {
            tracing::error!("Failed to read Luau tools directory {:?}: {}", tools_dir_path, e);
            // Return empty map on error, error already logged.
        }
    }
    if tools.is_empty() {
        tracing::info!("No Luau tools discovered or directory was empty: {:?}", tools_dir_path);
    } else {
        tracing::info!("Successfully discovered {} Luau tools: [{}]", tools.len(), tools.keys().cloned().collect::<Vec<String>>().join(", "));
    }
    tools
}

impl AppState {
    pub fn new() -> Self {
        let (trigger, waiter) = watch::channel(());

        let discovered_luau_tools = match env::current_exe().ok()
            .and_then(|p| p.parent().map(PathBuf::from)) // .../target/debug or .../target/release
            .and_then(|p| p.parent().map(PathBuf::from)) // .../target
            .and_then(|p| p.parent().map(PathBuf::from)) // .../ (project root)
            .map(|p| p.join("plugin/src/Tools"))
        {
            Some(tools_dir) => {
                tracing::info!("Resolved Luau tools directory to: {:?}", tools_dir);
                discover_luau_tools(&tools_dir)
            }
            None => {
                tracing::warn!("Could not determine Luau tools directory from executable path. Initializing with empty toolset.");
                HashMap::new()
            }
        };

        Self {
            process_queue: VecDeque::new(),
            output_map: HashMap::new(),
            waiter,
            trigger,
            discovered_luau_tools,
        }
    }
}

impl ToolArguments {
    fn new(args: ToolArgumentValues) -> (Self, Uuid) {
        Self { args, id: None }.with_id()
    }
    fn with_id(self) -> (Self, Uuid) {
        let id = Uuid::new_v4();
        (
            Self {
                args: self.args,
                id: Some(id),
            },
            id,
        )
    }
}
#[derive(Clone)]
pub struct RBXStudioServer {
    state: PackedState,
}

#[tool(tool_box)]
impl ServerHandler for RBXStudioServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::V_2025_03_26,
            server_info: Implementation::from_build_env(),
            instructions: Some(
                "Use 'execute_discovered_luau_tool' to run Luau scripts by name (e.g., CreateInstance, RunCode). Also available: run_command (direct Luau string), insert_model.".to_string()
            ),
            // Let `#[tool(tool_box)]` and `Default::default()` populate capabilities.
            // The `capabilities.tools` field will be derived from `ServerCapabilities::default()`
            // and then populated by the `tool_box` macro with tools defined in Rust
            // (i.e., run_command, insert_model, execute_discovered_luau_tool).
            capabilities: ServerCapabilities::default(),
            // Other ServerInfo fields like `custom_capabilities` are not used, so rely on default.
        }
    }
}

#[derive(Deserialize, Serialize, Clone, Debug)]
enum ToolArgumentValues {
    RunCommand { command: String },
    InsertModel { query: String },
    ExecuteLuauByName {
        tool_name: String,      // e.g., "CreateInstance"
        arguments_json: String, // JSON string of arguments for the Luau script
    },
}
#[tool(tool_box)]
impl RBXStudioServer {
    pub fn new(state: PackedState) -> Self {
        Self { state }
    }

    #[tool(
        description = "Executes a specific Luau tool script by its name with given arguments. The Luau script is sourced from the 'plugin/src/Tools' directory."
    )]
    async fn execute_discovered_luau_tool(
        &self,
        #[tool(param)]
        #[schemars(description = "Name of the Luau tool file (without .luau extension) to execute.")]
        tool_name: String,
        #[tool(param)]
        #[schemars(description = "A JSON string representing arguments for the Luau tool.")] // Updated description
        tool_arguments_str: String, // Changed from tool_arguments: Value to tool_arguments_str: String
    ) -> Result<CallToolResult, McpError> {
        // Lock state to check if the tool exists
        let app_state = self.state.lock().await;
        if !app_state.discovered_luau_tools.contains_key(&tool_name) {
            tracing::error!("Attempted to execute unknown Luau tool: {}", tool_name);
            return Ok(CallToolResult::error(vec![Content::text(format!(
                "Luau tool '{}' not found or not discovered.",
                tool_name
            ))]));
        }
        // Drop the lock as it's no longer needed
        drop(app_state);

        // Now tool_arguments_str is already a String, no need to serialize.
        // Basic validation could be added here to ensure it's a valid JSON string if necessary,
        // but for now, we'll pass it directly.
        let arguments_json = tool_arguments_str;

        self.generic_tool_run(ToolArgumentValues::ExecuteLuauByName {
            tool_name,
            arguments_json,
        })
        .await
    }

    #[tool(
        description = "Runs a command in Roblox Studio and returns the printed output. Can be used to both make changes and retrieve information"
    )]
    async fn run_command(
        &self,
        #[tool(param)]
        #[schemars(description = "code to run")]
        command: String,
    ) -> Result<CallToolResult, McpError> {
        self.generic_tool_run(ToolArgumentValues::RunCommand { command })
            .await
    }

    #[tool(
        description = "Inserts a model from the Roblox marketplace into the workspace. Returns the inserted model name."
    )]
    async fn insert_model(
        &self,
        #[tool(param)]
        #[schemars(description = "Query to search for the model.")]
        query: String,
    ) -> Result<CallToolResult, McpError> {
        self.generic_tool_run(ToolArgumentValues::InsertModel { query })
            .await
    }

    async fn generic_tool_run(&self, args: ToolArgumentValues) -> Result<CallToolResult, McpError> {
        let (command, id) = ToolArguments::new(args);
        tracing::debug!("Running command: {:?}", command);
        let (tx, mut rx) = mpsc::unbounded_channel::<Result<String>>();
        let trigger = {
            let mut state = self.state.lock().await;
            state.process_queue.push_back(command);
            state.output_map.insert(id, tx);
            state.trigger.clone()
        };
        trigger
            .send(())
            .map_err(|e| ErrorData::internal_error(format!("Unable to trigger send {e}"), None))?;
        let result = rx
            .recv()
            .await
            .ok_or(ErrorData::internal_error("Couldn't receive response", None))?;
        {
            let mut state = self.state.lock().await;
            state.output_map.remove_entry(&id);
        }
        tracing::debug!("Sending to MCP: {result:?}");
        match result {
            Ok(result) => Ok(CallToolResult::success(vec![Content::text(result)])),
            Err(err) => Ok(CallToolResult::error(vec![Content::text(err.to_string())])),
        }
    }
}

pub async fn request_handler(State(state): State<PackedState>) -> Result<impl IntoResponse> {
    let timeout = tokio::time::timeout(LONG_POLL_DURATION, async {
        loop {
            let mut waiter = {
                let mut state = state.lock().await;
                if let Some(task) = state.process_queue.pop_front() {
                    return Ok::<ToolArguments, Error>(task);
                }
                state.waiter.clone()
            };
            waiter.changed().await?
        }
    })
    .await;
    match timeout {
        Ok(result) => Ok(Json(result?).into_response()),
        _ => Ok((StatusCode::LOCKED, String::new()).into_response()),
    }
}

pub async fn response_handler(
    State(state): State<PackedState>,
    Json(payload): Json<RunCommandResponse>,
) -> Result<impl IntoResponse> {
    tracing::debug!("Received reply from studio {payload:?}");
    let mut state = state.lock().await;
    let tx = state
        .output_map
        .remove(&payload.id)
        .ok_or_eyre("Unknown ID")?;
    Ok(tx.send(Ok(payload.response))?)
}

pub async fn proxy_handler(
    State(state): State<PackedState>,
    Json(command): Json<ToolArguments>,
) -> Result<impl IntoResponse> {
    let id = command.id.ok_or_eyre("Got proxy command with no id")?;
    tracing::debug!("Received request to proxy {command:?}");
    let (tx, mut rx) = mpsc::unbounded_channel();
    {
        let mut state = state.lock().await;
        state.process_queue.push_back(command);
        state.output_map.insert(id, tx);
    }
    let response = rx.recv().await.ok_or_eyre("Couldn't receive response")??;
    {
        let mut state = state.lock().await;
        state.output_map.remove_entry(&id);
    }
    tracing::debug!("Sending back to dud: {response:?}");
    Ok(Json(RunCommandResponse { response, id }))
}

pub async fn dud_proxy_loop(state: PackedState, exit: Receiver<()>) {
    let client = reqwest::Client::new();

    let mut waiter = { state.lock().await.waiter.clone() };
    while exit.is_empty() {
        let entry = { state.lock().await.process_queue.pop_front() };
        if let Some(entry) = entry {
            let res = client
                .post(format!("http://127.0.0.1:{STUDIO_PLUGIN_PORT}/proxy"))
                .json(&entry)
                .send()
                .await;
            if let Ok(res) = res {
                let tx = {
                    state
                        .lock()
                        .await
                        .output_map
                        .remove(&entry.id.unwrap())
                        .unwrap()
                };
                let res = res
                    .json::<RunCommandResponse>()
                    .await
                    .map(|r| r.response)
                    .map_err(Into::into);
                tx.send(res).unwrap();
            } else {
                tracing::error!("Failed to proxy: {res:?}");
            };
        } else {
            waiter.changed().await.unwrap();
        }
    }
}
