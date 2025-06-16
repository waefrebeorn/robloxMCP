import asyncio
import os
import logging
import sys
import argparse # Added for command-line arguments
from pathlib import Path
# Remove List typing if no longer needed for ToolOutput specifically
# from typing import List # For ToolOutput typing

# Third-party imports
from dotenv import load_dotenv
from google import genai # I.1
from google.genai import types # I.2, III.1. types.Part will be used. ToolOutput removed.
from google.genai.errors import ServerError
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML
from rich.panel import Panel
# console object is now imported from console_ui
# Status is imported where it's used, or can be imported here if preferred globally

# Retry Parameters for Gemini API
MAX_API_RETRIES = 3
INITIAL_RETRY_DELAY_SECONDS = 1
RETRY_BACKOFF_FACTOR = 2

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
    console.print(Panel("[bold yellow]Warning:[/bold yellow] GEMINI_API_KEY not found. Using a dummy key 'DUMMY_KEY' for testing tool dispatch. Gemini calls will likely fail.", title="[yellow]Config Warning[/yellow]"))
    GEMINI_API_KEY = "DUMMY_KEY" # Provide a dummy key to proceed

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


async def _process_command(user_input_str: str, chat_session, tool_dispatcher, console, logger, is_test_file_command: bool = False) -> bool:
    """
    Processes a single command through the Gemini chat session, including tool calls and retries.
    Returns True if the command processing completed (even with handled errors),
    False if a critical/unrecoverable error occurred (e.g., max API retries).
    """
    if not user_input_str.strip():
        return True # Considered processed, no actual error

    command_processed_successfully = True
    try:
        current_retry_attempt = 0
        current_delay = INITIAL_RETRY_DELAY_SECONDS
        response = None
        while current_retry_attempt < MAX_API_RETRIES:
            try:
                if current_retry_attempt > 0:
                    with console.status(f"[bold yellow]Gemini API error. Retrying in {current_delay:.1f}s (Attempt {current_retry_attempt + 1}/{MAX_API_RETRIES})...[/bold yellow]", spinner="dots") as status_spinner_gemini_retry:
                        await asyncio.sleep(current_delay)
                with console.status(f"[bold green]Gemini is thinking... (Attempt {current_retry_attempt + 1})[/bold green]", spinner="dots") as status_spinner_gemini:
                    response = await chat_session.send_message(
                        message=user_input_str,
                        config=types.GenerateContentConfig(tools=[ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE])
                    )
                break # Success
            except ServerError as e:
                logger.warning(f"Gemini API ServerError (Attempt {current_retry_attempt + 1}/{MAX_API_RETRIES}): {e}")
                current_retry_attempt += 1
                if current_retry_attempt >= MAX_API_RETRIES:
                    logger.error(f"Max retries reached for Gemini API call. Last error: {e}")
                    ConsoleFormatter.print_gemini(f"I encountered a persistent server error after {MAX_API_RETRIES} attempts: {e.message or str(e)}")
                    command_processed_successfully = False
                    break
                current_delay *= RETRY_BACKOFF_FACTOR
            except asyncio.TimeoutError as e:
                logger.warning(f"Gemini API TimeoutError (Attempt {current_retry_attempt + 1}/{MAX_API_RETRIES}): {e}")
                current_retry_attempt += 1
                if current_retry_attempt >= MAX_API_RETRIES:
                    logger.error(f"Max retries reached for Gemini API call due to timeout. Last error: {e}")
                    ConsoleFormatter.print_gemini(f"The request to Gemini timed out after {MAX_API_RETRIES} attempts.")
                    command_processed_successfully = False
                    break
                current_delay *= RETRY_BACKOFF_FACTOR
            except Exception as e:
                logger.error(f"Unexpected error during Gemini API call (Attempt {current_retry_attempt + 1}): {e}", exc_info=True)
                ConsoleFormatter.print_gemini(f"I encountered an unexpected error while trying to reach Gemini: {str(e)}")
                command_processed_successfully = False
                break

        if response is None: # Failed to get initial response
            if is_test_file_command: # Only print this specific message if it's part of a test file sequence
                 console.print(f"[bold red]Skipping processing for command '{user_input_str}' due to API failure.[/bold red]")
            return False # Indicate critical failure

        # Inner loop for handling a sequence of function calls
        while True:
            pending_function_calls = []
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                        pending_function_calls.append(part.function_call)

            if not pending_function_calls:
                break # No more function calls from the model, exit inner loop

            tool_tasks = []
            for fc_to_execute in pending_function_calls:
                tool_tasks.append(tool_dispatcher.execute_tool_call(fc_to_execute))

            tool_call_results = await asyncio.gather(*tool_tasks)

            tool_response_parts = []
            for result_dict in tool_call_results:
                tool_response_parts.append(
                    types.Part(function_response=types.FunctionResponse(
                        name=result_dict['name'],
                        response=result_dict['response']
                    ))
                )

            if tool_response_parts:
                current_retry_attempt_tool = 0
                current_delay_tool = INITIAL_RETRY_DELAY_SECONDS
                response_tool_call = None

                while current_retry_attempt_tool < MAX_API_RETRIES:
                    try:
                        if current_retry_attempt_tool > 0:
                            with console.status(f"[bold yellow]Gemini API error (tool response). Retrying in {current_delay_tool:.1f}s (Attempt {current_retry_attempt_tool + 1}/{MAX_API_RETRIES})...[/bold yellow]", spinner="dots") as status_spinner_gemini_retry_tool:
                                await asyncio.sleep(current_delay_tool)
                        with console.status(f"[bold green]Gemini is processing tool results... (Attempt {current_retry_attempt_tool + 1})[/bold green]", spinner="dots") as status_spinner_gemini_processing:
                            response_tool_call = await chat_session.send_message(
                                message=tool_response_parts,
                                config=types.GenerateContentConfig(tools=[ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE])
                            )
                        break # Success
                    except ServerError as e:
                        logger.warning(f"Gemini API ServerError (tool response) (Attempt {current_retry_attempt_tool + 1}/{MAX_API_RETRIES}): {e}")
                        current_retry_attempt_tool += 1
                        if current_retry_attempt_tool >= MAX_API_RETRIES:
                            logger.error(f"Max retries reached for Gemini API call (tool response). Last error: {e}")
                            ConsoleFormatter.print_gemini(f"I encountered a persistent server error sending tool results after {MAX_API_RETRIES} attempts: {e.message or str(e)}")
                            command_processed_successfully = False
                            break
                        current_delay_tool *= RETRY_BACKOFF_FACTOR
                    except asyncio.TimeoutError as e:
                        logger.warning(f"Gemini API TimeoutError (tool response) (Attempt {current_retry_attempt_tool + 1}/{MAX_API_RETRIES}): {e}")
                        current_retry_attempt_tool += 1
                        if current_retry_attempt_tool >= MAX_API_RETRIES:
                            logger.error(f"Max retries reached for Gemini API call (tool response) due to timeout. Last error: {e}")
                            ConsoleFormatter.print_gemini(f"The request to Gemini for tool results timed out after {MAX_API_RETRIES} attempts.")
                            command_processed_successfully = False
                            break
                        current_delay_tool *= RETRY_BACKOFF_FACTOR
                    except Exception as e:
                        logger.error(f"Unexpected error during Gemini API call (tool response) (Attempt {current_retry_attempt_tool + 1}): {e}", exc_info=True)
                        ConsoleFormatter.print_gemini(f"I encountered an unexpected error sending tool results to Gemini: {str(e)}")
                        command_processed_successfully = False
                        break

                response = response_tool_call
                if response is None: # Failed to get response after tool call
                    logger.warning("Failed to send/receive tool responses to/from Gemini after multiple retries. Breaking from tool processing loop.")
                    return False # Indicate critical failure
            else:
                logger.warning("No tool response parts to send, though function calls were expected.")
                break # Should not happen if pending_function_calls was not empty

        # Print final response from Gemini
        if response and response.text:
            ConsoleFormatter.print_gemini_header()
            for char_chunk in response.text:
                 ConsoleFormatter.print_gemini_chunk(char_chunk)
            console.print()
        elif response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            text_content = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text') and part.text)
            if text_content:
                ConsoleFormatter.print_gemini_header()
                for char_chunk in text_content:
                    ConsoleFormatter.print_gemini_chunk(char_chunk)
                console.print()
            else:
                ConsoleFormatter.print_gemini("(No text content found in final response parts)")
        else:
            ConsoleFormatter.print_gemini("(No text response or recognizable content)")

    except MCPConnectionError as e:
        logger.warning(f"MCP Connection Error while processing command '{user_input_str}': {e}")
        console.print(Panel(f"[yellow]Connection issue: {e}. Check MCP server and Roblox Studio.[/yellow]", title="[yellow]MCP Warning[/yellow]"))
        if is_test_file_command: # For test files, this is a command failure
            command_processed_successfully = False
        # For interactive mode, the main loop's reconnect logic will handle this.
        # For single --test_command, this will also be a failure.
    except asyncio.TimeoutError:
        logger.error(f"A request to Gemini or a tool timed out for command: {user_input_str}.")
        console.print(Panel("[bold red]A request timed out. Please try again.[/bold red]", title="[red]Timeout Error[/red]"))
        command_processed_successfully = False
    except Exception as e:
        logger.error(f"An error occurred during the chat loop for command '{user_input_str}': {e}", exc_info=True)
        if hasattr(e, 'message') and isinstance(e.message, str):
            ConsoleFormatter.print_gemini(f"I encountered an internal error: {e.message}")
        else:
            ConsoleFormatter.print_gemini(f"I encountered an internal error: {str(e)}")
        command_processed_successfully = False

    return command_processed_successfully


async def main_loop():
    """Main entry point for the Roblox Studio Gemini Broker."""
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

    chat_session = client.aio.chats.create( # III.2. Rename chat to chat_session

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

    # genai.configure(api_key=GEMINI_API_KEY) # Old SDK

    # Initialize client and model resource name
    client = genai.Client(api_key=GEMINI_API_KEY)
    model_resource_name = f"models/{GEMINI_MODEL_NAME}"

    system_instruction_text = (
        "You are an expert AI assistant for Roblox Studio, named Gemini-Roblox-Broker. "
        "Your goal is to help users by using the provided tools to interact with their game development environment. "
        "First, think step-by-step about the user's request. "
        "Then, call the necessary tools with correctly formatted arguments. "
        "If a request is ambiguous, ask clarifying questions. "
        "After a tool is used, summarize the result for the user. "
        "You cannot see the screen or the project explorer, so rely on the tool outputs for information."
    )

    chat_session = client.aio.chats.create(
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
    mcp_client_instance = None

    try:
        mcp_client_instance = mcp_client
        from rich.status import Status
        with console.status("[bold green]Starting MCP Server...", spinner="dots") as status_spinner_mcp:
            await mcp_client.start()

        console.print(Panel("[bold green]Roblox Studio Gemini Broker Initialized[/bold green]",
                            title="[white]System Status[/white]",
                            subtitle=f"Model: {GEMINI_MODEL_NAME} | MCP Server: {'[bold green]Running[/bold green]' if mcp_client.is_alive() else '[bold red]Failed[/bold red]'}"))
        if not mcp_client.is_alive():
            console.print(Panel("[bold red]MCP Server failed to start. Please check the logs and try restarting the broker.[/bold red]", title="[red]Critical Error[/red]"))
            return

        parser = argparse.ArgumentParser(description="Roblox Studio Gemini Broker")
        parser.add_argument("--test_command", type=str, help="Execute a single test command and exit.")
        parser.add_argument('--test_file', type=str, help='Path to a file containing a list of test commands, one per line.')
        args = parser.parse_args()

        if args.test_file:
            console.print(f"\n[bold yellow]>>> Test File Mode: '{args.test_file}' <<<[/bold yellow]")
            file_command_errors = 0
            file_command_total = 0
            try:
                with open(args.test_file, 'r') as f:
                    commands = [line.strip() for line in f if line.strip()]

                file_command_total = len(commands)
                console.print(f"[info]Found {file_command_total} commands in the test file.[/info]")

                for i, user_input_str in enumerate(commands):
                    console.print(f"\n[bold cyan]>>> Executing from file ({i+1}/{file_command_total}):[/bold cyan] {user_input_str}")
                    if not await _process_command(user_input_str, chat_session, tool_dispatcher, console, logger, is_test_file_command=True):
                        file_command_errors += 1

                    if i < file_command_total - 1: # Don't sleep after the last command
                        console.print(f"[dim]Waiting for 12 seconds before next command...[/dim]")
                        await asyncio.sleep(12)

                console.print(f"\n[bold {'green' if file_command_errors == 0 else 'red'}]>>> Test file processing complete. {file_command_total - file_command_errors}/{file_command_total} commands succeeded. <<<[/bold {'green' if file_command_errors == 0 else 'red'}]")

            except FileNotFoundError:
                logger.error(f"Test file not found: {args.test_file}")
                console.print(f"[bold red]Error: Test file '{args.test_file}' not found.[/bold red]")
                file_command_errors = 1 # Indicate failure
            except Exception as e:
                logger.error(f"Error processing test file '{args.test_file}': {e}", exc_info=True)
                console.print(f"[bold red]An unexpected error occurred while processing the test file: {e}[/bold red]")
                file_command_errors = file_command_total # Assume all failed if the loop was interrupted

            # Regardless of errors in file processing, we want to ensure this mode exits.
            return # Exit after test file processing

        elif args.test_command:
            user_input_str = args.test_command
            console.print(f"\n[bold cyan]>>> Running Test Command:[/bold cyan] {user_input_str}")
            await _process_command(user_input_str, chat_session, tool_dispatcher, console, logger)
            console.print("\n[bold cyan]>>> Test command finished. Exiting. <<<[/bold cyan]")
            return # Exit after test command

        else: # Interactive Mode
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
                            break # Exit interactive loop if reconnect fails

                user_input_str = ""
                try:
                    prompt_text = HTML('<ansiblue><b>You: </b></ansiblue>')
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

                await _process_command(user_input_str, chat_session, tool_dispatcher, console, logger)

    except FileNotFoundError as e: # This is for rbx-mcp-server executable
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