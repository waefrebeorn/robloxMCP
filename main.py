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
MAX_API_RETRIES = 1
INITIAL_RETRY_DELAY_SECONDS = 1
RETRY_BACKOFF_FACTOR = 2

# Local module imports
from config_manager import config, DEFAULT_CONFIG, ROOT_DIR
from console_ui import ConsoleFormatter, console
from mcp_client import MCPClient, MCPConnectionError
# III.1. Import ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE
from gemini_tools import ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE, ToolDispatcher, FunctionCall, get_ollama_tools_json_schema # Added FunctionCall and get_ollama_tools_json_schema

# --- Script Configuration & Constants using loaded config ---
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Logger for this main application file

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Roblox Studio AI Broker")
parser.add_argument(
    "--llm_provider",
    type=str,
    choices=["gemini", "ollama"],
    default=config.get("LLM_PROVIDER", DEFAULT_CONFIG["LLM_PROVIDER"]),
    help="The LLM provider to use (gemini or ollama)."
)
parser.add_argument(
    "--ollama_model",
    type=str,
    default=config.get("OLLAMA_DEFAULT_MODEL", DEFAULT_CONFIG["OLLAMA_DEFAULT_MODEL"]),
    help="The Ollama model to use (if --llm_provider is ollama)."
)
parser.add_argument("--test_command", type=str, help="Execute a single test command and exit.")
parser.add_argument('--test_file', type=str, help='Path to a file containing a list of test commands, one per line.')
args = parser.parse_args()

# --- LLM Configuration ---
LLM_PROVIDER = args.llm_provider
OLLAMA_API_URL = config.get("OLLAMA_API_URL", DEFAULT_CONFIG["OLLAMA_API_URL"])
OLLAMA_MODEL_NAME = args.ollama_model # This now comes from args, falling back to config via argparse default

if LLM_PROVIDER == "gemini":
    ENV_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    CONFIG_GEMINI_API_KEY = config.get("GEMINI_API_KEY")

    if ENV_GEMINI_API_KEY:
        GEMINI_API_KEY = ENV_GEMINI_API_KEY
        logger.info("Using GEMINI_API_KEY from environment variable.")
    elif CONFIG_GEMINI_API_KEY and CONFIG_GEMINI_API_KEY != "None" and CONFIG_GEMINI_API_KEY is not None:
        GEMINI_API_KEY = CONFIG_GEMINI_API_KEY
        logger.info("Using GEMINI_API_KEY from config.json.")
    else:
        console.print(Panel("[bold yellow]Warning:[/bold yellow] GEMINI_API_KEY not found for Gemini provider. Using a dummy key 'DUMMY_KEY'. Gemini calls will likely fail.", title="[yellow]Config Warning[/yellow]"))
        GEMINI_API_KEY = "DUMMY_KEY" # Provide a dummy key

    GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME") or \
                        config.get("GEMINI_MODEL_NAME") or \
                        DEFAULT_CONFIG["GEMINI_MODEL_NAME"]
    logger.info(f"Using Gemini Model: {GEMINI_MODEL_NAME}")
elif LLM_PROVIDER == "ollama":
    logger.info(f"Using Ollama provider with API URL: {OLLAMA_API_URL} and Model: {OLLAMA_MODEL_NAME}")
    # Ollama client will be initialized in main_loop
else:
    logger.error(f"Invalid LLM_PROVIDER: {LLM_PROVIDER}. Exiting.")
    sys.exit(1)


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


async def _process_command(
    user_input_str: str,
    llm_provider: str,
    chat_session, # Can be Gemini chat session or Ollama client
    tool_dispatcher,
    console,
    logger,
    ollama_model_name: str = None, # Only for Ollama
    ollama_history: list = None, # Only for Ollama, stores message history
    gemini_model_resource_name: str = None, # Only for Gemini
    is_test_file_command: bool = False
) -> bool:
    """
    Processes a single command through the selected LLM provider, including tool calls and retries.
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
                if llm_provider == "gemini":
                    if current_retry_attempt > 0:
                        with console.status(f"[bold yellow]Gemini API error. Retrying in {current_delay:.1f}s (Attempt {current_retry_attempt + 1}/{MAX_API_RETRIES})...[/bold yellow]", spinner="dots") as status_spinner_gemini_retry:
                            await asyncio.sleep(current_delay)
                    with console.status(f"[bold green]Gemini is thinking... (Attempt {current_retry_attempt + 1})[/bold green]", spinner="dots") as status_spinner_gemini:
                        response = await chat_session.send_message( # chat_session is the Gemini chat
                            message=user_input_str,
                            config=types.GenerateContentConfig(tools=[ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE])
                        )
                    break # Success
                elif llm_provider == "ollama":
                    # Ollama doesn't have explicit retries in the same way, but we can implement a similar loop
                    if current_retry_attempt > 0:
                        with console.status(f"[bold yellow]Ollama API error. Retrying in {current_delay:.1f}s (Attempt {current_retry_attempt + 1}/{MAX_API_RETRIES})...[/bold yellow]", spinner="dots") as status_spinner_ollama_retry:
                            await asyncio.sleep(current_delay)
                    with console.status(f"[bold green]Ollama is thinking... (Attempt {current_retry_attempt + 1})[/bold green]", spinner="dots") as status_spinner_ollama:
                        # Add user message to history
                        ollama_history.append({'role': 'user', 'content': user_input_str})

                        # Get tools in Ollama format
                        ollama_formatted_tools = get_ollama_tools_json_schema()

                        response = await asyncio.to_thread(
                            chat_session.chat, # chat_session is the Ollama client
                            model=ollama_model_name,
                            messages=ollama_history,
                            tools=ollama_formatted_tools if ollama_formatted_tools else None # Pass tools to Ollama
                        )
                    # Add assistant response to history (even if it's a tool call)
                    if response and response.get('message'):
                        ollama_history.append(response['message'])
                    break # Success for Ollama

            except ServerError as e: # Gemini specific
                if llm_provider == "gemini":
                    logger.warning(f"Gemini API ServerError (Attempt {current_retry_attempt + 1}/{MAX_API_RETRIES}): {e}")
                    current_retry_attempt += 1
                    if current_retry_attempt >= MAX_API_RETRIES:
                        logger.error(f"Max retries reached for Gemini API call. Last error: {e}")
                        ConsoleFormatter.print_provider_error("Gemini", f"I encountered a persistent server error after {MAX_API_RETRIES} attempts: {e.message or str(e)}")
                        command_processed_successfully = False
                        break
                    current_delay *= RETRY_BACKOFF_FACTOR
                else: # Should not happen for Ollama here
                    logger.error(f"Unexpected ServerError with {llm_provider}: {e}", exc_info=True)
                    ConsoleFormatter.print_provider_error(llm_provider, f"An unexpected server error occurred: {str(e)}")
                    command_processed_successfully = False
                    break
            except asyncio.TimeoutError as e:
                logger.warning(f"{llm_provider.capitalize()} API TimeoutError (Attempt {current_retry_attempt + 1}/{MAX_API_RETRIES}): {e}")
                current_retry_attempt += 1
                if current_retry_attempt >= MAX_API_RETRIES:
                    logger.error(f"Max retries reached for {llm_provider.capitalize()} API call due to timeout. Last error: {e}")
                    ConsoleFormatter.print_provider_error(llm_provider, f"The request timed out after {MAX_API_RETRIES} attempts.")
                    command_processed_successfully = False
                    break
                current_delay *= RETRY_BACKOFF_FACTOR
            except Exception as e: # General errors (e.g., ollama connection error)
                logger.error(f"Unexpected error during {llm_provider.capitalize()} API call (Attempt {current_retry_attempt + 1}): {e}", exc_info=True)
                error_message = str(e)
                if llm_provider == "ollama" and "Connection refused" in error_message:
                     ConsoleFormatter.print_provider_error(llm_provider, f"Could not connect to Ollama at {OLLAMA_API_URL}. Ensure Ollama is running.")
                else:
                    ConsoleFormatter.print_provider_error(llm_provider, f"I encountered an unexpected error: {error_message}")
                command_processed_successfully = False
                break # Break from retry loop

        if response is None: # Failed to get initial response
            if is_test_file_command:
                 console.print(f"[bold red]Skipping processing for command '{user_input_str}' due to API failure with {llm_provider}.[/bold red]")
            return False # Indicate critical failure

        # Inner loop for handling a sequence of function calls
        while True: # Loop for iterative tool calls
            pending_function_calls = []
            if llm_provider == "gemini":
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                            pending_function_calls.append(part.function_call)
            elif llm_provider == "ollama":
                if response and response.get('message') and response['message'].get('tool_calls'):
                    for ollama_tc in response['message']['tool_calls']:
                        # Adapt Ollama tool call to Gemini's FunctionCall like structure for ToolDispatcher
                        # This assumes Ollama's tool call has 'name' and 'arguments' (or similar)
                        # Example: ollama_tc might be {'function': {'name': 'tool_name', 'arguments': {...}}}
                        if ollama_tc.get('function') and ollama_tc['function'].get('name'):
                            fc_name = ollama_tc['function']['name']
                            fc_args = ollama_tc['function'].get('arguments', {})
                            pending_function_calls.append(FunctionCall(name=fc_name, args=fc_args))
                        else:
                            logger.warning(f"Ollama tool call in unexpected format: {ollama_tc}")


            if not pending_function_calls:
                break # No more function calls from the model, exit inner tool processing loop

            tool_tasks = []
            for fc_to_execute in pending_function_calls:
                # ToolDispatcher expects FunctionCall objects (or dicts that look like them)
                tool_tasks.append(tool_dispatcher.execute_tool_call(fc_to_execute))

            tool_call_results = await asyncio.gather(*tool_tasks) # Results are dicts: {'name': ..., 'response': ...}

            if llm_provider == "gemini":
                tool_response_parts = []
                for result_dict in tool_call_results:
                    tool_response_parts.append(
                        types.Part(function_response=types.FunctionResponse(
                            name=result_dict['name'],
                            response=result_dict['response']
                        ))
                    )
                if not tool_response_parts:
                    logger.warning("No tool response parts to send for Gemini, though function calls were expected.")
                    break # Should not happen if pending_function_calls was not empty

                # Send tool results back to Gemini
                current_retry_attempt_tool = 0
                current_delay_tool = INITIAL_RETRY_DELAY_SECONDS
                response_tool_call = None
                while current_retry_attempt_tool < MAX_API_RETRIES:
                    try:
                        if current_retry_attempt_tool > 0:
                            with console.status(f"[bold yellow]Gemini API error (tool response). Retrying in {current_delay_tool:.1f}s...[/bold yellow]", spinner="dots"):
                                await asyncio.sleep(current_delay_tool)
                        with console.status(f"[bold green]Gemini is processing tool results...[/bold green]", spinner="dots"):
                            response_tool_call = await chat_session.send_message(
                                message=tool_response_parts,
                                config=types.GenerateContentConfig(tools=[ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE])
                            )
                        break # Success
                    except ServerError as e:
                        logger.warning(f"Gemini API ServerError (tool response) (Attempt {current_retry_attempt_tool + 1}/{MAX_API_RETRIES}): {e}")
                        # ... (rest of Gemini retry logic for tool response)
                        current_retry_attempt_tool += 1
                        if current_retry_attempt_tool >= MAX_API_RETRIES:
                            ConsoleFormatter.print_provider_error("Gemini", f"Max retries sending tool results: {e.message or str(e)}")
                            command_processed_successfully = False; break
                        current_delay_tool *= RETRY_BACKOFF_FACTOR
                    except asyncio.TimeoutError as e:
                        logger.warning(f"Gemini API TimeoutError (tool response) (Attempt {current_retry_attempt_tool + 1}/{MAX_API_RETRIES}): {e}")
                        current_retry_attempt_tool += 1
                        if current_retry_attempt_tool >= MAX_API_RETRIES:
                            ConsoleFormatter.print_provider_error("Gemini", f"Timeout sending tool results after {MAX_API_RETRIES} attempts.")
                            command_processed_successfully = False; break
                        current_delay_tool *= RETRY_BACKOFF_FACTOR
                    except Exception as e:
                        logger.error(f"Unexpected error Gemini API (tool response) (Attempt {current_retry_attempt_tool + 1}): {e}", exc_info=True)
                        ConsoleFormatter.print_provider_error("Gemini", f"Unexpected error sending tool results: {str(e)}")
                        command_processed_successfully = False; break
                response = response_tool_call # Update main response with Gemini's reply after tool call

            elif llm_provider == "ollama":
                # Send tool results back to Ollama
                # Ollama expects tool results in a specific format in the messages list
                for result_dict in tool_call_results:
                    # Find the original tool call ID if Ollama provides one and requires it for the response.
                    # This part is highly dependent on how Ollama handles tool call IDs.
                    # For now, assuming a simple list of tool results.
                    # The 'response' from tool_dispatcher is already a dict, convert to string if needed by Ollama.
                    ollama_history.append({
                        'role': 'tool',
                        'content': json.dumps(result_dict['response']), # Ensure content is serializable (e.g. JSON string)
                        'name': result_dict['name'] # Or however Ollama expects to map results to calls
                    })

                current_retry_attempt_tool = 0
                current_delay_tool = INITIAL_RETRY_DELAY_SECONDS
                response_tool_call = None
                while current_retry_attempt_tool < MAX_API_RETRIES: # Retry loop for Ollama after tool call
                    try:
                        if current_retry_attempt_tool > 0:
                            with console.status(f"[bold yellow]Ollama API error (tool response). Retrying in {current_delay_tool:.1f}s...[/bold yellow]", spinner="dots"):
                                await asyncio.sleep(current_delay_tool)
                        with console.status(f"[bold green]Ollama is processing tool results...[/bold green]", spinner="dots"):
                            response_tool_call = await asyncio.to_thread(
                                chat_session.chat, # Ollama client
                                model=ollama_model_name,
                            messages=ollama_history,
                            tools=get_ollama_tools_json_schema() if get_ollama_tools_json_schema() else None # Resend tools if needed by Ollama
                            )
                        if response_tool_call and response_tool_call.get('message'):
                             ollama_history.append(response_tool_call['message']) # Add Ollama's new response to history
                        break # Success
                    except asyncio.TimeoutError as e: # Specific Ollama timeout for tool response
                        logger.warning(f"Ollama API TimeoutError (tool response) (Attempt {current_retry_attempt_tool + 1}/{MAX_API_RETRIES}): {e}")
                        current_retry_attempt_tool += 1
                        if current_retry_attempt_tool >= MAX_API_RETRIES:
                             ConsoleFormatter.print_provider_error("Ollama", f"Timeout sending tool results after {MAX_API_RETRIES} attempts.")
                             command_processed_successfully = False; break
                        current_delay_tool *= RETRY_BACKOFF_FACTOR
                    except Exception as e: # Covers connection errors, etc.
                        logger.error(f"Ollama API error (tool response) (Attempt {current_retry_attempt_tool + 1}): {e}", exc_info=True)
                        ConsoleFormatter.print_provider_error("Ollama", f"API error sending tool results: {str(e)}")
                        current_retry_attempt_tool += 1
                        if current_retry_attempt_tool >= MAX_API_RETRIES:
                            command_processed_successfully = False; break
                        current_delay_tool *= RETRY_BACKOFF_FACTOR
                response = response_tool_call # Update main response with Ollama's reply

            if not command_processed_successfully or response is None:
                logger.warning(f"Failed to get valid response from {llm_provider} after tool processing. Breaking from tool loop.")
                return False # Indicate critical failure for the command

        # Print final response from LLM
        if llm_provider == "gemini":
            if response and response.text:
                ConsoleFormatter.print_provider_response_header("Gemini")
                for char_chunk in response.text:
                    ConsoleFormatter.print_provider_response_chunk("Gemini", char_chunk)
                console.print()
            elif response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                text_content = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text') and part.text)
                if text_content:
                    ConsoleFormatter.print_provider_response_header("Gemini")
                    for char_chunk in text_content:
                        ConsoleFormatter.print_provider_response_chunk("Gemini", char_chunk)
                    console.print()
                else:
                    ConsoleFormatter.print_provider_message("Gemini", "(No text content found in final response parts)")
            else:
                ConsoleFormatter.print_provider_message("Gemini", "(No text response or recognizable content from Gemini)")
        elif llm_provider == "ollama":
            if response and response.get('message') and response['message'].get('content'):
                ConsoleFormatter.print_provider_response_header("Ollama")
                # Ollama response is typically not streamed char by char here unless we implement that
                ConsoleFormatter.print_provider_response_chunk("Ollama", response['message']['content'])
                console.print()
            else:
                ConsoleFormatter.print_provider_message("Ollama", "(No text content in final response from Ollama)")

    except MCPConnectionError as e:
        logger.warning(f"MCP Connection Error while processing command '{user_input_str}' with {llm_provider}: {e}")
        console.print(Panel(f"[yellow]Connection issue: {e}. Check MCP server and Roblox Studio.[/yellow]", title="[yellow]MCP Warning[/yellow]"))
        if is_test_file_command:
            command_processed_successfully = False
    except asyncio.TimeoutError: # General timeout for the whole command processing
        logger.error(f"A request to {llm_provider} or a tool timed out for command: {user_input_str}.")
        console.print(Panel(f"[bold red]A request to {llm_provider} or a tool timed out. Please try again.[/bold red]", title="[red]Timeout Error[/red]"))
        command_processed_successfully = False
    except Exception as e:
        logger.error(f"An error occurred during the chat loop for command '{user_input_str}' with {llm_provider}: {e}", exc_info=True)
        error_msg = getattr(e, 'message', str(e))
        ConsoleFormatter.print_provider_error(llm_provider, f"I encountered an internal error: {error_msg}")
        command_processed_successfully = False

    return command_processed_successfully


async def main_loop():
    """Main entry point for the Roblox Studio AI Broker."""

    llm_client = None # Will be Gemini client or Ollama client
    chat_session = None # Gemini's chat session or Ollama's message history list
    gemini_model_resource_name = None # Specific to Gemini

    if LLM_PROVIDER == "gemini":
        try:
            client = genai.Client(api_key=GEMINI_API_KEY) # transport='async' is default for genai.Client
            gemini_model_resource_name = f"models/{GEMINI_MODEL_NAME}"
            llm_client = client # For Gemini, llm_client is the genai.Client itself
            system_instruction_text = (
                "You are an expert AI assistant for Roblox Studio, named Gemini-Roblox-Broker. "
                "Your goal is to help users by using the provided tools to interact with their game development environment. "
                "First, think step-by-step about the user's request. "
                "Then, call the necessary tools with correctly formatted arguments. "
                "If a request is ambiguous, ask clarifying questions. "
                "After a tool is used, summarize the result for the user. "
                "You cannot see the screen or the project explorer, so rely on the tool outputs for information."
            )
            chat_session = llm_client.aio.chats.create( # Gemini chat session
                model=gemini_model_resource_name,
                history=[
                    types.Content(role="user", parts=[types.Part(text=system_instruction_text)]),
                    types.Content(role="model", parts=[types.Part(text="Understood. I will act as an expert AI assistant for Roblox Studio.")])
                ]
            )
            logger.info(f"Gemini client and chat session initialized for model {GEMINI_MODEL_NAME}.")
        except Exception as e:
            logger.critical(f"Failed to initialize Gemini client: {e}", exc_info=True)
            console.print(Panel(f"[bold red]Critical Error:[/bold red] Failed to initialize Gemini: {e}", title="[red]LLM Init Error[/red]"))
            return
    elif LLM_PROVIDER == "ollama":
        try:
            import ollama # Dynamic import
            # Note: ollama.AsyncClient could be used if available and preferred for async operations
            llm_client = ollama.Client(host=OLLAMA_API_URL)
            # Test connection to Ollama by listing local models or a similar lightweight call
            try:
                await asyncio.to_thread(llm_client.list) # Test call
                logger.info(f"Successfully connected to Ollama at {OLLAMA_API_URL}")
            except Exception as e: # Catch connection errors specifically if possible
                logger.error(f"Failed to connect to Ollama at {OLLAMA_API_URL}: {e}")
                console.print(Panel(f"[bold red]Warning:[/bold red] Could not connect to Ollama server at '{OLLAMA_API_URL}'. "
                                    f"Please ensure Ollama is running and accessible. Error: {e}", title="[yellow]Ollama Connection Error[/yellow]"))
                # Decide if you want to exit or proceed with a non-functional Ollama client
                # For now, let's proceed, _process_command will handle failures.

            # Ollama uses a list of messages for history.
            # The system prompt for Ollama might need different formatting or content.
            # For now, using a similar system prompt.
            ollama_system_prompt = (
                "You are an expert AI assistant for Roblox Studio. "
                "Your goal is to help users by using the provided tools to interact with their game development environment. "
                "Think step-by-step. Call tools with correct arguments. Ask clarifying questions if needed. Summarize tool results."
            )
            chat_session = [{'role': 'system', 'content': ollama_system_prompt}] # This is the history for Ollama
            logger.info(f"Ollama client initialized. Target model: {OLLAMA_MODEL_NAME}. System prompt set.")
        except ImportError:
            logger.critical("Ollama provider selected, but 'ollama' library is not installed. Please run: pip install ollama")
            console.print(Panel("[bold red]Critical Error:[/bold red] Ollama library not found. Please install it with `pip install ollama`.", title="[red]Dependency Error[/red]"))
            return
        except Exception as e:
            logger.critical(f"Failed to initialize Ollama client: {e}", exc_info=True)
            console.print(Panel(f"[bold red]Critical Error:[/bold red] Failed to initialize Ollama: {e}", title="[red]LLM Init Error[/red]"))
            return


    mcp_client = MCPClient(
        RBX_MCP_SERVER_PATH,
        max_initial_start_attempts=MCP_MAX_INITIAL_START_ATTEMPTS,
        reconnect_attempts=MCP_RECONNECT_ATTEMPTS
    )
    # ToolDispatcher needs to be compatible with both Gemini's FunctionCall and adapted Ollama tool calls
    tool_dispatcher = ToolDispatcher(mcp_client)
    mcp_client_instance = None

    try:
        mcp_client_instance = mcp_client
        from rich.status import Status # Import here if not already global
        with console.status("[bold green]Starting MCP Server...", spinner="dots") as status_spinner_mcp:
            await mcp_client.start()

        active_model_display = ""
        if LLM_PROVIDER == "gemini":
            active_model_display = f"Gemini Model: {GEMINI_MODEL_NAME}"
        elif LLM_PROVIDER == "ollama":
            active_model_display = f"Ollama Model: {OLLAMA_MODEL_NAME} (via {OLLAMA_API_URL})"

        console.print(Panel(f"[bold green]Roblox Studio AI Broker Initialized ({LLM_PROVIDER.capitalize()})[/bold green]",
                            title="[white]System Status[/white]",
                            subtitle=f"{active_model_display} | MCP Server: {'[bold green]Running[/bold green]' if mcp_client.is_alive() else '[bold red]Failed[/bold red]'}"))

        if not mcp_client.is_alive():
            console.print(Panel("[bold red]MCP Server failed to start. Please check the logs and try restarting the broker.[/bold red]", title="[red]Critical Error[/red]"))
            return

        # args are already parsed globally now
        if args.test_file:
            console.print(f"\n[bold yellow]>>> Test File Mode: '{args.test_file}' ({LLM_PROVIDER.capitalize()}) <<<[/bold yellow]")
            file_command_errors = 0
            file_command_total = 0
            try:
                with open(args.test_file, 'r') as f:
                    commands = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                file_command_total = len(commands)
                console.print(f"[info]Found {file_command_total} commands in the test file.[/info]")

                for i, user_input_str in enumerate(commands):
                    console.print(f"\n[bold cyan]>>> Executing from file ({i+1}/{file_command_total}):[/bold cyan] {user_input_str}")
                    process_args = {
                        "user_input_str": user_input_str,
                        "llm_provider": LLM_PROVIDER,
                        "chat_session": chat_session, # This is Gemini chat or Ollama history list
                        "tool_dispatcher": tool_dispatcher,
                        "console": console,
                        "logger": logger,
                        "is_test_file_command": True
                    }
                    if LLM_PROVIDER == "ollama":
                        process_args["ollama_model_name"] = OLLAMA_MODEL_NAME
                        process_args["ollama_history"] = chat_session # Pass history for ollama
                        process_args["chat_session"] = llm_client # Pass ollama client for ollama
                    elif LLM_PROVIDER == "gemini":
                         process_args["gemini_model_resource_name"] = gemini_model_resource_name


                    if not await _process_command(**process_args):
                        file_command_errors += 1
                    if i < file_command_total - 1:
                        console.print(f"[dim]Waiting for 25 seconds before next command...[/dim]")
                        await asyncio.sleep(25)
                console.print(f"\n[bold {'green' if file_command_errors == 0 else 'red'}]>>> Test file processing complete. {file_command_total - file_command_errors}/{file_command_total} commands succeeded. <<<[/bold {'green' if file_command_errors == 0 else 'red'}]")

            except FileNotFoundError:
                logger.error(f"Test file not found: {args.test_file}")
                console.print(f"[bold red]Error: Test file '{args.test_file}' not found.[/bold red]")
            except Exception as e:
                logger.error(f"Error processing test file '{args.test_file}': {e}", exc_info=True)
                console.print(f"[bold red]An unexpected error occurred while processing the test file: {e}[/bold red]")
            return # Exit after test file processing

        elif args.test_command:
            user_input_str = args.test_command
            console.print(f"\n[bold cyan]>>> Running Test Command ({LLM_PROVIDER.capitalize()}):[/bold cyan] {user_input_str}")
            process_args = {
                "user_input_str": user_input_str,
                "llm_provider": LLM_PROVIDER,
                "chat_session": chat_session, # Gemini chat or Ollama history list
                "tool_dispatcher": tool_dispatcher,
                "console": console,
                "logger": logger,
            }
            if LLM_PROVIDER == "ollama":
                process_args["ollama_model_name"] = OLLAMA_MODEL_NAME
                process_args["ollama_history"] = chat_session # Pass history for ollama
                process_args["chat_session"] = llm_client # Pass ollama client
            elif LLM_PROVIDER == "gemini":
                process_args["gemini_model_resource_name"] = gemini_model_resource_name

            await _process_command(**process_args)
            console.print(f"\n[bold cyan]>>> Test command finished ({LLM_PROVIDER.capitalize()}). Exiting. <<<[/bold cyan]")
            return

        else: # Interactive Mode
            console.print(f"Type your commands for Roblox Studio ({LLM_PROVIDER.capitalize()} backend), or 'exit' to quit.", style="dim")
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
                    prompt_text = HTML(f'<ansiblue><b>You ({LLM_PROVIDER.capitalize()}): </b></ansiblue>')
                    user_input_str = await asyncio.to_thread(session.prompt, prompt_text, reserve_space_for_menu=0)
                except KeyboardInterrupt: console.print("\n[bold yellow]Exiting broker...[/bold yellow]"); break
                except EOFError: console.print("\n[bold yellow]Exiting broker (EOF)...[/bold yellow]"); break

                if user_input_str.lower() == 'exit': console.print("[bold yellow]Exiting broker...[/bold yellow]"); break

                process_args = {
                    "user_input_str": user_input_str,
                    "llm_provider": LLM_PROVIDER,
                    "chat_session": chat_session, # Gemini chat or Ollama history
                    "tool_dispatcher": tool_dispatcher,
                    "console": console,
                    "logger": logger,
                }
                if LLM_PROVIDER == "ollama":
                    process_args["ollama_model_name"] = OLLAMA_MODEL_NAME
                    process_args["ollama_history"] = chat_session # Pass history
                    process_args["chat_session"] = llm_client # Pass ollama client
                elif LLM_PROVIDER == "gemini":
                    process_args["gemini_model_resource_name"] = gemini_model_resource_name

                await _process_command(**process_args)

    except FileNotFoundError as e:
        logger.critical(f"Setup Error - RBX MCP Server path: {e}")
        console.print(Panel(f"[bold red]Setup Error:[/bold red] MCP Server executable not found at '{RBX_MCP_SERVER_PATH}'. Details: {e}. Ensure it is built and accessible.", title="[red]Critical Error[/red]"))
    except MCPConnectionError as e:
        logger.critical(f"MCP Critical Connection Error on startup: {e}")
        console.print(Panel(f"[bold red]MCP Critical Connection Error:[/bold red] {e}. Could not connect to Roblox Studio.", title="[red]Critical Error[/red]"))
    except Exception as e:
        logger.critical(f"Critical unhandled exception in main_loop: {e}", exc_info=True)
        console.print(Panel(f"[bold red]Critical unhandled exception:[/bold red] {e}", title="[red]Critical Error[/red]"))
    finally:
        if mcp_client_instance and mcp_client_instance.is_alive(): # mcp_client_instance should be mcp_client
            console.print("[bold yellow]Shutting down MCP server...[/bold yellow]")
            await mcp_client.stop()
        logger.info(f"Broker application finished (LLM Provider: {LLM_PROVIDER}).")
        console.print(f"[bold yellow]Broker application finished (LLM Provider: {LLM_PROVIDER}).[/bold yellow]")

if __name__ == '__main__':
    # Args are parsed globally now, so main_loop can use them directly.
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        # This might be redundant if the try/except in main_loop's interactive part catches it first.
        console.print("\n[bold red]Broker interrupted by user (Ctrl+C globally). Exiting...[/bold red]")
        logger.info("Broker interrupted by user (Ctrl+C globally).")
    except SystemExit as e:
        # This handles sys.exit calls, e.g., from argument parsing errors or LLM init failures
        if str(e) not in ["0", "1"] and e.code is not None : # Don't print for clean exits like sys.exit(0) or sys.exit(1) without a message
             console.print(f"\n[bold red]System exit: {e}[/bold red]")
        # If sys.exit was called due to GEMINI_API_KEY issue or Ollama import error, it's already logged/printed.