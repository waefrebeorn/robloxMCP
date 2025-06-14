import asyncio
import os
import logging
import sys
from pathlib import Path
# Remove List typing if no longer needed for ToolOutput specifically
# from typing import List # For ToolOutput typing

# Third-party imports
from dotenv import load_dotenv
from google import genai # I.1
from google.genai import types # I.2, III.1. types.Part will be used. ToolOutput removed.
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML
from rich.panel import Panel
# console object is now imported from console_ui
# Status is imported where it's used, or can be imported here if preferred globally

# Local module imports
from config_manager import config, DEFAULT_CONFIG, ROOT_DIR
from console_ui import ConsoleFormatter, console
from mcp_client import MCPClient, MCPConnectionError
# III.1. Import ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE
from gemini_tools import ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE, ToolDispatcher


# --- Script Configuration & Constants using loaded config ---
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Logger for this main application file

ENV_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CONFIG_GEMINI_API_KEY = config.get("GEMINI_API_KEY")

if ENV_GEMINI_API_KEY:
    GEMINI_API_KEY = ENV_GEMINI_API_KEY
    logger.info("Using GEMINI_API_KEY from environment variable.")
elif CONFIG_GEMINI_API_KEY and CONFIG_GEMINI_API_KEY != "None" and CONFIG_GEMINI_API_KEY is not None:
    GEMINI_API_KEY = CONFIG_GEMINI_API_KEY
    logger.info("Using GEMINI_API_KEY from config.json.")
else:
    console.print(Panel("[bold red]Error:[/bold red] GEMINI_API_KEY not found in environment variables or config.json. "
                        "Please set it in your .env file (recommended) or in config.json.", title="[red]Config Error[/red]"))
    sys.exit("GEMINI_API_KEY not set.")

GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME") or \
                    config.get("GEMINI_MODEL_NAME") or \
                    DEFAULT_CONFIG["GEMINI_MODEL_NAME"]
logger.info(f"Using Gemini Model: {GEMINI_MODEL_NAME}")

RBX_MCP_SERVER_PATH_STR = config.get("RBX_MCP_SERVER_PATH", DEFAULT_CONFIG["RBX_MCP_SERVER_PATH"])
_rbx_mcp_path = Path(RBX_MCP_SERVER_PATH_STR)
if not _rbx_mcp_path.is_absolute():
    RBX_MCP_SERVER_PATH = (ROOT_DIR / _rbx_mcp_path).resolve()
else:
    RBX_MCP_SERVER_PATH = _rbx_mcp_path
logger.info(f"RBX_MCP_SERVER_PATH set to: {RBX_MCP_SERVER_PATH}")

MCP_MAX_INITIAL_START_ATTEMPTS = config.get("MCP_MAX_INITIAL_START_ATTEMPTS", DEFAULT_CONFIG["MCP_MAX_INITIAL_START_ATTEMPTS"])
MCP_RECONNECT_ATTEMPTS = config.get("MCP_RECONNECT_ATTEMPTS", DEFAULT_CONFIG["MCP_RECONNECT_ATTEMPTS"])

history_file_path_str = config.get("HISTORY_FILE_PATH", DEFAULT_CONFIG["HISTORY_FILE_PATH"])
history_file = Path(history_file_path_str)
try:
    if not history_file.parent.exists():
        history_file.parent.mkdir(parents=True, exist_ok=True)
except Exception as e:
    console.print(Panel(f"[yellow]Warning: Could not create directory for history file '{history_file}': {e}[/yellow]", title="[yellow]File History Warning[/yellow]"))

session = PromptSession(history=FileHistory(str(history_file)))


async def main_loop():
    """Main entry point for the Roblox Studio Gemini Broker."""
    # III.2. Remove genai.configure
    # genai.configure(api_key=GEMINI_API_KEY) # Old SDK

    # III.2. Initialize client and model resource name
    # Set the transport to 'async' for asyncio compatibility
    client = genai.Client(api_key=GEMINI_API_KEY)
    model_resource_name = f"models/{GEMINI_MODEL_NAME}"

    # III.2. Replace GenerativeModel and start_chat
    system_instruction_text = (
        "You are an expert AI assistant for Roblox Studio, named Gemini-Roblox-Broker. "
        "Your goal is to help users by using the provided tools to interact with their game development environment. "
        "First, think step-by-step about the user's request. "
        "Then, call the necessary tools with correctly formatted arguments. "
        "If a request is ambiguous, ask clarifying questions. "
        "After a tool is used, summarize the result for the user. "
        "You cannot see the screen or the project explorer, so rely on the tool outputs for information."
    )
    # Create chat session using client.aio.chats.create
    chat_session = await client.chats.create( # III.2. Rename chat to chat_session
        model=model_resource_name,
        history=[
            types.Content(role="user", parts=[types.Part(text=system_instruction_text)]),
            types.Content(role="model", parts=[types.Part(text="Understood. I will act as an expert AI assistant for Roblox Studio.")])
        ]
    )

    mcp_client = MCPClient(
        RBX_MCP_SERVER_PATH,
        max_initial_start_attempts=MCP_MAX_INITIAL_START_ATTEMPTS,
        reconnect_attempts=MCP_RECONNECT_ATTEMPTS
    )
    tool_dispatcher = ToolDispatcher(mcp_client)
    mcp_client_instance = None # To store the mcp_client for finally block

    try:
        mcp_client_instance = mcp_client # Assign for finally block
        from rich.status import Status # Import here
        with console.status("[bold green]Starting MCP Server...", spinner="dots") as status_spinner_mcp:
            await mcp_client.start()

        console.print(Panel("[bold green]Roblox Studio Gemini Broker Initialized[/bold green]",
                            title="[white]System Status[/white]",
                            subtitle=f"Model: {GEMINI_MODEL_NAME} | MCP Server: {'[bold green]Running[/bold green]' if mcp_client.is_alive() else '[bold red]Failed[/bold red]'}"))
        if not mcp_client.is_alive():
            console.print(Panel("[bold red]MCP Server failed to start. Please check the logs and try restarting the broker.[/bold red]", title="[red]Critical Error[/red]"))
            return

        console.print("Type your commands for Roblox Studio, or 'exit' to quit.", style="dim")

        while True:
            if not mcp_client.is_alive():
                console.print(Panel("[bold yellow]Connection to Roblox Studio lost. Attempting to reconnect...[/bold yellow]", title="[yellow]Connection Issue[/yellow]"))
                with console.status("[bold yellow]Reconnecting to MCP server...", spinner="dots") as status_spinner:
                    if await mcp_client.reconnect():
                        status_spinner.update("[bold green]Reconnected successfully![/bold green]")
                        console.print(Panel("[bold green]Successfully reconnected to Roblox Studio.[/bold green]", title="[green]Connection Restored[/green]"))
                    else:
                        status_spinner.update("[bold red]Failed to reconnect.[/bold red]")
                        console.print(Panel("[bold red]Failed to reconnect to Roblox Studio after multiple attempts. Please restart Roblox Studio and the broker.[/bold red]", title="[red]Connection Failed[/red]"))
                        break

            user_input_str = ""
            try:
                prompt_text = HTML('<ansiblue bold>You: </ansiblue>')
                user_input_str = await asyncio.to_thread(session.prompt, prompt_text, reserve_space_for_menu=0)
            except KeyboardInterrupt:
                console.print("\n[bold yellow]Exiting broker...[/bold yellow]")
                break
            except EOFError:
                console.print("\n[bold yellow]Exiting broker (EOF)...[/bold yellow]")
                break

            if user_input_str.lower() == 'exit':
                console.print("[bold yellow]Exiting broker...[/bold yellow]")
                break
            if not user_input_str.strip():
                continue

            try:
                # III.3. New message sending and tool response loop
                # Send initial user message
                with console.status("[bold green]Gemini is thinking...", spinner="dots") as status_spinner_gemini:
                    response = await chat_session.send_message_async( # III.2. Use chat_session
                        content=user_input_str,
                        tools=[ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE] # Use new tool instance
                    )

                # Inner loop for handling a sequence of function calls
                while True:
                    pending_function_calls = []
                    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                                pending_function_calls.append(part.function_call)

                    if not pending_function_calls:
                        break # No more function calls from the model, exit inner loop

                    # Execute all function calls
                    tool_tasks = []
                    for fc_to_execute in pending_function_calls:
                        # Original status message was here, now handled by print_tool_call in ToolDispatcher
                        tool_tasks.append(tool_dispatcher.execute_tool_call(fc_to_execute))

                    tool_call_results = await asyncio.gather(*tool_tasks) # This is now a list of dicts

                    # Prepare parts for sending back to the model
                    tool_response_parts = []
                    for result_dict in tool_call_results: # result_dict is like {'name': ..., 'response': ...}
                        tool_response_parts.append(
                            types.Part(function_response=types.FunctionResponse( # Use types.FunctionResponse
                                name=result_dict['name'],
                                response=result_dict['response'] # This is already a dict from ToolDispatcher
                            ))
                        )

                    # Send tool responses back to the model
                    if tool_response_parts:
                        with console.status("[bold green]Gemini is processing tool results...", spinner="dots") as status_spinner_gemini_processing:
                            response = await chat_session.send_message_async( # III.2. Use chat_session
                                content=tool_response_parts, # Send list of Part objects
                                tools=[ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE] # Use new tool instance
                            )
                    else:
                        logger.warning("No tool response parts to send, though function calls were expected.")
                        break
                # End of inner while loop for function calls
                # 'response' now holds the final model response after any tool interactions

                # III.4. Accessing Final Text Response
                if response.text:
                    ConsoleFormatter.print_gemini_header()
                    # The new SDK's response.text might be streamed differently or need different handling
                    # For now, assume it's a simple string or compatible.
                    # If it's an async iterator, this would need to change:
                    # async for chunk in response.text_stream: # Example if it were a stream
                    #    ConsoleFormatter.print_gemini_chunk(chunk)
                    # For now, treating response.text as directly printable characters.
                    for char_chunk in response.text: # Assuming response.text is iterable string
                         ConsoleFormatter.print_gemini_chunk(char_chunk)
                    console.print()
                elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    # III.4. Updated text reconstruction
                    text_content = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text') and part.text)
                    if text_content:
                        ConsoleFormatter.print_gemini_header()
                        for char_chunk in text_content: # Assuming text_content is iterable string
                            ConsoleFormatter.print_gemini_chunk(char_chunk)
                        console.print()
                    else:
                        ConsoleFormatter.print_gemini("(No text content found in final response parts)")
                else:
                    ConsoleFormatter.print_gemini("(No text response or recognizable content)")

            except MCPConnectionError as e:
                logger.warning(f"MCP Connection Error in main loop: {e}")
                console.print(Panel(f"[yellow]Connection issue: {e}. Will attempt to reconnect.[/yellow]", title="[yellow]MCP Warning[/yellow]"))
                await asyncio.sleep(1)
            except asyncio.TimeoutError:
                logger.error("A request to Gemini or a tool timed out.")
                console.print(Panel("[bold red]A request timed out. Please try again.[/bold red]", title="[red]Timeout Error[/red]"))
            except Exception as e:
                logger.error(f"An error occurred during the chat loop: {e}", exc_info=True)
                # Check if the error is from the genai library and has specific message attributes
                if hasattr(e, 'message') and isinstance(e.message, str):
                    ConsoleFormatter.print_gemini(f"I encountered an internal error: {e.message}")
                else:
                    ConsoleFormatter.print_gemini(f"I encountered an internal error: {str(e)}")


    except FileNotFoundError as e:
        logger.critical(f"Setup Error: {e}")
        console.print(Panel(f"[bold red]Setup Error:[/bold red] {e}. Ensure rbx-studio-mcp executable is built and accessible.", title="[red]Critical Error[/red]"))
    except MCPConnectionError as e:
        logger.critical(f"MCP Critical Connection Error on startup: {e}")
        console.print(Panel(f"[bold red]MCP Critical Connection Error:[/bold red] {e}. Could not connect to Roblox Studio.", title="[red]Critical Error[/red]"))
    except Exception as e:
        logger.critical(f"Critical unhandled exception in main: {e}", exc_info=True)
        console.print(Panel(f"[bold red]Critical unhandled exception:[/bold red] {e}", title="[red]Critical Error[/red]"))
    finally:
        # Use mcp_client_instance which is assigned after mcp_client is defined.
        if 'mcp_client_instance' in locals() and mcp_client_instance and mcp_client_instance.is_alive():
            console.print("[bold yellow]Shutting down MCP server...[/bold yellow]")
            await mcp_client_instance.stop() # Use the instance from the try block
        logger.info("Broker application finished.")
        console.print("[bold yellow]Broker application finished.[/bold yellow]")

if __name__ == '__main__':
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        console.print("\n[bold red]Broker interrupted by user (Ctrl+C). Exiting...[/bold red]")
        logger.info("Broker interrupted by user (Ctrl+C).")
    except SystemExit as e:
        if str(e) == "GEMINI_API_KEY not set.":
            pass # Already handled by initial check
        else:
            console.print(f"\n[bold red]System exit: {e}[/bold red]")