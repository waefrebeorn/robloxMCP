import json
import logging
import asyncio
from typing import Any, Dict, List # Added List for ROBLOX_MCP_TOOLS type hint if needed
from google import genai # I.1
from google.genai import types # I.2

# --- Data Type Formatting for Gemini ---
# When providing arguments for tools, especially within complex structures like
# the 'properties' dictionary or 'arguments' list, use the following formats:
#
# Vector3: Represents a 3D vector or coordinates.
#   Format: { "x": number, "y": number, "z": number }
#   Example: { "x": 10.5, "y": 20, "z": 5.0 }
#
# Color3: Represents an RGB color. Values for r, g, b should be between 0 and 1.
#   Format: { "r": number, "g": number, "b": number }
#   Example: { "r": 0.0, "g": 0.5, "b": 1.0 } (for a shade of blue)
#
# CFrame: Represents a coordinate frame (position and orientation) in 3D space.
#   Position is a Vector3. Orientation is represented by Euler angles in degrees (XYZ order).
#   Format: { "position": {"x":0, "y":0, "z":0}, "orientation": {"x":0, "y":0, "z":0} }
#   Example: { "position": {"x":10, "y":5, "z":2}, "orientation": {"x":0, "y":90, "z":0} } (90-degree rotation around Y-axis)
#
# Enum: Roblox Enums should be passed as their full string path.
#   Format: "Enum.Material.Plastic"
#   Example: "Enum.Material.Neon", "Enum.KeyCode.Space"
#
# Instance Path: A string representing the hierarchical path to an instance in the game's DataModel.
#   Format: "Workspace.MyModel.MyPart"
#   Example: "Lighting.Atmosphere", "game.Players.LocalPlayer"
#
# UDim2: Represents a 2D dimension with scale and offset for both X and Y axes. Used for GUI Size and Position.
#   Format: { "scale_x": number, "offset_x": number, "scale_y": number, "offset_y": number }
#   Example: { "scale_x": 0.5, "offset_x": 100, "scale_y": 0.1, "offset_y": 5 }
#
# ---

# Assuming these will be in the same directory or PYTHONPATH is set up
from mcp_client import MCPClient, MCPConnectionError
from console_ui import ConsoleFormatter

logger = logging.getLogger(__name__)

# --- MCP Tool Definitions for Gemini ---
# II.1. Rename ROBLOX_MCP_TOOLS to ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE
ROBLOX_MCP_TOOLS_NEW_SDK_INSTANCE = types.Tool(
    function_declarations=[
        # --- Kept Existing Tools ---
        types.FunctionDeclaration(
            name="insert_model",
            description=(
                "Searches the Roblox Creator Store/Marketplace for a model and inserts the top result into the "
                "current Roblox Studio place. Best for general requests like 'add a tree' or 'find a sports car'."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="A search query for the model, e.g., 'red brick wall', 'low poly tree', 'sports car'.")
                },
                required=["query"]
            )
        ),
        types.FunctionDeclaration(
            name="RunCode", # Renamed from run_command to RunCode (maps to RunCode.luau)
            description=(
                "Executes a string of Luau code directly within Roblox Studio, typically in a global context. "
                "Use this for quick tests, simple commands, or actions not tied to a specific script instance. "
                "The output from `print()` statements in the command will be returned. "

                "Example: `RunCode(command='print(workspace.Baseplate.Size)')`" # Example updated

            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "command": types.Schema(type=types.Type.STRING, description="The Luau command to execute. Must be valid Luau syntax.")
                },
                required=["command"]
            )
        ),
        types.FunctionDeclaration(
            name="get_selection",
            description="Returns a list of the full paths of all instances currently selected in the Roblox Studio editor. Returns an empty list if nothing is selected.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={}) # Empty properties
        ),

        # --- Core Instance Manipulation Tools (Phase 1) ---
        types.FunctionDeclaration(
            name="CreateInstance",
            description="Creates any Roblox Instance (e.g., Part, SpotLight, Sound, Script) with initial properties. For Parent, use its string path. For Vector3, use {'x':0,'y':0,'z':0}. For Color3 (0-1 range), use {'r':0,'g':0,'b':0}. For CFrame (position & orientation in degrees), use {'position': vec3_dict, 'orientation': vec3_dict_degrees}. For Enums, use string like 'Enum.Material.Plastic'. For ColorSequence properties (e.g., on ParticleEmitters), provide as `{'start_color':color3_dict, 'end_color':color3_dict}` or full `{'keys': [{'time':t, 'value':color3_dict}, ...]}`. For NumberSequence (e.g., ParticleEmitter.Transparency), use `{'start_value':num, 'end_value':num}` or full `{'keys': [{'time':t, 'value':num}, ...]}`.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "class_name": types.Schema(type=types.Type.STRING, description="Class name of the instance to create (e.g., 'Part', 'SpotLight', 'Script')."),
                    "properties": types.Schema(
                        type=types.Type.OBJECT,
                        description="Dictionary of property names and initial values. E.g., {'Name': 'MyCoolPart', 'Parent': 'Workspace.Model', 'Size': {'x':1,'y':1,'z':1}, 'Color': {'r':1,'g':0,'b':0}}."
                    )
                },
                required=["class_name", "properties"]
            )
        ),
        types.FunctionDeclaration(
            name="set_instance_properties",
            description="Sets multiple properties of an existing Roblox instance. Use defined dictionary structures for complex types like Vector3, Color3 (0-1 range), CFrame (degrees for orientation). Enums as strings. This includes ColorSequence (e.g., `{'start_color':color3_dict, 'end_color':color3_dict}` or full key array) and NumberSequence (e.g., `{'start_value':num, 'end_value':num}` or full key array) properties.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="Path to the instance (e.g., 'Workspace.MyPart')."),
                    "properties": types.Schema(
                        type=types.Type.OBJECT,
                        description="Dictionary of property names and new values. E.g., {'Transparency': 0.5, 'Position': {'x':10,'y':5,'z':0}, 'Material': 'Enum.Material.Metal'}."
                    )
                },
                required=["path", "properties"]
            )
        ),
        types.FunctionDeclaration(

            name="GetInstanceProperties",

            description="Retrieves properties of an existing Roblox instance. If 'property_names' is provided, only those are fetched. Otherwise, many common scriptable properties are returned. Returns a dictionary of property names and their values. Complex types will be returned in their described dictionary/string formats.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="Path to the instance (e.g., 'Workspace.ExistingPart')."),
                    "property_names": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="Optional. List of property names to retrieve (e.g., ['Size', 'Color', 'CFrame', 'Material']). If omitted, common properties are fetched."
                    )
                },
                required=["path"] # property_names is now optional
            )
        ),
        types.FunctionDeclaration(
            name="call_instance_method",
            description="Calls a method on an instance. Arguments for complex types (Vector3, Color3, CFrame, Enums) should use their dictionary or string format. E.g., Humanoid:MoveTo({'x':1,'y':2,'z':3}) or Part:SetNetworkOwner(nil).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="Path to the instance (e.g., 'Workspace.MyPart')."),
                    "method_name": types.Schema(type=types.Type.STRING, description="Name of the method to call (e.g., 'MoveTo', 'Destroy', 'SetNetworkOwner')."),
                    "arguments": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(), # Luau side handles type validation of individual args
                        description="List of arguments for the method. Use defined dict/string formats for complex types. Empty list if no arguments. E.g., [{'x':10,'y':0,'z':5}] for MoveTo, or [nil] for SetNetworkOwner(nil)."
                    )
                },
                required=["path", "method_name", "arguments"]
            )
        ),
        types.FunctionDeclaration(
            name="delete_instance",
            description="Deletes the specified instance from the game.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "path": types.Schema(type=types.Type.STRING, description="Path to the instance to delete (e.g., 'Workspace.ObsoletePart').")
                },
                required=["path"]
            )
        ),
        types.FunctionDeclaration(
            name="SelectInstances",
            description="Sets the current selection in Roblox Studio to the specified instances. Pass an empty list to clear the selection.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "paths": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="A list of paths to the instances to select (e.g., ['Workspace.Part1', 'Workspace.Model.Part2']). Empty list clears selection."
                    )
                },
                required=["paths"]
            )
        ),

        # --- Essential Service Tools (Phase 1) ---
        types.FunctionDeclaration(
            name="run_script",
            description="Creates a new Script or LocalScript, sets its source code, and parents it to the specified instance. Returns the path to the created script or an error.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "parent_path": types.Schema(type=types.Type.STRING, description="Path to the instance where the script will be parented (e.g., 'Workspace.MyPart', 'StarterPlayer.StarterPlayerScripts')."),
                    "script_source": types.Schema(type=types.Type.STRING, description="The Luau source code for the script."),
                    "script_name": types.Schema(type=types.Type.STRING, description="The name for the new script instance (e.g., 'MyLogicScript')."),
                    "script_type": types.Schema(type=types.Type.STRING, enum=["Script", "LocalScript"], description="Type of script to create: 'Script' or 'LocalScript'.")
                },
                required=["parent_path", "script_source", "script_name", "script_type"]
            )
        ),
        types.FunctionDeclaration(
            name="set_lighting_property",
            description="Sets a property of the Lighting service. Use dictionary format for Color3 (0-1 range), Vector3. E.g., set 'Ambient' to {'r':0.1,'g':0.1,'b':0.1}.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "property_name": types.Schema(type=types.Type.STRING, description="Name of the Lighting service property (e.g., 'Ambient', 'Brightness', 'ClockTime', 'Technology')."),
                    "value": types.Schema(type=types.Type.STRING, description="New value for the property. Use dicts for Color3/Vector3, string for Enums. Value will be parsed by Luau.")
                },
                required=["property_name", "value"]
            )
        ),
        types.FunctionDeclaration(
            name="GetLightingProperty",
            description="Gets a property of the Lighting service. Returns value in its appropriate dict/string/primitive format.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "property_name": types.Schema(type=types.Type.STRING, description="Name of the Lighting service property to retrieve (e.g., 'Ambient', 'ClockTime').")
                },
                required=["property_name"]
            )
        ),
        types.FunctionDeclaration(
            name="PlaySoundId",
            description="Creates a Sound instance, sets its SoundId, parents it (defaults to Workspace), optionally sets properties (Volume, Looping), and plays it. Returns path to Sound instance or error.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "sound_id": types.Schema(type=types.Type.STRING, description="Roblox Sound ID (e.g., 'rbxassetid://123456789')."),
                    "parent_path": types.Schema(type=types.Type.STRING, default="Workspace", description="Optional. Path to parent the Sound instance. Defaults to 'Workspace' if not specified or invalid."),
                    "properties": types.Schema(
                        type=types.Type.OBJECT,
                        description="Optional. Dictionary of properties for the Sound instance, e.g., {'Volume': 0.5, 'Looping': True, 'Name': 'MySound'}."
                    )
                },
                required=["sound_id"]
            )
        ),
        types.FunctionDeclaration(
            name="set_workspace_property",
            description="Sets a property of the Workspace service. Use dictionary format for Vector3. E.g., set 'Gravity' to {'x':0,'y':-196.2,'z':0}.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "property_name": types.Schema(type=types.Type.STRING, description="Name of the Workspace service property (e.g., 'Gravity', 'FilteringEnabled')."),
                    "value": types.Schema(type=types.Type.STRING, description="New value for the property. Use dicts for Vector3, string for Enums. Value will be parsed by Luau.")
                },
                required=["property_name", "value"]
            )
        ),
        types.FunctionDeclaration(
            name="get_workspace_property",
            description="Gets a property of the Workspace service. Returns value in its appropriate dict/string/primitive format.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "property_name": types.Schema(type=types.Type.STRING, description="Name of the Workspace service property to retrieve (e.g., 'Gravity', 'FilteringEnabled').")
                },
                required=["property_name"]
            )
        ),
        types.FunctionDeclaration(
            name="kick_player",
            description="Kicks a player from the game. This requires the game to be running (e.g. Play Solo or server).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "player_path_or_name": types.Schema(type=types.Type.STRING, description="Full path to the Player object (e.g., 'game.Players.Username') or just the player's username string."),
                    "kick_message": types.Schema(type=types.Type.STRING, default="You have been kicked from the game.", description="Message to display to the kicked player.")
                },
                required=["player_path_or_name"]
            )
        ),
        types.FunctionDeclaration(
            name="create_team",
            description="Creates a new Team in the Teams service.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "team_name": types.Schema(type=types.Type.STRING, description="The name of the new team (e.g., 'Red Team')."),
                    "team_color_brickcolor_string": types.Schema(type=types.Type.STRING, description="BrickColor string for the team color (e.g., 'Bright red', 'Really blue'). See Roblox BrickColor codes."),
                    "auto_assignable": types.Schema(type=types.Type.BOOLEAN, default=True, description="Whether players are automatically assigned to this team. Defaults to true.")
                },
                required=["team_name", "team_color_brickcolor_string"]
            )
        ),

        # --- Phase 2 Tools ---
        types.FunctionDeclaration(
            name="tween_properties",
            description="Smoothly animates specified properties of an instance (e.g., Position, Size, Transparency, Color) to target values over time using TweenService. Does not wait for tween completion. For complex properties like Vector3, Color3, use their dictionary formats.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "instance_path": types.Schema(type=types.Type.STRING, description="Path to the instance to tween."),
                    "duration": types.Schema(type=types.Type.NUMBER, description="Duration of the tween in seconds."),
                    "easing_style": types.Schema(type=types.Type.STRING, description="Enum.EasingStyle string (e.g., 'Linear', 'Quad', 'Elastic')."),
                    "easing_direction": types.Schema(type=types.Type.STRING, description="Enum.EasingDirection string (e.g., 'In', 'Out', 'InOut')."),
                    "repeat_count": types.Schema(type=types.Type.INTEGER, description="Optional. Number of times to repeat. Default 0. Use -1 for infinite.", nullable=True),
                    "reverses": types.Schema(type=types.Type.BOOLEAN, description="Optional. If true, tween plays forwards then reverses. Default false.", nullable=True),
                    "delay_time": types.Schema(type=types.Type.NUMBER, description="Optional. Delay in seconds before tween starts. Default 0.", nullable=True),
                    "properties_to_tween": types.Schema(type=types.Type.OBJECT, description="Dictionary of properties and target values. E.g., {'Position': {'x':10,'y':20,'z':30}, 'Transparency': 0.8}.")
                },
                required=["instance_path", "duration", "easing_style", "easing_direction", "properties_to_tween"]
            )
        ),
        types.FunctionDeclaration(
            name="add_tag",
            description="Adds a tag to the specified instance using CollectionService.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "instance_path": types.Schema(type=types.Type.STRING, description="Path to the instance."),
                    "tag_name": types.Schema(type=types.Type.STRING, description="The tag string to add.")
                },
                required=["instance_path", "tag_name"]
            )
        ),
        types.FunctionDeclaration(
            name="remove_tag",
            description="Removes a tag from the specified instance using CollectionService.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "instance_path": types.Schema(type=types.Type.STRING, description="Path to the instance."),
                    "tag_name": types.Schema(type=types.Type.STRING, description="The tag string to remove.")
                },
                required=["instance_path", "tag_name"]
            )
        ),
        types.FunctionDeclaration(
            name="get_instances_with_tag",
            description="Returns a list of full paths for all instances that have the specified tag.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "tag_name": types.Schema(type=types.Type.STRING, description="The tag string to search for.")
                },
                required=["tag_name"]
            )
        ),
        types.FunctionDeclaration(
            name="has_tag",
            description="Checks if an instance has a specific tag.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "instance_path": types.Schema(type=types.Type.STRING, description="Path to the instance."),
                    "tag_name": types.Schema(type=types.Type.STRING, description="The tag string to check.")
                },
                required=["instance_path", "tag_name"]
            )
        ),
        types.FunctionDeclaration(
            name="compute_path",
            description="Computes a path using PathfindingService. Expects Vector3 dictionaries for positions. Returns waypoints or status.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "start_position": types.Schema(type=types.Type.OBJECT, description="Vector3 dictionary for start: {'x':0,'y':0,'z':0}."),
                    "end_position": types.Schema(type=types.Type.OBJECT, description="Vector3 dictionary for end: {'x':0,'y':0,'z':0}."),
                    "agent_parameters": types.Schema(type=types.Type.OBJECT, description="Optional. Dict for agent params: {'AgentRadius': 2, 'Costs': {'Walkable':1}}.", nullable=True)
                },
                required=["start_position", "end_position"]
            )
        ),
        types.FunctionDeclaration(
            name="create_proximity_prompt",
            description="Creates a ProximityPrompt instance. Scripting its Triggered event requires a separate 'run_script' call.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "parent_part_path": types.Schema(type=types.Type.STRING, description="Path to the Part the prompt will be attached to."),
                    "properties": types.Schema(type=types.Type.OBJECT, description="Optional. Dict for ProximityPrompt properties (e.g., {'ActionText': 'Interact'}).", nullable=True)
                },
                required=["parent_part_path"]
            )
        ),
        types.FunctionDeclaration(
            name="get_product_info",
            description="Retrieves information about an asset from the marketplace.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "asset_id": types.Schema(type=types.Type.INTEGER, description="The ID of the asset."),
                    "info_type": types.Schema(type=types.Type.STRING, description="Enum.InfoType string (e.g., 'Asset', 'Product').") # Or types.Schema(type=types.Type.STRING, enum=["Asset", "Product"])
                },
                required=["asset_id", "info_type"]
            )
        ),
        types.FunctionDeclaration(
            name="prompt_purchase",
            description="Prompts a player to purchase a general asset (like a model or UGC item) using its asset ID. For game passes, a different specific prompt might be needed on the Roblox side. Requires player interaction.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "player_path": types.Schema(type=types.Type.STRING, description="Path to player instance (e.g., 'Players.Username')."),
                    "asset_id": types.Schema(type=types.Type.INTEGER, description="The ID of the asset to purchase.")
                },
                required=["player_path", "asset_id"]
            )
        ),
        types.FunctionDeclaration(
            name="add_debris_item",
            description="Adds an instance to Debris service for auto-destruction after a specified lifetime.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "instance_path": types.Schema(type=types.Type.STRING, description="Path to the instance for Debris."),
                    "lifetime": types.Schema(type=types.Type.NUMBER, description="Lifetime in seconds before destruction.")
                },
                required=["instance_path", "lifetime"]
            )
        ),

        # --- Phase 3 Tools (UI & Input) ---
        types.FunctionDeclaration(
            name="create_gui_element",
            description="Creates GUI elements (ScreenGui, Frame, TextButton, etc.). Parent ScreenGuis to Player paths (e.g., 'Players.LocalPlayer.PlayerGui') or 'StarterGui'. Others to parent GUI elements. For UDim2 (Size/Position), use {'scale_x':0,'offset_x':0,'scale_y':0,'offset_y':0}. If `element_type` is 'ScreenGui' and `parent_path` is nil, it attempts to parent to `Players.LocalPlayer.PlayerGui`; this will error if `LocalPlayer` is not available (e.g., in a server-side context without a specific player target).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "element_type": types.Schema(type=types.Type.STRING, description="Class name of GUI element (e.g., 'ScreenGui', 'Frame', 'TextButton')."),
                    "parent_path": types.Schema(type=types.Type.STRING, description="Optional. Path to parent GUI element, Player (e.g. 'Players.LocalPlayer.PlayerGui'), or 'StarterGui'. Context-dependent if nil for ScreenGui.", nullable=True),
                    "properties": types.Schema(type=types.Type.OBJECT, description="Optional. Dict of properties. E.g., {'Name':'MyButton', 'Size':{'scale_x':0.1,'offset_x':0,'scale_y':0.1,'offset_y':0}, 'Text':'Click'}.", nullable=True)
                },
                required=["element_type"]
            )
        ),
        types.FunctionDeclaration(
            name="get_mouse_position",
            description="Returns the current 2D screen position (X, Y) of the mouse cursor.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={})
        ),
        types.FunctionDeclaration(
            name="get_mouse_hit_cframe",
            description="Returns CFrame (position & orientation dict) in 3D space mouse is pointing at. Can specify camera path.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                     "camera_path": types.Schema(type=types.Type.STRING, description="Optional. Path to Camera instance. Defaults to Workspace.CurrentCamera.", nullable=True)
                }
                # No required parameters, camera_path is optional
            )
        ),
        types.FunctionDeclaration(
            name="is_key_down",
            description="Checks if a keyboard key is currently pressed. Use Enum.KeyCode string (e.g., 'E', 'Space', 'LeftShift', 'KeypadOne').",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "key_code_string": types.Schema(type=types.Type.STRING, description="KeyCode string (e.g., 'E', 'Space', 'KeypadOne').")
                },
                required=["key_code_string"]
            )
        ),
        types.FunctionDeclaration(
            name="is_mouse_button_down",
            description="Checks if a mouse button is currently pressed. Use Enum.UserInputType string for mouse buttons (e.g., 'MouseButton1', 'MouseButton2', 'MouseButton3').",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "mouse_button_string": types.Schema(type=types.Type.STRING, description="Mouse button UserInputType string (e.g., 'MouseButton1').")
                },
                required=["mouse_button_string"]
            )
        ),

        # --- Phase 4 Tools (DataStores) ---
        types.FunctionDeclaration(
            name="save_data",
            description="Saves a Lua table (as JSON object/array, string, number, or boolean) to a DataStore using a name and key.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "store_name": types.Schema(type=types.Type.STRING, description="Name of the DataStore."),
                    "key": types.Schema(type=types.Type.STRING, description="The key to save data under."),
                    "data": types.Schema(type=types.Type.STRING, description="Data to save (JSON object/array, string, number, or boolean). Complex Lua tables will be JSON encoded by the client; provide as valid JSON structure. Value will be parsed by Luau.")
                },
                required=["store_name", "key", "data"]
            )
        ),
        types.FunctionDeclaration(
            name="load_data",
            description="Loads data from a DataStore using a name and key. Returns data in JSON-friendly format.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "store_name": types.Schema(type=types.Type.STRING, description="Name of the DataStore."),
                    "key": types.Schema(type=types.Type.STRING, description="The key to load data from.")
                },
                required=["store_name", "key"]
            )
        ),
        types.FunctionDeclaration(
            name="increment_data",
            description="Atomically increments or decrements a numerical value stored in a DataStore. If the key does not exist, it's initialized with the increment_by value.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "store_name": types.Schema(type=types.Type.STRING, description="Name of the DataStore."),
                    "key": types.Schema(type=types.Type.STRING, description="The key for the numerical value."),
                    "increment_by": types.Schema(type=types.Type.NUMBER, description="Amount to increment by. Can be negative to decrement.")
                },
                required=["store_name", "key", "increment_by"]
            )
        ),
        types.FunctionDeclaration(
            name="remove_data",
            description="Removes data for a specific key from a DataStore.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "store_name": types.Schema(type=types.Type.STRING, description="Name of the DataStore."),
                    "key": types.Schema(type=types.Type.STRING, description="The key of the data to remove.")
                },
                required=["store_name", "key"]
            )
        ),

        # --- Phase 5 Tools (Teleport, Chat, HTTP, Teams, InsertService, Utility) ---
        types.FunctionDeclaration(
            name="teleport_player_to_place",
            description="Teleports one or more players to a different place in the same game or a different game. Requires valid player paths and a place ID.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "player_paths": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="List of full paths to Player instances to teleport (e.g., ['Players.Player1', 'Players.Player2'])."),
                    "place_id": types.Schema(type=types.Type.INTEGER, description="The ID of the destination place."),
                    "job_id": types.Schema(type=types.Type.STRING, description="Optional. Specific server job ID to teleport to.", nullable=True),
                    "teleport_data": types.Schema(type=types.Type.OBJECT, description="Optional. Data to pass to the destination place (accessible via GetTeleportData). Should be a JSON object.", nullable=True),
                    "custom_loading_screen_gui_path": types.Schema(type=types.Type.STRING, description="Optional. Path to a custom ScreenGui for loading screen.", nullable=True)
                },
                required=["player_paths", "place_id"]
            )
        ),
        types.FunctionDeclaration(
            name="get_teleport_data",
            description="Retrieves data passed to the current place via a teleport. Only useful if the place was teleported to with data.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={})
        ),
        types.FunctionDeclaration(
            name="send_chat_message",
            description="Sends a message to a TextChannel. If `speaker_path` is provided, that instance is the source. If `channel_name` is nil, a default system channel is targeted. True private whispers are not directly supported; to simulate, Gemini can format the message content e.g., '[To TargetPlayer]: your message'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "message_text": types.Schema(type=types.Type.STRING, description="The text of the message to send."),
                    "channel_name": types.Schema(type=types.Type.STRING, description="Optional. Name of the chat channel (e.g., 'All', 'Team'). Defaults to system behavior.", nullable=True),
                    "speaker_path": types.Schema(type=types.Type.STRING, description="Optional. Path to an instance to act as speaker (e.g. an NPC's Part or Model).", nullable=True),
                    "target_player_path": types.Schema(type=types.Type.STRING, description="Optional. Path to a Player instance for a whisper/private message.", nullable=True)
                },
                required=["message_text"]
            )
        ),
        types.FunctionDeclaration(
            name="filter_text_for_player",
            description="Filters text according to Roblox chat filter rules for a specific player. Returns the filtered text.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "text_to_filter": types.Schema(type=types.Type.STRING, description="The text to be filtered."),
                    "player_path": types.Schema(type=types.Type.STRING, description="Path to the Player instance for whom the text is being filtered.")
                },
                required=["text_to_filter", "player_path"]
            )
        ),
        types.FunctionDeclaration(
            name="create_text_channel",
            description="Creates a new text chat channel in the Chat service.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "channel_name": types.Schema(type=types.Type.STRING, description="The name for the new text channel."),
                    "properties": types.Schema(type=types.Type.OBJECT, description="Optional. Dictionary of properties for the TextChannel (e.g., {'WelcomeMessage': 'Hi!'}).", nullable=True)
                },
                required=["channel_name"]
            )
        ),
        # http_request tool removed.
        types.FunctionDeclaration(
            name="get_teams",
            description="Returns a list of all teams in the game, with their names and full paths.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={})
        ),
        types.FunctionDeclaration(
            name="get_players_in_team",
            description="Returns a list of players (names and paths) in a specific team.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "team_path_or_name": types.Schema(type=types.Type.STRING, description="Full path to the Team instance or its exact name.")
                },
                required=["team_path_or_name"]
            )
        ),
        types.FunctionDeclaration(
            name="load_asset_by_id",
            description="Loads an asset from Roblox using its ID via InsertService. Returns the path to the loaded asset container (typically a Model).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "asset_id": types.Schema(type=types.Type.INTEGER, description="The ID of the asset to load."),
                    "parent_path": types.Schema(type=types.Type.STRING, description="Optional. Path to the instance where the loaded asset should be parented. Defaults to Workspace.", nullable=True),
                    "desired_name": types.Schema(type=types.Type.STRING, description="Optional. Name to give the loaded asset model.", nullable=True)
                },
                required=["asset_id"]
            )
        ),
        types.FunctionDeclaration(
            name="get_children_of_instance",
            description="Returns a list of full paths for all immediate children of the specified instance.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "instance_path": types.Schema(type=types.Type.STRING, description="Path to the instance whose children are to be retrieved.")
                },
                required=["instance_path"]
            )
        ),
        types.FunctionDeclaration(
            name="get_descendants_of_instance",
            description="Returns a list of full paths for all descendants (children, children of children, etc.) of the specified instance.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "instance_path": types.Schema(type=types.Type.STRING, description="Path to the instance whose descendants are to be retrieved.")
                },
                required=["instance_path"]
            )
        ),
        types.FunctionDeclaration(
            name="find_first_child_matching",
            description="Finds the first child of an instance that matches the given name. Can search recursively.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "parent_path": types.Schema(type=types.Type.STRING, description="Path to the parent instance to search within."),
                    "child_name": types.Schema(type=types.Type.STRING, description="Name of the child instance to find."),
                    "recursive": types.Schema(type=types.Type.BOOLEAN, description="Optional. If true, searches descendants recursively. Defaults to false (immediate children only).", nullable=True)
                },
                required=["parent_path", "child_name"]
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

        elif tool_name == "RunCode": # Changed from run_command to RunCode
            command = args.get("command")
            if not isinstance(command, str) or not command.strip(): # Keep allowing empty string for now, Luau side might handle
                return False, "Invalid 'command'. Must be a string."
        elif tool_name == "get_selection":
            pass
        # --- Core Instance Manipulation Tools ---
        elif tool_name == "CreateInstance":
            class_name = args.get("class_name")
            properties = args.get("properties")
            if not isinstance(class_name, str) or not class_name.strip():
                return False, "Invalid 'class_name'. Must be a non-empty string."
            if not isinstance(properties, dict): # 'properties' should at least be a dict
                return False, "Invalid 'properties'. Must be a dictionary."
        elif tool_name == "set_instance_properties":
            path = args.get("path")
            properties = args.get("properties")
            if not isinstance(path, str) or not path.strip():
                return False, "Invalid 'path'. Must be a non-empty string."
            if not isinstance(properties, dict) or not properties:
                return False, "Invalid 'properties'. Must be a non-empty dictionary."
        elif tool_name == "get_instance_properties":
            path = args.get("path")
            property_names = args.get("property_names")
            if not isinstance(path, str) or not path.strip():
                return False, "Invalid 'path'. Must be a non-empty string."
            if not isinstance(property_names, list) or not property_names:
                return False, "Invalid 'property_names'. Must be a non-empty list of strings."
            if not all(isinstance(p, str) and p.strip() for p in property_names):
                return False, "Invalid 'property_names'. All items must be non-empty strings."
        elif tool_name == "call_instance_method":
            path = args.get("path")
            method_name = args.get("method_name")
            arguments = args.get("arguments")
            if not isinstance(path, str) or not path.strip():
                return False, "Invalid 'path'. Must be a non-empty string."
            if not isinstance(method_name, str) or not method_name.strip():
                return False, "Invalid 'method_name'. Must be a non-empty string."
            if not isinstance(arguments, list): # arguments should be a list (can be empty)
                return False, "Invalid 'arguments'. Must be a list."
        elif tool_name == "delete_instance":
            path = args.get("path")
            if not isinstance(path, str) or not path.strip():
                return False, "Invalid 'path'. Must be a non-empty string."
        elif tool_name == "select_instances":
            paths = args.get("paths")
            if not isinstance(paths, list):
                return False, "Invalid 'paths'. Must be a list of strings."
            if not all(isinstance(p, str) and p.strip() for p in paths if paths): # Check elements if list is not empty
                 return False, "Invalid 'paths'. All items must be non-empty strings if list is not empty."

        # --- Essential Service Tools ---
        elif tool_name == "run_script":
            parent_path = args.get("parent_path")
            script_source = args.get("script_source")
            script_name = args.get("script_name")
            script_type = args.get("script_type")
            if not isinstance(parent_path, str) or not parent_path.strip():
                return False, "Invalid 'parent_path'. Must be a non-empty string."
            if not isinstance(script_source, str) or not script_source.strip(): # Allow empty script, but must be string
                return False, "Invalid 'script_source'. Must be a string."
            if not isinstance(script_name, str) or not script_name.strip():
                return False, "Invalid 'script_name'. Must be a non-empty string."
            if script_type not in ["Script", "LocalScript"]:
                return False, "Invalid 'script_type'. Must be 'Script' or 'LocalScript'."
        elif tool_name == "set_lighting_property":
            property_name = args.get("property_name")
            # Value can be various types, so only check existence of key
            if not isinstance(property_name, str) or not property_name.strip():
                return False, "Invalid 'property_name'. Must be a non-empty string."
            if "value" not in args:
                return False, "'value' parameter is required."
        elif tool_name == "get_lighting_property":
            property_name = args.get("property_name")
            if not isinstance(property_name, str) or not property_name.strip():
                return False, "Invalid 'property_name'. Must be a non-empty string."
        elif tool_name == "play_sound_id":
            sound_id = args.get("sound_id")
            if not isinstance(sound_id, str) or not sound_id.strip():
                return False, "Invalid 'sound_id'. Must be a non-empty string."
            # parent_path and properties are optional or have defaults
            if "parent_path" in args and not isinstance(args.get("parent_path"), str):
                return False, "Invalid 'parent_path'. Must be a string if provided."
            if "properties" in args and not isinstance(args.get("properties"), dict):
                return False, "Invalid 'properties'. Must be a dictionary if provided."
        elif tool_name == "set_workspace_property":
            property_name = args.get("property_name")
            if not isinstance(property_name, str) or not property_name.strip():
                return False, "Invalid 'property_name'. Must be a non-empty string."
            if "value" not in args:
                return False, "'value' parameter is required."
        elif tool_name == "get_workspace_property":
            property_name = args.get("property_name")
            if not isinstance(property_name, str) or not property_name.strip():
                return False, "Invalid 'property_name'. Must be a non-empty string."
        elif tool_name == "kick_player":
            player_path_or_name = args.get("player_path_or_name")
            if not isinstance(player_path_or_name, str) or not player_path_or_name.strip():
                return False, "Invalid 'player_path_or_name'. Must be a non-empty string."
            if "kick_message" in args and not isinstance(args.get("kick_message"), str):
                 return False, "Invalid 'kick_message'. Must be a string if provided."
        elif tool_name == "create_team":
            team_name = args.get("team_name")
            team_color = args.get("team_color_brickcolor_string")
            auto_assignable = args.get("auto_assignable") # Optional, defaults in schema
            if not isinstance(team_name, str) or not team_name.strip():
                return False, "Invalid 'team_name'. Must be a non-empty string."
            if not isinstance(team_color, str) or not team_color.strip():
                return False, "Invalid 'team_color_brickcolor_string'. Must be a non-empty string."
            if "auto_assignable" in args and not isinstance(auto_assignable, bool):
                return False, "Invalid 'auto_assignable'. Must be a boolean if provided."

        # --- Phase 2 Tools Validation ---
        elif tool_name == "tween_properties":
            if not isinstance(args.get("instance_path"), str) or not args.get("instance_path").strip():
                return False, "Invalid 'instance_path'. Must be a non-empty string."
            if not isinstance(args.get("duration"), (int, float)) or args.get("duration") <= 0:
                return False, "Invalid 'duration'. Must be a positive number."
            if not isinstance(args.get("easing_style"), str) or not args.get("easing_style").strip():
                return False, "Invalid 'easing_style'. Must be a non-empty string."
            if not isinstance(args.get("easing_direction"), str) or not args.get("easing_direction").strip():
                return False, "Invalid 'easing_direction'. Must be a non-empty string."
            if not isinstance(args.get("properties_to_tween"), dict) or not args.get("properties_to_tween"):
                return False, "Invalid 'properties_to_tween'. Must be a non-empty dictionary."
            if "repeat_count" in args and args.get("repeat_count") is not None and not isinstance(args.get("repeat_count"), int):
                return False, "Invalid 'repeat_count'. Must be an integer if provided."
            if "reverses" in args and args.get("reverses") is not None and not isinstance(args.get("reverses"), bool):
                return False, "Invalid 'reverses'. Must be a boolean if provided."
            if "delay_time" in args and args.get("delay_time") is not None and (not isinstance(args.get("delay_time"), (int, float)) or args.get("delay_time") < 0):
                return False, "Invalid 'delay_time'. Must be a non-negative number if provided."

        elif tool_name == "add_tag" or tool_name == "remove_tag" or tool_name == "has_tag":
            if not isinstance(args.get("instance_path"), str) or not args.get("instance_path").strip():
                return False, "Invalid 'instance_path'. Must be a non-empty string."
            if not isinstance(args.get("tag_name"), str) or not args.get("tag_name").strip():
                return False, "Invalid 'tag_name'. Must be a non-empty string."

        elif tool_name == "get_instances_with_tag":
            if not isinstance(args.get("tag_name"), str) or not args.get("tag_name").strip():
                return False, "Invalid 'tag_name'. Must be a non-empty string."

        elif tool_name == "compute_path":
            if not isinstance(args.get("start_position"), dict):
                return False, "Invalid 'start_position'. Must be a dictionary."
            if not isinstance(args.get("end_position"), dict):
                return False, "Invalid 'end_position'. Must be a dictionary."
            if "agent_parameters" in args and args.get("agent_parameters") is not None and not isinstance(args.get("agent_parameters"), dict):
                return False, "Invalid 'agent_parameters'. Must be a dictionary if provided."

        elif tool_name == "create_proximity_prompt":
            if not isinstance(args.get("parent_part_path"), str) or not args.get("parent_part_path").strip():
                return False, "Invalid 'parent_part_path'. Must be a non-empty string."
            if "properties" in args and args.get("properties") is not None and not isinstance(args.get("properties"), dict):
                return False, "Invalid 'properties'. Must be a dictionary if provided."

        elif tool_name == "get_product_info":
            if not isinstance(args.get("asset_id"), int) or args.get("asset_id") <= 0:
                return False, "Invalid 'asset_id'. Must be a positive integer."
            if not isinstance(args.get("info_type"), str) or not args.get("info_type").strip():
                return False, "Invalid 'info_type'. Must be a non-empty string."

        elif tool_name == "prompt_purchase":
            if not isinstance(args.get("player_path"), str) or not args.get("player_path").strip():
                return False, "Invalid 'player_path'. Must be a non-empty string."
            if not isinstance(args.get("asset_id"), int) or args.get("asset_id") <= 0:
                return False, "Invalid 'asset_id'. Must be a positive integer."

        elif tool_name == "add_debris_item":
            if not isinstance(args.get("instance_path"), str) or not args.get("instance_path").strip():
                return False, "Invalid 'instance_path'. Must be a non-empty string."
            if not isinstance(args.get("lifetime"), (int, float)) or args.get("lifetime") < 0: # Typically non-negative, though Debris might handle <0
                return False, "Invalid 'lifetime'. Must be a non-negative number."

        # --- Phase 3 Tools Validation (UI & Input) ---
        elif tool_name == "create_gui_element":
            if not isinstance(args.get("element_type"), str) or not args.get("element_type").strip():
                return False, "Invalid 'element_type'. Must be a non-empty string."
            if "parent_path" in args and args.get("parent_path") is not None and (not isinstance(args.get("parent_path"), str) or not args.get("parent_path").strip()):
                return False, "Invalid 'parent_path'. Must be a non-empty string if provided."
            if "properties" in args and args.get("properties") is not None and not isinstance(args.get("properties"), dict):
                return False, "Invalid 'properties'. Must be a dictionary if provided."

        elif tool_name == "get_mouse_position":
            # No arguments to validate
            pass

        elif tool_name == "get_mouse_hit_cframe":
            if "camera_path" in args and args.get("camera_path") is not None and (not isinstance(args.get("camera_path"), str) or not args.get("camera_path").strip()):
                 return False, "Invalid 'camera_path'. Must be a non-empty string if provided."

        elif tool_name == "is_key_down":
            if not isinstance(args.get("key_code_string"), str) or not args.get("key_code_string").strip():
                return False, "Invalid 'key_code_string'. Must be a non-empty string."

        elif tool_name == "is_mouse_button_down":
            if not isinstance(args.get("mouse_button_string"), str) or not args.get("mouse_button_string").strip():
                return False, "Invalid 'mouse_button_string'. Must be a non-empty string."

        # --- Phase 4 Tools Validation (DataStores) ---
        elif tool_name == "save_data":
            if not isinstance(args.get("store_name"), str) or not args.get("store_name").strip():
                return False, "Invalid 'store_name'. Must be a non-empty string."
            if not isinstance(args.get("key"), str) or not args.get("key").strip():
                return False, "Invalid 'key'. Must be a non-empty string."
            if "data" not in args: # Data can be various types (dict, list, str, int, float, bool, None)
                return False, "'data' parameter is required."

        elif tool_name == "load_data":
            if not isinstance(args.get("store_name"), str) or not args.get("store_name").strip():
                return False, "Invalid 'store_name'. Must be a non-empty string."
            if not isinstance(args.get("key"), str) or not args.get("key").strip():
                return False, "Invalid 'key'. Must be a non-empty string."

        elif tool_name == "increment_data":
            if not isinstance(args.get("store_name"), str) or not args.get("store_name").strip():
                return False, "Invalid 'store_name'. Must be a non-empty string."
            if not isinstance(args.get("key"), str) or not args.get("key").strip():
                return False, "Invalid 'key'. Must be a non-empty string."
            if not isinstance(args.get("increment_by"), (int, float)):
                return False, "Invalid 'increment_by'. Must be a number."

        elif tool_name == "remove_data":
            if not isinstance(args.get("store_name"), str) or not args.get("store_name").strip():
                return False, "Invalid 'store_name'. Must be a non-empty string."
            if not isinstance(args.get("key"), str) or not args.get("key").strip():
                return False, "Invalid 'key'. Must be a non-empty string."

        # --- Phase 5 Tools Validation ---
        elif tool_name == "teleport_player_to_place":
            player_paths = args.get("player_paths")
            if not isinstance(player_paths, list) or not player_paths:
                return False, "Invalid 'player_paths'. Must be a non-empty list."
            if not all(isinstance(p, str) and p.strip() for p in player_paths):
                return False, "All items in 'player_paths' must be non-empty strings."
            if not isinstance(args.get("place_id"), int) or args.get("place_id") <= 0:
                return False, "Invalid 'place_id'. Must be a positive integer."
            if "job_id" in args and args.get("job_id") is not None and (not isinstance(args.get("job_id"), str) or not args.get("job_id").strip()):
                return False, "Invalid 'job_id'. Must be a non-empty string if provided."
            if "teleport_data" in args and args.get("teleport_data") is not None and not isinstance(args.get("teleport_data"), dict):
                return False, "Invalid 'teleport_data'. Must be a dictionary if provided."
            if "custom_loading_screen_gui_path" in args and args.get("custom_loading_screen_gui_path") is not None and \
               (not isinstance(args.get("custom_loading_screen_gui_path"), str) or not args.get("custom_loading_screen_gui_path").strip()):
                return False, "Invalid 'custom_loading_screen_gui_path'. Must be a non-empty string if provided."

        elif tool_name == "get_teleport_data":
            # No arguments to validate
            pass

        elif tool_name == "send_chat_message":
            if not isinstance(args.get("message_text"), str): # Allow empty message? For now, yes.
                return False, "Invalid 'message_text'. Must be a string."
            if "channel_name" in args and args.get("channel_name") is not None and (not isinstance(args.get("channel_name"), str) or not args.get("channel_name").strip()):
                return False, "Invalid 'channel_name'. Must be a non-empty string if provided."
            if "speaker_path" in args and args.get("speaker_path") is not None and (not isinstance(args.get("speaker_path"), str) or not args.get("speaker_path").strip()):
                return False, "Invalid 'speaker_path'. Must be a non-empty string if provided."
            if "target_player_path" in args and args.get("target_player_path") is not None and \
               (not isinstance(args.get("target_player_path"), str) or not args.get("target_player_path").strip()):
                return False, "Invalid 'target_player_path'. Must be a non-empty string if provided."

        elif tool_name == "filter_text_for_player":
            if not isinstance(args.get("text_to_filter"), str): # Allow empty? Yes.
                 return False, "Invalid 'text_to_filter'. Must be a string."
            if not isinstance(args.get("player_path"), str) or not args.get("player_path").strip():
                return False, "Invalid 'player_path'. Must be a non-empty string."

        elif tool_name == "create_text_channel":
            if not isinstance(args.get("channel_name"), str) or not args.get("channel_name").strip():
                return False, "Invalid 'channel_name'. Must be a non-empty string."
            if "properties" in args and args.get("properties") is not None and not isinstance(args.get("properties"), dict):
                return False, "Invalid 'properties'. Must be a dictionary if provided."

        # http_request validation removed.

        elif tool_name == "get_teams":
            # No arguments to validate
            pass

        elif tool_name == "get_players_in_team":
            if not isinstance(args.get("team_path_or_name"), str) or not args.get("team_path_or_name").strip():
                return False, "Invalid 'team_path_or_name'. Must be a non-empty string."

        elif tool_name == "load_asset_by_id":
            if not isinstance(args.get("asset_id"), int) or args.get("asset_id") <= 0:
                return False, "Invalid 'asset_id'. Must be a positive integer."
            if "parent_path" in args and args.get("parent_path") is not None and (not isinstance(args.get("parent_path"), str) or not args.get("parent_path").strip()):
                return False, "Invalid 'parent_path'. Must be a non-empty string if provided."
            if "desired_name" in args and args.get("desired_name") is not None and (not isinstance(args.get("desired_name"), str) or not args.get("desired_name").strip()):
                return False, "Invalid 'desired_name'. Must be a non-empty string if provided."

        elif tool_name == "get_children_of_instance" or tool_name == "get_descendants_of_instance":
            if not isinstance(args.get("instance_path"), str) or not args.get("instance_path").strip():
                return False, "Invalid 'instance_path'. Must be a non-empty string."

        elif tool_name == "find_first_child_matching":
            if not isinstance(args.get("parent_path"), str) or not args.get("parent_path").strip():
                return False, "Invalid 'parent_path'. Must be a non-empty string."
            if not isinstance(args.get("child_name"), str) or not args.get("child_name").strip():
                return False, "Invalid 'child_name'. Must be a non-empty string."
            if "recursive" in args and args.get("recursive") is not None and not isinstance(args.get("recursive"), bool):
                return False, "Invalid 'recursive'. Must be a boolean if provided."

        return True, ""

    # II.2. Update execute_tool_call
    async def execute_tool_call(self, function_call: types.FunctionCall) -> Dict[str, Any]: # II.2. Input type hint and return type
        """Executes a single tool call and returns a dictionary for the new SDK."""
        original_tool_name = function_call.name
        original_tool_args = dict(function_call.args)

        mcp_tool_name = original_tool_name
        mcp_tool_args = original_tool_args

        ConsoleFormatter.print_tool_call(original_tool_name, original_tool_args)

        is_valid, error_msg = self._validate_args(original_tool_name, original_tool_args)
        if not is_valid:
            ConsoleFormatter.print_tool_error({"validation_error": f"Argument validation failed: {error_msg}"})

            return {"name": original_tool_name, "response": {"error": f"Invalid arguments provided by AI: {error_msg}"}}

        if original_tool_name == "insert_model":
            mcp_tool_name = "insert_model"
            mcp_tool_args = original_tool_args
            logger.info(f"Dispatching ToolCall: '{original_tool_name}' directly to MCP tool '{mcp_tool_name}' with args: {mcp_tool_args}")
        else:
            # All other tools (CreateInstance, RunCode, GetSelection, etc.) are routed via execute_discovered_luau_tool
            mcp_tool_name = "execute_discovered_luau_tool"
            # Serialize original_tool_args into a JSON string
            tool_arguments_json_str = json.dumps(original_tool_args)
            luau_tool_name_to_execute = original_tool_name
            if original_tool_name == "set_instance_properties":
                luau_tool_name_to_execute = "SetInstanceProperties"
            # Add other mappings here if needed in the future
            mcp_tool_args = {
                "tool_name": luau_tool_name_to_execute, # Use the potentially corrected name
                "tool_arguments_str": tool_arguments_json_str
            }
            # Update logger message to reflect the change if desired, or keep as is if original_tool_args is fine for logging.
            # For clarity in logs, let's log what's actually being prepared for MCP:
            logger.info(f"Dispatching ToolCall: '{original_tool_name}' via MCP tool '{mcp_tool_name}' for Luau script '{luau_tool_name_to_execute}'. Luau script args (as JSON string): {tool_arguments_json_str}")

        output_content_dict = {}
        try:
            mcp_response = await self.mcp_client.send_tool_execution_request(mcp_tool_name, mcp_tool_args)

            if mcp_tool_name == "insert_model": # insert_model returns result directly, not nested
                if "result" in mcp_response:
                    output_content_dict = {"status": "success", "output": mcp_response["result"]}
                    ConsoleFormatter.print_tool_result(mcp_response["result"])
                elif "error" in mcp_response:
                    output_content_dict = {"status": "error", "details": mcp_response["error"]}
                    ConsoleFormatter.print_tool_error(mcp_response["error"])
                else:
                    output_content_dict = {"status": "unknown_response", "raw": mcp_response}
                    ConsoleFormatter.print_tool_error(output_content_dict)

            # For execute_discovered_luau_tool results:
            elif "result" in mcp_response: # This 'result' is the dict like {"content": [...], "isError": ...}
                raw_mcp_luau_result = mcp_response.get("result")

                if not isinstance(raw_mcp_luau_result, dict):
                    # This case should ideally not happen if MCP server is consistent
                    logger.error(f"Unexpected raw_mcp_luau_result type for {original_tool_name}: {type(raw_mcp_luau_result)}. Content: {raw_mcp_luau_result}")
                    output_content_dict = {"status": "error", "details": "Malformed MCP response: 'result' is not a dictionary.", "raw_luau_result": raw_mcp_luau_result }
                    ConsoleFormatter.print_tool_error(output_content_dict)
                    return {"name": original_tool_name, "response": output_content_dict}

                is_luau_error = raw_mcp_luau_result.get("isError", False)
                content_list = raw_mcp_luau_result.get("content", [])
                inner_text = ""

                if isinstance(content_list, list) and len(content_list) > 0 and isinstance(content_list[0], dict):
                    inner_text = content_list[0].get("text", "")
                elif is_luau_error and not content_list : # Error might be flagged with no content, or content is not as expected
                    inner_text = raw_mcp_luau_result.get("errorMessage", "Luau tool error: No error message provided in content.") if "errorMessage" in raw_mcp_luau_result else "Luau tool error: Malformed or missing content."
                elif not is_luau_error : # Success case but malformed content
                     logger.warning(f"Malformed content list for successful Luau call {original_tool_name}: {content_list}")
                     inner_text = '{"status":"error", "tool_message":"Tool returned success but content was malformed in MCP response."}' # Force JSON
                # if is_luau_error is true AND content_list is malformed, inner_text will be the errorMessage or generic one from above

                if is_luau_error:
                    output_content_dict = {"status": "error_from_luau_tool", "tool_message": inner_text.strip()}
                    ConsoleFormatter.print_tool_error({"luau_tool_error_message": inner_text.strip()})
                else:
                    # No error flagged by Luau, so inner_text should be a JSON string.
                    try:

                        data = json.loads(inner_text)
                        # --- Start of specific tool success parsing ---
                        if original_tool_name == "get_selection":
                            if isinstance(data, dict) and \
                               "selected_instances" in data and \
                               isinstance(data["selected_instances"], list) and \
                               not data["selected_instances"]:

                                output_content_dict = {
                                    "status": "success",
                                    "message": "No instances are currently selected in Roblox Studio.",
                                    "selection_empty": True,
                                    "selected_instances_paths": []
                                }
                                ConsoleFormatter.print_tool_result({"status": "success", "message": "No instances selected (processed by Python agent)."})

                            else: # Assumes 'data' itself is the expected output if not empty selection.
                                output_content_dict = {"status": "success", "output": data}
                                ConsoleFormatter.print_tool_result(data)
                        elif original_tool_name == "FindFirstChildMatching":
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", ""),
                               "parent_path": data.get("parent_path"), "child_name_searched": data.get("child_name_searched"),
                               "recursive_search": data.get("recursive_search"), "child_found": bool(data.get("found_child_path")),
                               "found_child_path": data.get("found_child_path"), "found_child_class_name": data.get("found_child_class_name")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "message": f"FindFirstChildMatching processed: {data.get('message', '')}"})
                        elif original_tool_name == "GetChildrenOfInstance":
                            children_list = data.get("children", [])
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", f"Found {len(children_list)} children for {data.get('instance_path')}."),
                               "instance_path": data.get("instance_path"), "children_count": len(children_list), "children": children_list
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "message": f"GetChildrenOfInstance processed for {data.get('instance_path')}"})
                        elif original_tool_name == "GetDescendantsOfInstance":
                            descendants_list = data.get("descendants", [])
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", f"Found {len(descendants_list)} descendants for {data.get('instance_path')}."),
                               "instance_path": data.get("instance_path"), "descendants_count": len(descendants_list), "descendants": descendants_list
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "message": f"GetDescendantsOfInstance processed for {data.get('instance_path')}"})
                        elif original_tool_name == "GetInstancesWithTag":
                            instances_list = data.get("instances", [])
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", f"Found {len(instances_list)} instances with tag '{data.get('tag_name')}'."),
                               "tag_name": data.get("tag_name"), "instance_count": len(instances_list), "instances": instances_list
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "message": f"GetInstancesWithTag processed for tag {data.get('tag_name')}"})
                        elif original_tool_name == "HasTag":
                             output_content_dict = {
                               "status": "success", "tool_message": data.get("message", f"Tag '{data.get('tag_name')}' on '{data.get('instance_path')}' is {data.get('has_tag')}."),
                               "instance_path": data.get("instance_path"), "tag_name": data.get("tag_name"), "has_tag": data.get("has_tag")
                            }
                             ConsoleFormatter.print_tool_result({"status": "success", "message": f"HasTag processed for {data.get('instance_path')}"})
                        elif original_tool_name == "CreateInstance":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "instance_path": data.get("instance_path"), "class_name": data.get("class_name")}
                            ConsoleFormatter.print_tool_result({"status": "success", "message": f"CreateInstance processed: {data.get('message')}"})
                        elif original_tool_name == "DeleteInstance":
                            path_not_found = data.get("path_not_found")
                            output_content_dict = {
                               "status": "success_instance_not_found" if path_not_found else "success",
                               "tool_message": data.get("message"), "deleted_path": data.get("deleted_path"), "path_not_found": path_not_found
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "message": f"DeleteInstance processed: {data.get('message')}"})
                        elif original_tool_name in ["GetProperties", "GetInstanceProperties"]:
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", f"Properties fetched for {data.get('instance_path')}."),
                               "instance_path": data.get("instance_path"), "properties": data.get("properties"),"errors": data.get("errors")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": f"Properties fetched for {data.get('instance_path')}"})
                        elif original_tool_name == "GetLightingProperty":
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", f"Lighting property {data.get('property_name')} fetched."),
                               "property_name": data.get("property_name"), "value": data.get("value")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": f"Lighting property {data.get('property_name')} fetched."})
                        elif original_tool_name == "GetWorkspaceProperty":
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", f"Workspace property {data.get('property_name')} fetched."),
                               "property_name": data.get("property_name"), "value": data.get("value")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": f"Workspace property {data.get('property_name')} fetched."})
                        elif original_tool_name == "GetMouseHitCFrame":
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", "Mouse hit CFrame processed."),
                               "instance_hit_path": data.get("instance_hit_path"), "position": data.get("position"), "cframe_components": data.get("cframe_components")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message", "Mouse hit CFrame processed.")})
                        elif original_tool_name == "GetMousePosition":
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", "Mouse position fetched."),
                               "x": data.get("x"), "y": data.get("y"), "viewport_size": data.get("viewport_size")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message", "Mouse position fetched.")})
                        elif original_tool_name == "GetPlayersInTeam":
                            players_list = data.get("players", [])
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", f"Players in team {data.get('team_name')} fetched."),
                               "team_name": data.get("team_name"), "team_path": data.get("team_path"),
                               "player_count": len(players_list), "players": players_list
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": f"Players in team {data.get('team_name')} fetched."})
                        elif original_tool_name == "GetProductInfo":
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", f"Product info for asset ID {data.get('asset_id')} fetched."),
                               "asset_id": data.get("asset_id"), "info_type_used": data.get("info_type_used"), "product_info": data.get("product_info")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": f"Product info for asset ID {data.get('asset_id')} fetched."})
                        elif original_tool_name == "GetTeams":
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", "Teams fetched."),
                               "team_count": data.get("team_count"), "teams": data.get("teams")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message", "Teams fetched.")})
                        elif original_tool_name == "GetTeleportData":
                            output_content_dict = {
                               "status": "success", "tool_message": data.get("message", "Teleport data fetched."),
                               "teleport_data": data.get("teleport_data"), "source_place_id": data.get("source_place_id")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message", "Teleport data fetched.")})
                        elif original_tool_name == "AddDebrisItem":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "instance_path": data.get("instance_path"), "lifetime": data.get("lifetime")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "AddTag":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "instance_path": data.get("instance_path"), "tag_name": data.get("tag_name")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "CallInstanceMethod":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "results": data.get("results")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "CreateGuiElement":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "element_path": data.get("element_path"), "element_type": data.get("element_type"), "parent_path_used": data.get("parent_path_used")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "CreateProximityPrompt":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "prompt_path": data.get("prompt_path"), "action_text": data.get("action_text"), "object_text": data.get("object_text"), "max_activation_distance": data.get("max_activation_distance")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "CreateTeam":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "team_name": data.get("team_name"), "team_color": data.get("team_color"), "auto_assignable": data.get("auto_assignable"), "team_path": data.get("team_path")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "CreateTextChannel":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "channel_name": data.get("channel_name"), "channel_path": data.get("channel_path")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "IncrementData":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "store_name": data.get("store_name"), "key": data.get("key"), "new_value": data.get("new_value"), "incremented_by": data.get("incremented_by")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "IsKeyDown":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "key_code_used": data.get("key_code_used"), "is_down": data.get("is_down")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "IsMouseButtonDown":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "mouse_button_checked": data.get("mouse_button_checked"), "is_down": data.get("is_down")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "KickPlayer":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "kicked_player_name": data.get("kicked_player_name"), "kick_message_used": data.get("kick_message_used")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "LoadAssetById":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "asset_path": data.get("asset_path"), "asset_id": data.get("asset_id"), "asset_class_name": data.get("asset_class_name")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "LoadData":
                             output_content_dict = {"status": "success", "tool_message": data.get("message"), "store_name": data.get("store_name"), "key": data.get("key"), "data": data.get("data")}
                             ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "PlaySoundId":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "sound_path": data.get("sound_path"), "sound_id": data.get("sound_id"), "is_playing": data.get("is_playing"), "duration": data.get("duration"), "details": data.get("details")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "PromptPurchase":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "player_name": data.get("player_name"), "asset_id": data.get("asset_id"), "purchase_type_prompted": data.get("purchase_type_prompted")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "RemoveData":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "store_name": data.get("store_name"), "key": data.get("key")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "RunScript":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "script_path": data.get("script_path"), "script_type": data.get("script_type"), "initially_disabled": data.get("initially_disabled")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "SaveData":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "store_name": data.get("store_name"), "key": data.get("key")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "SelectInstances":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "selected_paths": data.get("selected_paths"), "selection_count": data.get("selection_count"), "errors_finding_paths": data.get("errors_finding_paths")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "SendChatMessage":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "message_sent": data.get("message_sent"), "channel_used": data.get("channel_used"), "speaker_used": data.get("speaker_used")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name in ["SetInstanceProperties", "SetProperties"]:
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "instance_path": data.get("instance_path"), "results": data.get("results")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "SetLightingProperty":
                            output_content_dict = {"status": "success", "tool_message": data.get("message", f"Lighting property {data.get('property_name')} set."), "property_name": data.get("property_name"), "new_value_set": data.get("new_value_set")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": f"Lighting property {data.get('property_name')} set."})
                        elif original_tool_name == "SetWorkspaceProperty":
                            output_content_dict = {"status": "success", "tool_message": data.get("message", f"Workspace property {data.get('property_name')} set."), "property_name": data.get("property_name"), "new_value_set": data.get("new_value_set")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": f"Workspace property {data.get('property_name')} set."})
                        elif original_tool_name == "TeleportPlayerToPlace":
                            output_content_dict = {"status": "success", "tool_message": data.get("message", "Teleport initiated."), "players_teleported_paths": data.get("players_teleported_paths"), "place_id": data.get("place_id"), "job_id": data.get("job_id"), "teleport_data_sent": data.get("teleport_data_sent")}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message", "Teleport initiated.")})
                        elif original_tool_name == "TweenProperties":
                            output_content_dict = {"status": "success", "tool_message": data.get("message"), "instance_path": data.get("instance_path"), "duration": data.get("duration"), "easing_style_used": data.get("easing_style_used"), "easing_direction_used": data.get("easing_direction_used"), "properties_goal_summary": str(data.get("properties_goal"))}
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message")})
                        elif original_tool_name == "RunCode":
                            output_content_dict = {
                                "status": "success",
                                "tool_message": data.get("message", "Code executed.") + " The command has been processed and its output is included.",
                                "explicit_completion_notice": "This RunCode command is now complete. Do not call it again unless the user makes a new request to run code.",
                                "return_values": data.get("return_values"),
                                "output": data.get("output")
                            }
                            ConsoleFormatter.print_tool_result({"status": "success", "tool_name": original_tool_name, "processed_message": data.get("message", "RunCode processed.")})
                        else: # Default handler for tools that successfully return JSON but don't have specific parsing
                            output_content_dict = {"status": "success", "data_from_tool": data}
                            ConsoleFormatter.print_tool_result(output_content_dict)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing expected JSON for successful {original_tool_name} result: {e}. Content was: {inner_text}")
                        output_content_dict = {"status": "error", "parsing_error_in_python": str(e), "raw_content": inner_text, "tool_message": "Tool returned success, but its JSON payload was malformed."}
                        ConsoleFormatter.print_tool_error(output_content_dict)

            elif "error" in mcp_response: # Error from the MCP server itself (e.g. tool not found by MCP)

                error_data = mcp_response["error"]
                output_content_dict = {"status": "error", "details": error_data}
                ConsoleFormatter.print_tool_error(error_data) # Pass the whole error_data dict
            else: # Unexpected response from MCP server
                output_content_dict = {"status": "unknown_response", "raw": mcp_response}
                ConsoleFormatter.print_tool_error(output_content_dict)
        except MCPConnectionError as e: # Raised by mcp_client.send_request
            logger.error(f"MCP Connection Error during tool '{original_tool_name}' (mcp: '{mcp_tool_name}'): {e}")
            output_content_dict = {"status": "error", "details": f"MCP Connection Error: {e}"}
            ConsoleFormatter.print_tool_error(output_content_dict) # Show error in console
        except asyncio.TimeoutError: # From mcp_client.send_request (if it re-raises it)
            logger.error(f"Tool call '{original_tool_name}' (mcp: '{mcp_tool_name}') timed out.")
            output_content_dict = {"status": "error", "details": "Request to Roblox Studio timed out."}
            ConsoleFormatter.print_tool_error(output_content_dict)
        except Exception as e: # Other unexpected errors
            logger.error(f"Unhandled error executing tool '{original_tool_name}' (mcp: '{mcp_tool_name}'): {e}", exc_info=True)
            output_content_dict = {"status": "error", "details": f"An internal broker error occurred: {e}"}
            ConsoleFormatter.print_tool_error(output_content_dict)

        # II.2. Return a dictionary using the original tool name
        return {"name": original_tool_name, "response": output_content_dict}
