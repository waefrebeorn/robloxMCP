
// Necessary imports
use crate::error::Result;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::{extract::State, Json};
// color_eyre is not directly used, McpError handles errors.
use rmcp::model::{
    ServerCapabilities, ServerInfo, ProtocolVersion, Implementation, Content, CallToolResult, ToolsCapability,
};
use rmcp::schemars;
use rmcp::tool;
use rmcp::{Error as McpError, ServerHandler};

use std::collections::{HashMap, VecDeque};
// use serde_json::Value; // Likely not needed if serde_json::Map and json! macro are used
use std::path::{Path, PathBuf};
use std::fs;
use std::env;

use std::sync::Arc;
use tokio::sync::oneshot::Receiver; // If dud_proxy_loop uses it
use tokio::sync::{mpsc, watch, Mutex};
use tokio::time::Duration;
use uuid::Uuid;

use tracing::{debug, error, info, warn};


pub const STUDIO_PLUGIN_PORT: u16 = 44755;
const LONG_POLL_DURATION: Duration = Duration::from_secs(15);

// DiscoveredTool struct
#[derive(Clone, Debug)]
pub struct DiscoveredTool {
    pub file_path: PathBuf,
}

// discover_luau_tools function
pub fn discover_luau_tools(tools_dir_path: &Path) -> HashMap<String, DiscoveredTool> {
    let mut tools = HashMap::new();

    info!("Attempting to discover Luau tools in: {:?}", tools_dir_path);
    if !tools_dir_path.exists() {
        warn!("Luau tools directory does not exist: {:?}", tools_dir_path);
        return tools;
    }
    if !tools_dir_path.is_dir() {
        error!("Luau tools path is not a directory: {:?}", tools_dir_path);
        return tools;
    }

    match fs::read_dir(tools_dir_path) {
        Ok(entries) => {
            for entry in entries.filter_map(Result::ok) {
                let path = entry.path();
                if path.is_file() && path.extension().and_then(|s| s.to_str()) == Some("luau") {
                    if let Some(tool_name) = path.file_stem().and_then(|s| s.to_str()).map(String::from) {
                        info!("Discovered Luau tool: {} at {:?}", tool_name, path);
                        tools.insert(tool_name, DiscoveredTool { file_path: path });

                    } else {
                        warn!("Could not convert tool name (file stem) to string for path: {:?}", path);

                    }
                }
            }
        }
        Err(e) => {
            error!("Failed to read Luau tools directory {:?}: {}", tools_dir_path, e);
        }
    }

    if tools.is_empty() {
        info!("No Luau tools discovered or directory was empty: {:?}", tools_dir_path);
    } else {
        info!("Successfully discovered {} Luau tools: [{}]", tools.len(), tools.keys().cloned().collect::<Vec<String>>().join(", "));
    }
    tools
}

// AppState struct and ::new()

pub struct AppState {
    process_queue: VecDeque<ToolArguments>,
    output_map: HashMap<Uuid, mpsc::UnboundedSender<Result<String, McpError>>>,
    waiter: watch::Receiver<()>,
    trigger: watch::Sender<()>,
    discovered_luau_tools: HashMap<String, DiscoveredTool>,
}
pub type PackedState = Arc<Mutex<AppState>>;

impl AppState {
    pub fn new() -> Self {
        let (trigger, waiter) = watch::channel(());

        // Corrected path finding logic for AppState::new()
        let base_path = env::current_exe().ok()
            .and_then(|p| p.parent().map(PathBuf::from)) // target/debug or target/release
            .and_then(|p| p.parent().map(PathBuf::from)) // target
            .and_then(|p| p.parent().map(PathBuf::from)) // project root
            .unwrap_or_else(|| PathBuf::from(".")); // Default to current dir if path fails

        // Corrected fallback path for consistency
        let tools_dir_pathbuf = base_path.join("plugin/src/Tools");

        info!("Attempting to discover Luau tools in: {:?}", tools_dir_pathbuf);
        let discovered_tools = discover_luau_tools(&tools_dir_pathbuf); // Pass by reference
        if discovered_tools.is_empty() {
            warn!("No Luau tools discovered in {:?}. Ensure path is correct and .luau files exist.", tools_dir_pathbuf);
        }


        Self {
            process_queue: VecDeque::new(),
            output_map: HashMap::new(),
            waiter,
            trigger,

            discovered_luau_tools: discovered_tools,

        }
    }
}

#[derive(rmcp::serde::Deserialize, rmcp::serde::Serialize, Clone, Debug)]
pub enum ToolArgumentValues {
    RunCommand { command: String },
    InsertModel { query: String },
    ExecuteLuauByName {
        tool_name: String,
        arguments_json: String,
    }
}

#[derive(rmcp::serde::Deserialize, rmcp::serde::Serialize, Clone, Debug)]
pub struct ToolArguments {
    args: ToolArgumentValues,
    id: Option<Uuid>,
}

impl ToolArguments {
     fn new_with_id(args_values: ToolArgumentValues) -> (Self, Uuid) {
         let id = Uuid::new_v4();
         (
             Self {
                 args: args_values,
                 id: Some(id),
             },
             id,
         )
     }
}


// RunCommandResponse struct
#[derive(rmcp::serde::Deserialize, rmcp::serde::Serialize, Clone, Debug)]
pub struct RunCommandResponse {
    response: String,

    id: Uuid,
}

// RBXStudioServer struct and ::new()
#[derive(Clone)]
pub struct RBXStudioServer {
    state: PackedState,
}

impl RBXStudioServer {
    pub fn new(state: PackedState) -> Self {
        Self { state }
    }

    async fn generic_tool_run(&self, args_values: ToolArgumentValues) -> Result<CallToolResult, McpError> {
         let (command_with_wrapper_id, id) = ToolArguments::new_with_id(args_values);
         info!(target: "mcp_server::generic_tool_run", request_id = %id, command_args = ?command_with_wrapper_id.args, "Queueing command for plugin");
         debug!("Queueing command for plugin: {:?}", command_with_wrapper_id.args);
         let (tx, mut rx) = mpsc::unbounded_channel::<Result<String, McpError>>();
         let trigger = {
             let mut state = self.state.lock().await;
             state.process_queue.push_back(command_with_wrapper_id);
             state.output_map.insert(id, tx);
             state.trigger.clone()
         };
         trigger.send(()).map_err(|e| McpError::internal_error(format!("Unable to trigger send for plugin: {e}"), None))?;
         info!(target: "mcp_server::generic_tool_run", request_id = %id, "Trigger sent for queued command");

         info!(target: "mcp_server::generic_tool_run", request_id = %id, "Waiting for plugin response from channel");
         let result_from_plugin_result = rx.recv().await
             .ok_or_else(|| McpError::internal_error("Plugin response channel closed unexpectedly.", None))?;

         match &result_from_plugin_result {
            Ok(res_str) => info!(target: "mcp_server::generic_tool_run", request_id = %id, response_len = res_str.len(), "Received successful response from plugin channel"),
            Err(e) => warn!(target: "mcp_server::generic_tool_run", request_id = %id, error = ?e, "Received error from plugin channel"),
         }

         {
             let mut state = self.state.lock().await;
             state.output_map.remove(&id);
         }

         match result_from_plugin_result {
            Ok(res_str) => {
                debug!("Received success from plugin, sending to MCP client: {:?}", res_str);
                Ok(CallToolResult::success(vec![Content::text(res_str)]))
            }
            Err(mcp_err) => {


                error!("Received error from plugin for id {}: {:?}", id, mcp_err);
                Ok(CallToolResult::error(vec![Content::text(mcp_err.to_string())]))
            }
        }
    }
}



#[tool(tool_box)]
impl ServerHandler for RBXStudioServer {
    fn get_info(&self) -> ServerInfo {
        let mut base_capabilities = ServerCapabilities::builder().enable_tools().build();
        if let Some(tools_caps) = base_capabilities.tools.as_mut() {
            tools_caps.list_changed = Some(true); // Explicitly set list_changed
        } else {
            // This case should ideally not happen if enable_tools() guarantees Some(ToolsCapability::default())
            base_capabilities.tools = Some(ToolsCapability { list_changed: Some(true) });
        }

        // Luau tool discovery and processing is simplified to just logging.
        // No `tools_map` or `rmcp::model::Tool` construction needed here anymore.
        if let Ok(app_state) = self.state.try_lock() {
            for (tool_name, _) in &app_state.discovered_luau_tools { // Changed _discovered_tool to _
                tracing::info!("Discovered Luau tool (not added to capabilities.tools due to API limitations): {}", tool_name);
            }
        } else {
            tracing::warn!("Could not lock AppState in get_info to add Luau tools to capabilities. Proceeding with macro-defined tools only.");
        }

        // base_capabilities.tools will remain as initialized by ServerCapabilities::builder().enable_tools().build();
        // and potentially modified by setting list_changed.
        // Luau tools are not merged back.

        ServerInfo {
            protocol_version: ProtocolVersion::V_2025_03_26,

            server_info: Implementation::from_build_env(),
            instructions: Some(
                "Use 'execute_discovered_luau_tool' to run Luau scripts by name (e.g., CreateInstance, RunCode). Also available: run_command (direct Luau string), insert_model.".to_string()
            ),
            capabilities: base_capabilities, // Return the modified base_capabilities
        }
    }
}


#[tool(tool_box)]
impl RBXStudioServer {
    #[tool(description = "Runs a raw Luau command string in Roblox Studio.")]

    async fn run_command(
        &self,
        #[tool(param)] #[schemars(description = "The Luau code to execute.")] command: String,
    ) -> Result<CallToolResult, McpError> {

        self.generic_tool_run(ToolArgumentValues::RunCommand { command }).await

    }

    #[tool(description = "Inserts a model from the Roblox marketplace into the workspace.")]
    async fn insert_model(
        &self,
        #[tool(param)] #[schemars(description = "Query to search for the model.")] query: String,
    ) -> Result<CallToolResult, McpError> {
        self.generic_tool_run(ToolArgumentValues::InsertModel { query }).await
    }

    #[tool(description = "Executes a specific Luau tool script by its name with given arguments.")]
    async fn execute_discovered_luau_tool(
        &self,
        #[tool(param)] #[schemars(description = "Name of the Luau tool file (without .luau extension) to execute.")] tool_name: String,
        #[tool(param)] #[schemars(description = "A JSON string representing arguments for the Luau tool.")] tool_arguments_str: String,
    ) -> Result<CallToolResult, McpError> {
        info!(target: "mcp_server::execute_luau", tool_name = %tool_name, args_json = %tool_arguments_str, "Executing Luau tool by name");
        let app_state = self.state.lock().await;
        if !app_state.discovered_luau_tools.contains_key(&tool_name) {
            warn!("Attempted to execute unknown Luau tool: {}", tool_name);
            return Ok(CallToolResult::error(vec![Content::text(format!("Luau tool '{}' not found by server.", tool_name))]));
        }
        if let Some(discovered_tool_info) = app_state.discovered_luau_tools.get(&tool_name) {
            info!(target: "mcp_server::execute_luau", tool_name = %tool_name, script_path = ?discovered_tool_info.file_path, "Found Luau script path");
        }

        self.generic_tool_run(ToolArgumentValues::ExecuteLuauByName {
            tool_name,
            arguments_json: tool_arguments_str,
        }).await
    }
}

pub async fn response_handler(
     State(state): State<PackedState>,
     Json(payload): Json<RunCommandResponse>,
 ) -> Result<impl IntoResponse, StatusCode> {
     debug!("Received reply from studio plugin: {:?}", payload);
     let mut app_state = state.lock().await;
     if let Some(tx) = app_state.output_map.remove(&payload.id) {

         if let Err(_e) = tx.send(Ok(payload.response)) { // Plugin sends string, which could be success JSON or error JSON

             error!("Failed to send plugin response to internal channel for id: {}", payload.id);
         }
     } else {
         warn!("Received response for unknown or already handled id: {}", payload.id);
     }
     Ok(StatusCode::OK)
 }

 pub async fn request_handler(State(state): State<PackedState>) -> Result<impl IntoResponse, StatusCode> {
     let timeout_result = tokio::time::timeout(LONG_POLL_DURATION, async {
         loop {
             let mut waiter = {
                 let mut app_state_locked = state.lock().await;
                 if let Some(task_with_id) = app_state_locked.process_queue.pop_front() {
                     return Ok::<_, McpError>(Json(task_with_id));
                 }
                 app_state_locked.waiter.clone()
             };
             if waiter.changed().await.is_err() {
                 error!("Waiter channel closed, MCP server might be shutting down.");

                 return Err(McpError::internal_error("Server shutting down, poll aborted.".to_string(), None));
             }
         }
     }).await;

     match timeout_result {
         Ok(Ok(json_response)) => Ok(json_response.into_response()),
         Ok(Err(mcp_err)) => {
             warn!("Request handler loop error: {:?}", mcp_err);
             Ok((StatusCode::INTERNAL_SERVER_ERROR, format!("Server error: {}", mcp_err.message)).into_response())
         }
         Err(_timeout_err) => {
             Ok((StatusCode::NO_CONTENT).into_response())
         }
     }
 }

 pub async fn proxy_handler(
     State(state): State<PackedState>,
     Json(command_with_id): Json<ToolArguments>,
 ) -> Result<impl IntoResponse, StatusCode> {
     let id = command_with_id.id.ok_or_else(|| {
         error!("Proxy command received with no ID: {:?}", command_with_id.args);
         StatusCode::BAD_REQUEST
     })?;
     debug!("Received request to proxy: {:?} for ID: {}", command_with_id.args, id);
     let (tx, mut rx) = mpsc::unbounded_channel();
     {
         let mut app_state = state.lock().await;
         app_state.process_queue.push_back(command_with_id);
         app_state.output_map.insert(id, tx);
         _ = app_state.trigger.send(());
     }


     match tokio::time::timeout(LONG_POLL_DURATION + Duration::from_secs(5), rx.recv()).await {
         Ok(Some(Ok(response_str))) => {
             Ok(Json(RunCommandResponse { response: response_str, id }).into_response())
         }
         Ok(Some(Err(mcp_err))) => {
             error!("Error proxied from tool execution for id {}: {:?}", id, mcp_err);

             Ok((StatusCode::INTERNAL_SERVER_ERROR, format!("Proxied error: {}", mcp_err.message)).into_response())

         }
         Ok(None) => {
             error!("Proxy: Response channel closed for id {}", id);
             Err(StatusCode::INTERNAL_SERVER_ERROR)
         }
         Err(_timeout_err) => {
             error!("Proxy: Timeout waiting for response for id {}", id);
             state.lock().await.output_map.remove(&id);
             Err(StatusCode::GATEWAY_TIMEOUT)
         }
     }
 }

 pub async fn dud_proxy_loop(state: PackedState, mut exit_rx: Receiver<()>) {
     let client = reqwest::Client::new();
     info!("Dud proxy loop started. Polling for tasks to send to actual HTTP plugin endpoint.");

     loop {

         let task_to_proxy = tokio::select! {
            biased; // Process exit signal with higher priority
            _ = &mut exit_rx => {
                info!("Dud proxy loop received exit signal.");
                None // Will break the loop
            }
            // Wait for a new task to be available, or for the exit signal
            res = async {
                let mut waiter = state.lock().await.waiter.clone();
                waiter.changed().await.map_err(|e| {
                    error!("Dud proxy: Waiter channel closed. Error: {:?}", e);
                    e
                })
            } => {
                if res.is_err() {
                    None // Break the loop if channel closed
                } else {
                    let mut app_state_locked = state.lock().await;
                    app_state_locked.process_queue.pop_front()
                }
            }
        };

        if let Some(ref task_with_id) = task_to_proxy {
            let task_id = task_with_id.id.expect("Task in queue should have an ID for proxy");
            info!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, args = ?task_with_id.args, "Popped task from process_queue");
            debug!("Dud proxy: Sending task {:?} (ID: {}) to /proxy endpoint", task_with_id.args, task_id);

            let request_url = format!("http://127.0.0.1:{}/proxy", STUDIO_PLUGIN_PORT);
            info!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, url = %request_url, payload_args = ?task_with_id.args, "Sending HTTP POST to plugin");
            let res = client
                .post(request_url)
                .json(&task_with_id)
                .send()
                .await;

            match res {
                Ok(response) => {
                    let response_status_for_log = response.status();
                    info!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, status = %response_status_for_log, "Received HTTP response from plugin");
                    // Read text first for logging in case JSON parsing fails
                    let response_text_for_logging = match response.text().await {
                        Ok(text) => text,
                        Err(_) => "[Could not read response text]".to_string(),
                    };

                    if response_status.is_success() {
                        match rmcp::serde_json::from_str::<RunCommandResponse>(&response_text_for_logging) {
                            Ok(run_command_response) => {
                                if let Some(tx) = state.lock().await.output_map.remove(&task_id) {
                                    info!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, "Sending successful decoded response to internal channel");
                                    if tx.send(Ok(run_command_response.response)).is_err() {
                                        error!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, "Failed to send proxied response to internal channel for id (channel closed or full)");
                                    } else {
                                        debug!("Dud proxy: Successfully forwarded response for task ID: {}", task_id);
                                    }
                                } else {
                                    warn!("Dud proxy: No sender found in output_map for proxied task ID: {}", task_id);
                                }
                            }
                            Err(e) => {
                                error!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, error = ?e, status = %response_status_for_log, body = %response_text_for_logging, "Failed to decode RunCommandResponse from /proxy endpoint");
                                if let Some(tx) = state.lock().await.output_map.remove(&task_id) {
                                    info!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, "Sending decoding error to internal channel");
                                    _ = tx.send(Err(McpError::internal_error(format!("Dud proxy failed to decode response: {}", e), None)));
                                }
                            }
                        }
                    } else {
                        error!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, status = %response_status_for_log, body = %response_text_for_logging, "Request to /proxy endpoint failed");
                        if let Some(tx) = state.lock().await.output_map.remove(&task_id) {
                             _ = tx.send(Err(McpError::internal_error(format!("Dud proxy failed with status {}", response_status_for_log), None)));
                        }
                    }
                }
                Err(e) => {
                    error!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, error = ?e, "Failed to send HTTP request to /proxy endpoint");
                    if let Some(tx) = state.lock().await.output_map.remove(&task_id) {
                       info!(target: "mcp_server::dud_proxy_loop", task_id = %task_id, "Sending HTTP request error to internal channel");
                       _ = tx.send(Err(McpError::internal_error(format!("Dud proxy failed to send request: {}",e ), None)));
                    }
                }
            }
        } else {
            // task_to_proxy is None, meaning either exit signal or waiter error from select!
            info!("Dud proxy loop: No task obtained from select (possibly exit signal or waiter error). Exiting.");
            break; // Exit the loop
        }
        // Sleep only if a task was processed and loop is not breaking
        if task_to_proxy.is_some() {
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
     }
     info!("Dud proxy loop finished.");
 }
