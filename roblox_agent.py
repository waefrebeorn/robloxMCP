import asyncio
import json
import os
import uuid
import logging
import sys
import re
from collections import deque
from pathlib import Path
from typing import Any, Coroutine, Callable, Dict, List

from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import FunctionCall, Tool, Part, ToolOutput
from google.generativeai.protos import GenerationConfig

# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL_NAME = 'gemini-1.5-flash-latest' # Or 'gemini-1.5-pro-latest'

# Use pathlib for robust, cross-platform path handling
ROOT_DIR = Path(__file__).parent
RBX_MCP_SERVER_PATH = ROOT_DIR / "target" / "release" / "rbx-studio-mcp"

# --- Console Output Formatting ---

class ConsoleFormatter:
    """Utility for printing colored text to the console."""
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def print_user(text: str):
        print(f"{ConsoleFormatter.BOLD}{ConsoleFormatter.BLUE}You: {ConsoleFormatter.ENDC}{text}")

    @staticmethod
    def print_gemini(text: str):
        print(f"\n{ConsoleFormatter.BOLD}{ConsoleFormatter.PURPLE}Gemini:{ConsoleFormatter.ENDC} {text}")

    @staticmethod
    def print_thought(text: str):
        print(f"{ConsoleFormatter.YELLOW}{text}{ConsoleFormatter.ENDC}")

    @staticmethod
    def print_tool_call(tool_name: str, args: dict):
        args_str = json.dumps(args, indent=2)
        print(f"\n{ConsoleFormatter.CYAN}🤖 Calling tool: {tool_name}\n{args_str}{ConsoleFormatter.ENDC}")

    @staticmethod
    def print_tool_result(result: Any):
        print(f"{ConsoleFormatter.GREEN}✅ Tool Result: {result}{ConsoleFormatter.ENDC}")
        
    @staticmethod
    def print_tool_error(error: Any):
        print(f"{ConsoleFormatter.RED}❌ Tool Error: {error}{ConsoleFormatter.ENDC}")

# --- MCP Tool Definitions for Gemini ---
# CORRECTED: insert_model now takes a `query` string, matching the Luau implementation.
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
    ]
)

# --- MCP Client for Rust Server Communication ---

class MCPClient:
    """Manages asynchronous communication with the Rust MCP server process."""
    def __init__(self, server_path: Path):
        self.server_path = server_path
        self.process: asyncio.subprocess.Process | None = None
        self.pending_requests: Dict[str, asyncio.Future] = {}

    async def start(self) -> None:
        """Launches the MCP server process and starts I/O reader tasks."""
        if not self.server_path.exists():
            raise FileNotFoundError(f"MCP server executable not found at '{self.server_path}'. Please build it with 'cargo build --release'.")

        logger.info(f"Starting MCP server: {self.server_path} --stdio")
        try:
            self.process = await asyncio.create_subprocess_exec(
                str(self.server_path), "--stdio",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            asyncio.create_task(self._read_stdout())
            asyncio.create_task(self._read_stderr())
            logger.info("MCP server subprocess launched.")
            await asyncio.sleep(2) # Give server time to initialize and connect to Studio.
        except Exception as e:
            logger.critical(f"Failed to start MCP server process: {e}")
            raise

    async def stop(self) -> None:
        """Gracefully stops the MCP server process."""
        if self.process and self.process.returncode is None:
            logger.info("Terminating MCP server process...")
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
                logger.info("MCP server process terminated gracefully.")
            except asyncio.TimeoutError:
                logger.warning("MCP server did not terminate gracefully, killing process.")
                self.process.kill()

    def is_alive(self) -> bool:
        """Check if the MCP server process is running."""
        return self.process is not None and self.process.returncode is None

    async def _read_stdout(self) -> None:
        """Reads and processes JSON messages from the server's stdout."""
        while self.is_alive():
            try:
                line_bytes = await self.process.stdout.readline()
                if not line_bytes: break # EOF
                line = line_bytes.decode('utf-8').strip()
                if line:
                    self._process_incoming_message(line)
            except Exception as e:
                logger.error(f"Error reading MCP stdout: {e}", exc_info=True)
                break
        logger.warning("MCP stdout reader task finished.")

    async def _read_stderr(self) -> None:
        """Logs the server's stderr for debugging."""
        while self.is_alive():
            try:
                line_bytes = await self.process.stderr.readline()
                if not line_bytes: break
                logger.warning(f"[MCP STDERR]: {line_bytes.decode('utf-8').strip()}")
            except Exception as e:
                logger.error(f"Error reading MCP stderr: {e}", exc_info=True)
                break
        logger.warning("MCP stderr reader task finished.")

    def _process_incoming_message(self, json_str: str) -> None:
        """Parses a message and resolves the corresponding pending request future."""
        try:
            msg = json.loads(json_str)
            request_id = msg.get("id")
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done():
                    future.set_result(msg)
            else:
                # This could be a notification/event from the server
                logger.info(f"Received unhandled MCP message (event?): {msg}")
        except json.JSONDecodeError:
            logger.warning(f"Skipping malformed JSON from MCP server: '{json_str}'")
        except Exception as e:
            logger.error(f"Unexpected error processing MCP message: {e} - Line: '{json_str}'", exc_info=True)

    async def send_request(self, method: str, params: dict, timeout: float = 60.0) -> dict:
        """Sends a JSON-RPC request to the MCP server and awaits its response."""
        if not self.is_alive():
            raise RuntimeError("MCP server process is not running.")

        request_id = str(uuid.uuid4())
        request_payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        try:
            json_message = json.dumps(request_payload) + "\n"
            self.process.stdin.write(json_message.encode('utf-8'))
            await self.process.stdin.drain()
            logger.info(f"-> Sent MCP request (ID: {request_id}, Method: {method})")
            return await asyncio.wait_for(future, timeout=timeout)
        except (asyncio.TimeoutError, BrokenPipeError) as e:
            logger.error(f"Error communicating with MCP server for request {request_id}: {e}")
            if request_id in self.pending_requests:
                del self.pending_requests[request_id] # Clean up
            raise
            
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
        return True, ""

    async def execute_tool_call(self, function_call: FunctionCall) -> ToolOutput:
        """Executes a single tool call and returns a ToolOutput for Gemini."""
        tool_name = function_call.name
        tool_args = dict(function_call.args)
        
        ConsoleFormatter.print_tool_call(tool_name, tool_args)
        
        is_valid, error_msg = self._validate_args(tool_name, tool_args)
        if not is_valid:
            ConsoleFormatter.print_tool_error(f"Argument validation failed: {error_msg}")
            return ToolOutput(
                tool_name,
                json.dumps({"error": f"Invalid arguments provided by AI: {error_msg}"})
            )

        output_content = {}
        try:
            mcp_response = await self.mcp_client.send_request(tool_name, tool_args)
            if "result" in mcp_response:
                output_content = {"status": "success", "output": mcp_response["result"]}
                ConsoleFormatter.print_tool_result(mcp_response["result"])
            elif "error" in mcp_response:
                error_data = mcp_response["error"]
                output_content = {"status": "error", "details": error_data}
                ConsoleFormatter.print_tool_error(error_data.get('message', str(error_data)))
            else:
                output_content = {"status": "unknown_response", "raw": mcp_response}
                ConsoleFormatter.print_tool_error(f"Unexpected response format: {mcp_response}")
        except asyncio.TimeoutError:
            output_content = {"status": "error", "details": "Request timed out. Roblox Studio may be busy or disconnected."}
            ConsoleFormatter.print_tool_error(output_content["details"])
        except Exception as e:
            output_content = {"status": "error", "details": f"An internal broker error occurred: {e}"}
            ConsoleFormatter.print_tool_error(output_content["details"])
            logger.error(f"Unhandled error executing tool '{tool_name}': {e}", exc_info=True)

        return ToolOutput(tool_name, json.dumps(output_content))

# --- Main Application Logic ---

async def main():
    """Main entry point for the Roblox Studio Gemini Broker."""
    # --- Initialization ---
    if not GEMINI_API_KEY:
        logger.critical("GEMINI_API_KEY environment variable not set. Please create a .env file or set it.")
        return
    genai.configure(api_key=GEMINI_API_KEY)
    
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL_NAME,
        tools=[ROBLOX_MCP_TOOLS],
        system_instruction=(
            "You are an expert AI assistant for Roblox Studio, named Gemini-Roblox-Broker. "
            "Your goal is to help users by using the provided tools to interact with their game development environment. "
            "First, think step-by-step about the user's request. "
            "Then, call the necessary tools with correctly formatted arguments. "
            "If a request is ambiguous, ask clarifying questions. "
            "After a tool is used, summarize the result for the user. "
            "You cannot see the screen or the project explorer, so rely on the tool outputs for information."
        )
    )
    chat = model.start_chat(enable_automatic_function_calling=False) # We will handle calls manually
    mcp_client = MCPClient(RBX_MCP_SERVER_PATH)
    tool_dispatcher = ToolDispatcher(mcp_client)

    try:
        await mcp_client.start()
        
        print("\n--- Roblox Studio Gemini Broker ---")
        print(f"Model: {GEMINI_MODEL_NAME} | MCP Server: {'Running' if mcp_client.is_alive() else 'Failed'}")
        print("Type your commands for Roblox Studio, or 'exit' to quit.")

        # --- Main Chat Loop ---
        while True:
            user_input = await asyncio.to_thread(input, "\n> ")
            if user_input.lower() == 'exit':
                break
            if not user_input.strip():
                continue

            ConsoleFormatter.print_user(user_input)
            
            if not mcp_client.is_alive():
                logger.error("Rust MCP server process is no longer running.")
                print("Broker Error: Connection to Roblox Studio lost. Please restart the application.")
                break

            try:
                # Send prompt to Gemini and get initial response
                response = await chat.send_message_async(user_input)
                
                tool_outputs: List[ToolOutput] = []
                
                # Loop to handle one or more tool calls from Gemini
                while response.candidates[0].content.parts[0].function_call.name:
                    function_calls = response.candidates[0].content.parts
                    
                    # Execute all function calls concurrently
                    tasks = [tool_dispatcher.execute_tool_call(fc) for fc in function_calls]
                    results = await asyncio.gather(*tasks)
                    tool_outputs.extend(results)

                    # Send tool results back to Gemini
                    response = await chat.send_message_async(
                        Part(tool_output=ToolOutput(tool_outputs))
                    )
                
                # Print Gemini's final text response after all tool calls are processed
                if response.text:
                   ConsoleFormatter.print_gemini(response.text)

            except Exception as e:
                logger.error(f"An error occurred during the chat loop: {e}", exc_info=True)
                ConsoleFormatter.print_gemini(f"I encountered an internal error: {e}")

    except FileNotFoundError as e:
        logger.critical(f"Setup Error: {e}")
    except Exception as e:
        logger.critical(f"Critical unhandled exception in main: {e}", exc_info=True)
    finally:
        await mcp_client.stop()
        logger.info("Broker application finished.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Broker interrupted by user (Ctrl+C).")