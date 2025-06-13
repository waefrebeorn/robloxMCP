import json
import logging
from typing import Any, Dict, List # Added List for ROBLOX_MCP_TOOLS type hint if needed
from google.generativeai.types import FunctionCall, Tool, Part, ToolOutput

# Assuming these will be in the same directory or PYTHONPATH is set up
from mcp_client import MCPClient, MCPConnectionError
from console_ui import ConsoleFormatter

logger = logging.getLogger(__name__)

# --- MCP Tool Definitions for Gemini ---
ROBLOX_MCP_TOOLS = Tool(
    function_declarations=[
        {
            "name": "insert_model",
            "description": (
                "Searches the Roblox Creator Store/Marketplace for a model and inserts the top result into the "
                "current Roblox Studio place. Best for general requests like 'add a tree' or 'find a sports car'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A search query for the model, e.g., 'red brick wall', 'low poly tree', 'sports car'.",
                    },
                },
                "required": ["query"]
            }
        },
        {
            "name": "run_code",
            "description": (
                "Executes a string of Luau code directly within Roblox Studio. Use this for complex or custom actions "
                "not covered by other tools. The output from `print()` statements in the code will be returned."
                "Example: `run_code(code='print(workspace.Baseplate.Size)')`"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Luau code to execute. Must be valid Luau syntax."
                    }
                },
                "required": ["code"]
            }
        },
        {
            "name": "get_selection",
            "description": "Returns a list of the names and paths of all instances currently selected in the Roblox Studio editor. Returns an empty list if nothing is selected.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "get_properties",
            "description": "Retrieves the specified properties of a given instance in the Roblox Studio place.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the instance, e.g., 'Workspace.Baseplate'."
                    },
                    "properties": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "A list of property names to retrieve, e.g., ['Color', 'Size', 'Position']."
                    }
                },
                "required": ["path", "properties"]
            }
        },
        {
            "name": "set_properties",
            "description": "Sets one or more properties of a given instance in Roblox Studio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the instance, e.g., 'Workspace.Part'."
                    },
                    "properties": {
                        "type": "object",
                        "description": "A dictionary of property names and their new values, e.g., {'Color': {'r': 1, 'g': 0, 'b': 0}, 'Anchored': true}."
                    }
                },
                "required": ["path", "properties"]
            }
        }
    ]
)

# --- Tool Dispatcher ---

class ToolDispatcher:
    """Validates and executes tool calls via the MCPClient."""
    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client

    def _validate_args(self, tool_name: str, args: dict) -> tuple[bool, str]:
        """Performs basic validation on tool arguments."""
        if tool_name == "insert_model":
            query = args.get("query")
            if not isinstance(query, str) or not query.strip():
                return False, "Invalid 'query'. It must be a non-empty string."
        elif tool_name == "run_code":
            code = args.get("code")
            if not isinstance(code, str) or not code.strip():
                return False, "Invalid 'code'. It must be a non-empty string."
        elif tool_name == "get_properties":
            path = args.get("path")
            properties = args.get("properties")
            if not isinstance(path, str) or not path.strip():
                return False, "Invalid 'path'. It must be a non-empty string."
            if not isinstance(properties, list) or not properties: # Ensure properties is a non-empty list
                return False, "Invalid 'properties'. It must be a non-empty list of strings."
            if not all(isinstance(p, str) and p.strip() for p in properties): # Ensure all items are non-empty strings
                return False, "Invalid 'properties'. All items must be non-empty strings."
        elif tool_name == "set_properties":
            path = args.get("path")
            properties_to_set = args.get("properties") # Renamed to avoid conflict with outer scope 'properties'
            if not isinstance(path, str) or not path.strip():
                return False, "Invalid 'path'. It must be a non-empty string."
            if not isinstance(properties_to_set, dict) or not properties_to_set: # Ensure it's a non-empty object
                return False, "Invalid 'properties'. It must be a non-empty object."
        # get_selection has no arguments to validate.
        return True, ""

    async def execute_tool_call(self, function_call: FunctionCall) -> ToolOutput:
        """Executes a single tool call and returns a ToolOutput for Gemini."""
        tool_name = function_call.name
        tool_args = dict(function_call.args) # Make a mutable copy

        ConsoleFormatter.print_tool_call(tool_name, tool_args)

        is_valid, error_msg = self._validate_args(tool_name, tool_args)
        if not is_valid:
            # Using a dictionary for the error detail to be consistent with other error formats
            ConsoleFormatter.print_tool_error({"validation_error": f"Argument validation failed: {error_msg}"})
            return ToolOutput(
                tool_name,
                json.dumps({"error": f"Invalid arguments provided by AI: {error_msg}"})
            )

        output_content = {}
        try:
            # MCPClient.send_request will raise MCPConnectionError if connection is down
            mcp_response = await self.mcp_client.send_request(tool_name, tool_args)

            if "result" in mcp_response:
                output_content = {"status": "success", "output": mcp_response["result"]}
                ConsoleFormatter.print_tool_result(mcp_response["result"])
            elif "error" in mcp_response: # Error from the Luau tool execution
                error_data = mcp_response["error"]
                output_content = {"status": "error", "details": error_data}
                ConsoleFormatter.print_tool_error(error_data) # Pass the whole error_data dict
            else: # Unexpected response from MCP server
                output_content = {"status": "unknown_response", "raw": mcp_response}
                ConsoleFormatter.print_tool_error(output_content)
        except MCPConnectionError as e: # Raised by mcp_client.send_request
            logger.error(f"MCP Connection Error during tool '{tool_name}': {e}")
            output_content = {"status": "error", "details": f"MCP Connection Error: {e}"}
            ConsoleFormatter.print_tool_error(output_content) # Show error in console
            # This error will be passed back to Gemini
        except asyncio.TimeoutError: # From mcp_client.send_request (if it re-raises it)
            logger.error(f"Tool call '{tool_name}' timed out.")
            output_content = {"status": "error", "details": "Request to Roblox Studio timed out."}
            ConsoleFormatter.print_tool_error(output_content)
        except Exception as e: # Other unexpected errors
            logger.error(f"Unhandled error executing tool '{tool_name}': {e}", exc_info=True)
            output_content = {"status": "error", "details": f"An internal broker error occurred: {e}"}
            ConsoleFormatter.print_tool_error(output_content)

        return ToolOutput(tool_name, json.dumps(output_content))
