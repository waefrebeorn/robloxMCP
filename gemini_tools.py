import json
import logging
import asyncio
from typing import Any, Dict, List # Added List for ROBLOX_MCP_TOOLS type hint if needed
from google import genai # I.1
from google.genai import types # I.2

# Assuming these will be in the same directory or PYTHONPATH is set up
from mcp_client import MCPClient, MCPConnectionError
from console_ui import ConsoleFormatter

logger = logging.getLogger(__name__)

# --- MCP Tool Definitions for Gemini ---
# II.1. Rename ROBLOX_MCP_TOOLS to ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE
ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE = types.Tool( # II.1. Main object is types.Tool
    function_declarations=[
        types.FunctionDeclaration( # II.1. Each entry is types.FunctionDeclaration
            name="insert_model",
            description=(
                "Searches the Roblox Creator Store/Marketplace for a model and inserts the top result into the "
                "current Roblox Studio place. Best for general requests like 'add a tree' or 'find a sports car'."
            ),
            parameters=types.Schema( # II.1. parameters is types.Schema
                type=types.Type.OBJECT, # II.1. type="object" becomes types.Type.OBJECT
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="A search query for the model, e.g., 'red brick wall', 'low poly tree', 'sports car'.") # II.1. type="string" becomes types.Type.STRING
                },
                required=["query"]
            )
        ),
        types.FunctionDeclaration(
            name="run_code",
            description=(
                "Executes a string of Luau code directly within Roblox Studio. Use this for complex or custom actions "
                "not covered by other tools. The output from `print()` statements in the code will be returned."
                "Example: `run_code(code='print(workspace.Baseplate.Size)')`"
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "code": types.Schema(type=types.Type.STRING, description="The Luau code to execute. Must be valid Luau syntax.")
                },
                required=["code"]
            )
        ),
        types.FunctionDeclaration(
            name="get_selection",
            description="Returns a list of the names and paths of all instances currently selected in the Roblox Studio editor. Returns an empty list if nothing is selected.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={}) # Empty properties
        ),
        types.FunctionDeclaration(
            name="get_properties",
            description="Retrieves the specified properties of a given instance in the Roblox Studio place.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="The path to the instance, e.g., 'Workspace.Baseplate'."),
                    "properties": types.Schema( # II.1. type="array" becomes types.Type.ARRAY
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING), # II.1. items is types.Schema
                        description="A list of property names to retrieve, e.g., ['Color', 'Size', 'Position']."
                    )
                },
                required=["path", "properties"]
            )
        ),
        types.FunctionDeclaration(
            name="set_properties",
            description="Sets one or more properties of a given instance in Roblox Studio.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="The path to the instance, e.g., 'Workspace.Part'."),
                    "properties": types.Schema( # II.1. properties is a dict of types.Schema
                        type=types.Type.OBJECT, # This inner properties schema is an object itself
                        description="A dictionary of property names and their new values, e.g., {'Color': {'r': 1, 'g': 0, 'b': 0}, 'Anchored': true}."
                        # Note: The new SDK might require a more detailed schema for the 'properties' object values if they are not just primitives.
                        # For now, representing it as a generic object. If specific value types are needed (e.g. all numbers or all strings), this would need further refinement.
                    )
                },
                required=["path", "properties"]
            )
        )
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

    # II.2. Update execute_tool_call
    async def execute_tool_call(self, function_call: types.FunctionCall) -> Dict[str, Any]: # II.2. Input type hint and return type
        """Executes a single tool call and returns a dictionary for the new SDK."""
        tool_name = function_call.name
        # The new SDK's FunctionCall.args is already a dict-like object (Struct)
        # Forcing it to dict for broader compatibility if internal methods expect plain dicts.
        tool_args = dict(function_call.args)

        ConsoleFormatter.print_tool_call(tool_name, tool_args)

        is_valid, error_msg = self._validate_args(tool_name, tool_args)
        if not is_valid:
            ConsoleFormatter.print_tool_error({"validation_error": f"Argument validation failed: {error_msg}"})
            # II.2. Return a dictionary
            return {"name": tool_name, "response": {"error": f"Invalid arguments provided by AI: {error_msg}"}}

        output_content_dict = {} # This will be the value for the 'response' key
        try:
            # MCPClient.send_request will raise MCPConnectionError if connection is down
            mcp_response = await self.mcp_client.send_tool_execution_request(tool_name, tool_args)

            if "result" in mcp_response:
                output_content_dict = {"status": "success", "output": mcp_response["result"]}
                ConsoleFormatter.print_tool_result(mcp_response["result"])
            elif "error" in mcp_response: # Error from the Luau tool execution
                error_data = mcp_response["error"]
                output_content_dict = {"status": "error", "details": error_data}
                ConsoleFormatter.print_tool_error(error_data) # Pass the whole error_data dict
            else: # Unexpected response from MCP server
                output_content_dict = {"status": "unknown_response", "raw": mcp_response}
                ConsoleFormatter.print_tool_error(output_content_dict)
        except MCPConnectionError as e: # Raised by mcp_client.send_request
            logger.error(f"MCP Connection Error during tool '{tool_name}': {e}")
            output_content_dict = {"status": "error", "details": f"MCP Connection Error: {e}"}
            ConsoleFormatter.print_tool_error(output_content_dict) # Show error in console
        except asyncio.TimeoutError: # From mcp_client.send_request (if it re-raises it)
            logger.error(f"Tool call '{tool_name}' timed out.")
            output_content_dict = {"status": "error", "details": "Request to Roblox Studio timed out."}
            ConsoleFormatter.print_tool_error(output_content_dict)
        except Exception as e: # Other unexpected errors
            logger.error(f"Unhandled error executing tool '{tool_name}': {e}", exc_info=True)
            output_content_dict = {"status": "error", "details": f"An internal broker error occurred: {e}"}
            ConsoleFormatter.print_tool_error(output_content_dict)

        # II.2. Return a dictionary
        return {"name": tool_name, "response": output_content_dict}
