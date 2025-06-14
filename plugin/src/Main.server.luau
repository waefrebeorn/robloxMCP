local Main = script:FindFirstAncestor("MCPStudioPlugin")
local MockWebSocketService = require(Main.MockWebSocketService)
local Types = require(Main.Types)

local ChangeHistoryService = game:GetService("ChangeHistoryService")
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local StudioService = game:GetService("StudioService")

local URI = "http://localhost:44755"
local RECEIVE_ENDPOINT = "/request"
local SEND_ENDPOINT = "/response"

if RunService:IsRunning() then
	return
end

local old_warn = warn
local function log(...)
	if false then
		old_warn(...)
	end
end

local function fetchBuiltinTools()
	local tools = {}
	for _, tool in Main.Tools:GetChildren() do
		if tool:IsA("ModuleScript") then
			table.insert(tools, require(tool) :: Types.ToolFunction)
		end
	end
	return tools -- This function is no longer used directly for dispatch
end

-- New: Load tools into a dictionary for named dispatch
local function loadToolFunctions()
    local toolModules = {}
    local toolsFolder = Main.Tools or script.Tools -- Prefer Main.Tools if defined, else script.Tools

    -- Existing tools (assuming they follow the new execute(args) pattern or are adapted)
    if toolsFolder:FindFirstChild("InsertModel") then
        toolModules["InsertModel"] = require(toolsFolder.InsertModel)
    end
    if toolsFolder:FindFirstChild("RunCode") then
        toolModules["run_code"] = require(toolsFolder.RunCode) -- Gemini uses 'run_code'
    end
    if toolsFolder:FindFirstChild("GetSelection") then
        toolModules["get_selection"] = require(toolsFolder.GetSelection) -- Gemini uses 'get_selection'
    end
    -- Note: GetProperties and SetProperties are removed as per previous subtasks

    -- Add new Phase 1 tools
    toolModules["create_instance"] = require(toolsFolder.CreateInstance)
    toolModules["set_instance_properties"] = require(toolsFolder.SetInstanceProperties)
    toolModules["get_instance_properties"] = require(toolsFolder.GetInstanceProperties)
    toolModules["call_instance_method"] = require(toolsFolder.CallInstanceMethod)
    toolModules["delete_instance"] = require(toolsFolder.DeleteInstance)
    toolModules["select_instances"] = require(toolsFolder.SelectInstances)
    toolModules["run_script"] = require(toolsFolder.RunScript)
    toolModules["set_lighting_property"] = require(toolsFolder.SetLightingProperty)
    toolModules["get_lighting_property"] = require(toolsFolder.GetLightingProperty)
    toolModules["play_sound_id"] = require(toolsFolder.PlaySoundId)
    toolModules["set_workspace_property"] = require(toolsFolder.SetWorkspaceProperty)
    toolModules["get_workspace_property"] = require(toolsFolder.GetWorkspaceProperty)
    toolModules["kick_player"] = require(toolsFolder.KickPlayer)
    toolModules["create_team"] = require(toolsFolder.CreateTeam)

    -- Add new Phase 2 tools
    toolModules["tween_properties"] = require(toolsFolder.TweenProperties)
    toolModules["add_tag"] = require(toolsFolder.AddTag)
    toolModules["remove_tag"] = require(toolsFolder.RemoveTag)
    toolModules["get_instances_with_tag"] = require(toolsFolder.GetInstancesWithTag)
    toolModules["has_tag"] = require(toolsFolder.HasTag)
    toolModules["compute_path"] = require(toolsFolder.ComputePath)
    toolModules["create_proximity_prompt"] = require(toolsFolder.CreateProximityPrompt)
    toolModules["get_product_info"] = require(toolsFolder.GetProductInfo)
    toolModules["prompt_purchase"] = require(toolsFolder.PromptPurchase)
    toolModules["add_debris_item"] = require(toolsFolder.AddDebrisItem)

    -- Add new Phase 3 tools (UI & Input)
    toolModules["create_gui_element"] = require(toolsFolder.CreateGuiElement)
    toolModules["get_mouse_position"] = require(toolsFolder.GetMousePosition)
    toolModules["get_mouse_hit_cframe"] = require(toolsFolder.GetMouseHitCFrame)
    toolModules["is_key_down"] = require(toolsFolder.IsKeyDown)
    toolModules["is_mouse_button_down"] = require(toolsFolder.IsMouseButtonDown)

    -- Add new Phase 4 tools (DataStores)
    toolModules["save_data"] = require(toolsFolder.SaveData)
    toolModules["load_data"] = require(toolsFolder.LoadData)
    toolModules["increment_data"] = require(toolsFolder.IncrementData)
    toolModules["remove_data"] = require(toolsFolder.RemoveData)

    -- Add new Phase 5 tools
    toolModules["teleport_player_to_place"] = require(toolsFolder.TeleportPlayerToPlace)
    toolModules["get_teleport_data"] = require(toolsFolder.GetTeleportData)
    toolModules["send_chat_message"] = require(toolsFolder.SendChatMessage)
    toolModules["filter_text_for_player"] = require(toolsFolder.FilterTextForPlayer)
    toolModules["create_text_channel"] = require(toolsFolder.CreateTextChannel)
    -- http_request tool removed
    toolModules["get_teams"] = require(toolsFolder.GetTeams)
    toolModules["get_players_in_team"] = require(toolsFolder.GetPlayersInTeam)
    toolModules["load_asset_by_id"] = require(toolsFolder.LoadAssetById)
    toolModules["get_children_of_instance"] = require(toolsFolder.GetChildrenOfInstance)
    toolModules["get_descendants_of_instance"] = require(toolsFolder.GetDescendantsOfInstance)
    toolModules["find_first_child_matching"] = require(toolsFolder.FindFirstChildMatching)

    return toolModules
end

local toolFunctions = loadToolFunctions()

local function connectWebSocket()
	local client = MockWebSocketService:CreateClient(URI)
	client:SetReceiveEndpoint(RECEIVE_ENDPOINT)
	client:SetSendEndpoint(SEND_ENDPOINT)

	client.Opened:Once(function()
		log("[MCP] Connection opened")
	end)

	client.Closed:Once(function()
		log("[MCP] Connection closed")
	end)

	client.MessageReceived:Connect(function(message)
		log("[MCP] Message received")

		local decodedSuccess, body = pcall(HttpService.JSONDecode, HttpService, message)
		if not decodedSuccess or not body or type(body) ~= "table" then
			log("[MCP] Error: Failed to decode JSON message or invalid format: " .. (body or message) )
			-- Cannot send ID-specific error if ID cannot be parsed.
			return
		end

		local id = body.id
		local toolName = body.tool_name -- Assuming the request contains 'tool_name'
		local toolArgs = body.arguments -- Assuming the request contains 'arguments' for the tool

		if not id or type(id) ~= "string" then
			log("[MCP] Error: Message ID is missing or not a string.")
			return
		end

		local responseSent = false
		local function sendResponseOnce(responseContent, isError)
			if not responseSent then
				responseSent = true
				local responseTable = {
					id = id,
					result = { -- Adhering to a structure similar to Gemini's ToolResult/FunctionResponse
                        name = toolName or "unknown_tool",
                        response = responseContent -- This is the content from the tool (already JSON stringified by ToolHelpers)
                    }
				}
                if isError then
                    responseTable.result.response = HttpService:JSONEncode({ -- Ensure error content is also JSON
                        error = { message = responseContent } -- Simple error structure
                    })
                end

				local finalResponseJson, encodeErr = pcall(HttpService.JSONEncode, HttpService, responseTable)
				if not encodeErr then
					log("[MCP] Sending response: " .. finalResponseJson)
					client:Send(finalResponseJson)
				else
					log("[MCP] CRITICAL: Failed to encode final response: " .. tostring(encodeErr))
                    -- Fallback if even the error response can't be formed
                    client:Send(HttpService:JSONEncode({id=id, result={name=toolName or "unknown_tool", response=HttpService:JSONEncode({error={message="Failed to encode server response."}})}}))
				end
			end
		end

		if not toolName or type(toolName) ~= "string" then
			sendResponseOnce("Tool name not provided or invalid.", true)
			return
		end

		local toolFunc = toolFunctions[toolName]
		if not toolFunc then
			sendResponseOnce("Tool not found: " .. toolName, true)
			return
		end

		local recording = ChangeHistoryService:TryBeginRecording("StudioMCP - " .. toolName)

		local success, result = pcall(toolFunc, toolArgs or {}) -- Pass empty table if no args

		if success then
            -- result should be { content = "json_string", isError = boolean } from ToolHelpers
            if type(result) == "table" and result.content then
                if result.isError then
                    sendResponseOnce(result.content, true) -- Error content is already JSON from ToolHelpers.FormatErrorResult
                else
                    sendResponseOnce(result.content, false) -- Success content is already JSON from ToolHelpers.FormatSuccessResult
                end
            else
                -- Should not happen if tools use ToolHelpers correctly
                log("[MCP] Error: Tool returned unexpected result format: " .. tostring(result))
                sendResponseOnce("Tool " .. toolName .. " returned an unexpected result format.", true)
            end
		else
			-- Error from pcall itself (error within toolFunc before it formats its own error, or error in require)
			log("[MCP] Error executing tool " .. toolName .. ": " .. tostring(result))
			sendResponseOnce("Internal error executing tool " .. toolName .. ": " .. tostring(result), true)
		end

		if recording then
			ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
		end
		log("[MCP] Handled request for tool: " .. toolName)
	end)

	return client
end

local function getButtonImage()
	local ok, response = pcall(function()
		return StudioService:GetClassIcon("PackageLink").Image
	end)
	return ok and response or "rbxasset://textures/ui/GuiImagePlaceholder.png"
end

local currentClient: MockWebSocketService.MockWebSocketClient? = connectWebSocket() -- nil for default off
print("The MCP Studio plugin is ready for prompts.")

local toolbar = plugin:CreateToolbar("MCP")
local toggleButton = toolbar:CreateButton("Toggle MCP", "Toggle connection to the server", getButtonImage())
toggleButton.ClickableWhenViewportHidden = true
toggleButton:SetActive(currentClient ~= nil)

toggleButton.Click:Connect(function()
	if not currentClient then
		currentClient = connectWebSocket()
		print("The MCP Studio plugin is ready for prompts.")
	else
		currentClient:Close()
		currentClient = nil
		print("The MCP Studio plugin is stopped.")
	end
end)
