import json
from typing import Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.json import JSON

# --- Rich Console Initialization ---
console = Console()

class ConsoleFormatter:
    """Utility for printing colored text to the console using Rich."""

    @staticmethod
    def print_user(text: str):
        console.print(Panel(Text(text, style="blue"), title="[bold blue]You[/bold blue]", border_style="blue"))

    @staticmethod
    def print_gemini(text: str): # Used for non-streamed full messages or errors
        console.print(Panel(Text(text, style="purple"), title="[bold purple]Gemini[/bold purple]", border_style="purple"))

    @staticmethod
    def print_gemini_header():
        console.print(Text("Gemini:", style="bold purple"), end=" ") # No panel for streaming start

    @staticmethod
    def print_gemini_chunk(text: str): # For streaming
        console.print(Text(text, style="purple"), end="")

    @staticmethod
    def print_thought(text: str):
        # Thoughts are internal, not printing with Rich for now unless specified
        # If needed, could be: console.print(Panel(Text(text, style="yellow"), title="[bold yellow]Thought[/bold yellow]", border_style="yellow"))
        pass

    @staticmethod
    def print_tool_call(tool_name: str, args: dict):
        args_json = JSON(json.dumps(args)) # Rich JSON formatting
        console.print(Panel(args_json, title=f"[bold cyan]🤖 Tool Call: {tool_name}[/bold cyan]", border_style="cyan"))

    @staticmethod
    def print_tool_result(result: Any):
        try:
            result_json = JSON(json.dumps(result)) # Rich JSON formatting
        except TypeError: # Handle cases where result is not directly JSON serializable (e.g. already a string)
            result_json = Text(str(result))
        console.print(Panel(result_json, title="[bold green]✅ Tool Result[/bold green]", border_style="green"))

    @staticmethod
    def print_tool_error(error: Any):
        try:
            error_json = JSON(json.dumps(error)) # Rich JSON formatting
        except TypeError:
            error_json = Text(str(error))
        console.print(Panel(error_json, title="[bold red]❌ Tool Error[/bold red]", border_style="red"))

# Example usage (for testing this module directly)
if __name__ == '__main__':
    from typing import Any # Required for example usage
    ConsoleFormatter.print_user("This is a test user message.")
    ConsoleFormatter.print_gemini("This is a test Gemini message.")
    ConsoleFormatter.print_gemini_header()
    ConsoleFormatter.print_gemini_chunk("This is a ")
    ConsoleFormatter.print_gemini_chunk("streamed Gemini message.")
    console.print() # for newline
    ConsoleFormatter.print_tool_call("test_tool", {"param1": "value1", "param2": 123})
    ConsoleFormatter.print_tool_result({"status": "success", "data": [1, 2, 3]})
    ConsoleFormatter.print_tool_error({"error_code": 500, "message": "Something went wrong."})
    ConsoleFormatter.print_tool_error("A simple error string.")
