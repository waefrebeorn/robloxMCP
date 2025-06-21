from google.genai import types
from typing import List, Dict, Any

# --- Desktop Tool Definitions for LLMs (Gemini and Ollama Schema Generation) ---

DESKTOP_TOOLS_INSTANCE = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="capture_screen_region",
            description="Captures a specified rectangular region of the primary screen and returns it as an image. The image can then be used as input for other tools that analyze images.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "x": types.Schema(type=types.Type.INTEGER, description="The x-coordinate of the top-left corner of the region."),
                    "y": types.Schema(type=types.Type.INTEGER, description="The y-coordinate of the top-left corner of the region."),
                    "width": types.Schema(type=types.Type.INTEGER, description="The width of the region in pixels."),
                    "height": types.Schema(type=types.Type.INTEGER, description="The height of the region in pixels."),
                    "save_path": types.Schema(type=types.Type.STRING, nullable=True, description="Optional file path to save the captured image for debugging. If None, image is not saved to disk by this tool directly but returned for further processing.")
                },
                required=["x", "y", "width", "height"]
            )
        ),
        types.FunctionDeclaration(
            name="capture_full_screen",
            description="Captures the entire primary screen and returns it as an image. The image can then be used as input for other tools that analyze images.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "save_path": types.Schema(type=types.Type.STRING, nullable=True, description="Optional file path to save the captured image for debugging. If None, image is not saved to disk by this tool directly but returned for further processing.")
                }
            )
        ),
        types.FunctionDeclaration(
            name="get_screen_resolution",
            description="Returns the width and height of the primary screen in pixels.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={})
        ),
        types.FunctionDeclaration(
            name="mouse_move",
            description="Moves the mouse cursor to the specified X, Y coordinates on the screen.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "x": types.Schema(type=types.Type.INTEGER, description="The target x-coordinate."),
                    "y": types.Schema(type=types.Type.INTEGER, description="The target y-coordinate."),
                    "duration": types.Schema(type=types.Type.NUMBER, nullable=True, description="Optional. Time in seconds to spend moving the mouse. Defaults to a short duration (e.g., 0.25s).")
                },
                required=["x", "y"]
            )
        ),
        types.FunctionDeclaration(
            name="mouse_click",
            description="Performs a mouse click at the specified X, Y coordinates, or at the current mouse position if coordinates are not provided.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "x": types.Schema(type=types.Type.INTEGER, nullable=True, description="Optional. The target x-coordinate. If None, clicks at current mouse position."),
                    "y": types.Schema(type=types.Type.INTEGER, nullable=True, description="Optional. The target y-coordinate. If None, clicks at current mouse position."),
                    "button": types.Schema(type=types.Type.STRING, nullable=True, enum=["left", "middle", "right"], description="Optional. Mouse button to click ('left', 'middle', 'right'). Defaults to 'left'."),
                    "clicks": types.Schema(type=types.Type.INTEGER, nullable=True, description="Optional. Number of times to click. Defaults to 1."),
                    "interval": types.Schema(type=types.Type.NUMBER, nullable=True, description="Optional. Time in seconds between clicks if clicks > 1. Defaults to 0.1s.")
                }
                # No required fields, as clicking at current position with defaults is valid.
            )
        ),
        types.FunctionDeclaration(
            name="mouse_drag",
            description="Drags the mouse from a starting X,Y position to an ending X,Y position while holding a mouse button.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "start_x": types.Schema(type=types.Type.INTEGER, description="The x-coordinate of the drag start position."),
                    "start_y": types.Schema(type=types.Type.INTEGER, description="The y-coordinate of the drag start position."),
                    "end_x": types.Schema(type=types.Type.INTEGER, description="The x-coordinate of the drag end position."),
                    "end_y": types.Schema(type=types.Type.INTEGER, description="The y-coordinate of the drag end position."),
                    "duration": types.Schema(type=types.Type.NUMBER, nullable=True, description="Optional. Time in seconds to spend dragging. Defaults to 0.5s."),
                    "button": types.Schema(type=types.Type.STRING, nullable=True, enum=["left", "middle", "right"], description="Optional. Mouse button to hold during drag. Defaults to 'left'.")
                },
                required=["start_x", "start_y", "end_x", "end_y"]
            )
        ),
        types.FunctionDeclaration(
            name="mouse_scroll",
            description="Scrolls the mouse wheel up or down. Can specify scroll location or use current mouse position.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "amount": types.Schema(type=types.Type.INTEGER, description="Number of units to scroll. Positive for up, negative for down."),
                    "x": types.Schema(type=types.Type.INTEGER, nullable=True, description="Optional. X-coordinate for scroll. Defaults to current mouse position."),
                    "y": types.Schema(type=types.Type.INTEGER, nullable=True, description="Optional. Y-coordinate for scroll. Defaults to current mouse position.")
                },
                required=["amount"]
            )
        ),
        types.FunctionDeclaration(
            name="keyboard_type",
            description="Types the provided text using the keyboard, as if typed by a user.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "text": types.Schema(type=types.Type.STRING, description="The text string to type."),
                    "interval": types.Schema(type=types.Type.NUMBER, nullable=True, description="Optional. Time in seconds between pressing each key. Defaults to a small interval (e.g., 0.01s).")
                },
                required=["text"]
            )
        ),
        types.FunctionDeclaration(
            name="keyboard_press_key",
            description="Presses a single special key (e.g., 'enter', 'esc', 'ctrl', 'f1') or a sequence of regular keys.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "key_name": types.Schema(
                        type=types.Type.STRING,
                        description="Name of the key to press (e.g., 'enter', 'a', 'ctrl', 'shift', 'alt', 'left', 'f5'). Can also be a list of characters to press sequentially e.g. 'abc'."
                    )
                },
                required=["key_name"]
            )
        ),
        types.FunctionDeclaration(
            name="keyboard_hotkey",
            description="Presses a combination of keys simultaneously (e.g., Ctrl+C, Alt+F4).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "keys": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="A list of key names to press together. Example: ['ctrl', 'c'] for Ctrl+C."
                    )
                },
                required=["keys"]
            )
        ),
        types.FunctionDeclaration(
            name="analyze_image_with_vision_model",
            description="Sends a previously captured image (identified by a reference ID or using the last captured image) along with a text prompt to a vision model (e.g., Moondream) for analysis, such as OCR or description. The image capture should typically happen in a prior step.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "prompt_text": types.Schema(type=types.Type.STRING, description="The text prompt to guide the vision model's analysis (e.g., 'What text is in this image?', 'Describe this UI element.')."),
                    "image_reference_id": types.Schema(type=types.Type.STRING, nullable=True, description="Optional. A reference ID of a previously captured image to analyze. If not provided, the system may use the last captured image if available.")
                },
                required=["prompt_text"]
            )
        ),
        # Example of a more composite tool that might combine actions:
        types.FunctionDeclaration(
            name="find_text_on_screen_and_click",
            description="Captures the full screen, uses a vision model (OCR) to find the specified text, and then clicks on the center of the found text's bounding box. Returns coordinates if successful, or an error.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "text_to_find": types.Schema(type=types.Type.STRING, description="The text string to search for on the screen."),
                    "click_button": types.Schema(type=types.Type.STRING, nullable=True, enum=["left", "middle", "right"], description="Optional. Mouse button to click if text is found. Defaults to 'left'."),
                    "occurrence": types.Schema(type=types.Type.INTEGER, nullable=True, description="Optional. Which occurrence of the text to click if multiple are found (1-based index). Defaults to 1 (the first one).")
                },
                required=["text_to_find"]
            )
        ),
        # Window Management Tools
        types.FunctionDeclaration(
            name="list_windows",
            description="Lists the titles of all currently open and visible windows. Can be filtered by a search string.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title_filter": types.Schema(type=types.Type.STRING, nullable=True, description="Optional. If provided, only windows whose titles contain this string (case-insensitive) will be returned.")
                }
            )
        ),
        types.FunctionDeclaration(
            name="get_active_window_title",
            description="Returns the title of the currently active (focused) window.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={})
        ),
        types.FunctionDeclaration(
            name="focus_window",
            description="Attempts to focus (activate or bring to foreground) a window identified by its title. Matches exact title first, then substring.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title": types.Schema(type=types.Type.STRING, description="The title of the window to focus (exact or substring).")
                },
                required=["title"]
            )
        ),
        types.FunctionDeclaration(
            name="get_window_geometry",
            description="Returns the position (x, y) and size (width, height) of a window identified by its title. Matches exact title first, then substring.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title": types.Schema(type=types.Type.STRING, description="The title of the window to get geometry for (exact or substring).")
                },
                required=["title"]
            )
        ),
        # File System Tools
        types.FunctionDeclaration(
            name="list_directory",
            description="Lists the contents (files and subdirectories) of a specified directory path.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="The path to the directory to list.")
                },
                required=["path"]
            )
        ),
        types.FunctionDeclaration(
            name="read_text_file",
            description="Reads the content of a specified text file. Content may be truncated if very large or if max_chars is specified.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="The path to the text file to read."),
                    "max_chars": types.Schema(type=types.Type.INTEGER, nullable=True, description="Optional. Maximum number of characters to read from the beginning of the file.")
                },
                required=["path"]
            )
        )
    ]
)

def get_ollama_tools_json_schema() -> List[Dict[str, Any]]:
    """
    Converts Gemini tool declarations from DESKTOP_TOOLS_INSTANCE
    to a JSON schema list compatible with Ollama.
    """
    ollama_tools = []

    gemini_type_to_json_type = {
        types.Type.STRING: "string",
        types.Type.OBJECT: "object",
        types.Type.ARRAY: "array",
        types.Type.NUMBER: "number",
        types.Type.INTEGER: "integer",
        types.Type.BOOLEAN: "boolean",
    }

    def convert_schema(gemini_schema: types.Schema) -> Dict[str, Any]:
        if not gemini_schema:
            return {}

        json_schema = {}
        gemini_type = gemini_schema.type

        if gemini_type in gemini_type_to_json_type:
            json_schema["type"] = gemini_type_to_json_type[gemini_type]
        elif gemini_schema.properties:
            json_schema["type"] = "object"
        else:
            json_schema["type"] = "string" # Default/fallback

        if gemini_schema.description:
            json_schema["description"] = gemini_schema.description

        if gemini_schema.nullable:
            # For JSON schema, optionality is often handled by not being in 'required'.
            # Some systems support "nullable": true, or type: ["type", "null"]
            # We'll add "nullable" for clarity if the target system (Ollama) might use it.
            # Or, adjust based on Ollama's specific schema expectations.
            # For now, let's assume Ollama might handle it by type union or just optionality.
            # To be safe, if nullable is true, make it a union type with "null"
            if json_schema.get("type") and json_schema.get("type") != "object": # Avoid for objects with properties
                json_schema["type"] = [json_schema["type"], "null"]


        if gemini_schema.enum:
            json_schema["enum"] = list(gemini_schema.enum)

        if gemini_type == types.Type.OBJECT and gemini_schema.properties:
            json_schema["properties"] = {
                name: convert_schema(prop_schema)
                for name, prop_schema in gemini_schema.properties.items()
            }
            if gemini_schema.required:
                json_schema["required"] = list(gemini_schema.required)

        elif gemini_type == types.Type.ARRAY and gemini_schema.items:
            json_schema["items"] = convert_schema(gemini_schema.items)

        return json_schema

    if DESKTOP_TOOLS_INSTANCE and DESKTOP_TOOLS_INSTANCE.function_declarations:
        for declaration in DESKTOP_TOOLS_INSTANCE.function_declarations:
            tool_schema = {
                "name": declaration.name,
                "description": declaration.description,
                "parameters": convert_schema(declaration.parameters) if declaration.parameters else {"type": "object", "properties": {}}
            }
            ollama_tools.append({"type": "function", "function": tool_schema})

    return ollama_tools

if __name__ == '__main__':
    # Print the Gemini tool declarations (for inspection)
    # print("--- Gemini Tool Declarations ---")
    # if DESKTOP_TOOLS_INSTANCE and DESKTOP_TOOLS_INSTANCE.function_declarations:
    #     for func_decl in DESKTOP_TOOLS_INSTANCE.function_declarations:
    #         print(f"Name: {func_decl.name}")
    #         print(f"  Description: {func_decl.description}")
    #         if func_decl.parameters:
    #             print(f"  Parameters:")
    #             for param_name, param_schema in func_decl.parameters.properties.items():
    #                 print(f"    {param_name}:")
    #                 print(f"      Type: {param_schema.type}")
    #                 if param_schema.description:
    #                     print(f"      Description: {param_schema.description}")
    #                 if param_schema.nullable:
    #                     print(f"      Nullable: {param_schema.nullable}")
    #                 if param_schema.enum:
    #                     print(f"      Enum: {list(param_schema.enum)}")
    #         print("-" * 20)

    # Print the Ollama JSON schema (for inspection)
    print("\n--- Ollama JSON Schema ---")
    ollama_schema = get_ollama_tools_json_schema()
    import json
    print(json.dumps(ollama_schema, indent=2))

    # Verify a specific tool's schema for nullable properties
    print("\n--- Specific Tool Schema Check (mouse_click) ---")
    for tool in ollama_schema:
        if tool["function"]["name"] == "mouse_click":
            print(json.dumps(tool, indent=2))
            break
