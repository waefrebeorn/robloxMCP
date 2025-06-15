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
    print("[MCP Diagnostics] Attempting to load tool functions...")
    local toolModules = {}

    print("[MCP Diagnostics] Main (script:FindFirstAncestor(\"MCPStudioPlugin\")) is: " .. tostring(Main))
    if Main then
        print("[MCP Diagnostics] Main.Tools is: " .. tostring(Main.Tools))
    else
        print("[MCP Diagnostics] Main is nil, cannot access Main.Tools.")
    end

    if script:FindFirstChild("Tools") then
        print("[MCP Diagnostics] script.Tools is: " .. tostring(script.Tools) .. " (" .. script.Tools:GetFullName() .. ")")
    else
        print("[MCP Diagnostics] script.Tools is: nil (not found as a child of script)")
    end


    local toolsFolder = Main and Main.Tools or script.Tools -- Check Main before Main.Tools
    print("[MCP Diagnostics] Determined toolsFolder: " .. tostring(toolsFolder) .. (toolsFolder and (" (" .. toolsFolder:GetFullName() .. ")") or ""))

    if toolsFolder then
        print("[MCP Diagnostics] Tools folder found. Iterating children...")
        local children = toolsFolder:GetChildren()
        print("[MCP Diagnostics] Number of children in toolsFolder: " .. tostring(#children))
        for i, toolModuleScript in ipairs(children) do
            print("[MCP Diagnostics] Processing child #" .. i .. ": " .. toolModuleScript.Name .. ", ClassName: " .. toolModuleScript.ClassName)
            if toolModuleScript:IsA("ModuleScript") then
                print("[MCP Diagnostics] Attempting to require ModuleScript: " .. toolModuleScript.Name)
                local success, toolFunctionOrError = pcall(require, toolModuleScript)
                if success and type(toolFunctionOrError) == "function" then
                    print("[MCP Diagnostics] Successfully loaded tool: " .. toolModuleScript.Name)
                    toolModules[toolModuleScript.Name] = toolFunctionOrError
                elseif success then
                    print("[MCP Diagnostics] Error loading tool " .. toolModuleScript.Name .. ": require succeeded but returned type " .. type(toolFunctionOrError) .. " instead of function.")
                else
                    print("[MCP Diagnostics] Error loading tool " .. toolModuleScript.Name .. " (pcall failed): " .. tostring(toolFunctionOrError))
                end
            else
                print("[MCP Diagnostics] Child " .. toolModuleScript.Name .. " is not a ModuleScript. Skipping.")
            end
        end
    else
        print("[MCP Diagnostics] Error: Tools folder not found or resolved to nil.")

    end

    local loadedToolNames = {}
    for name, _ in pairs(toolModules) do
        table.insert(loadedToolNames, name)
    end

    print("[MCP Diagnostics] Finished loading tools. Loaded tool names: {" .. table.concat(loadedToolNames, ", ") .. "}")

    return toolModules
end

local toolFunctions = loadToolFunctions()
-- For debugging, print loaded tools
-- for name, _ in pairs(toolFunctions) do
-- log("[MCP] Registered tool function: " .. name) -- Keep this commented or use print for consistency
-- end
-- for name, _ in pairs(toolFunctions) do
-- log("[MCP] Registered tool function: " .. name) -- Keep this commented or use print for consistency
-- end

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
			log("[MCP] Error: Failed to decode JSON message or invalid format: " .. (body or message))
			return
		end

		local id = body.id
		if not id or type(id) ~= "string" then
			log("[MCP] Error: Message ID is missing or not a string in body: ", body)
			return
		end

		local responseSent = false
		local function sendResponseOnce(responseCallToolResultTable, originalToolNameForResponse) -- Removed isError param as it's in the table
			if not responseSent then
				responseSent = true

				-- responseCallToolResultTable is the Lua table like {content={{type="text",...}}, isError=...}
				-- This is what needs to be JSON encoded and sent as the 'response' field of the body to /response

				local successEncode, resultOrError = pcall(HttpService.JSONEncode, HttpService, responseCallToolResultTable)
				local jsonEncodedCallToolResultStr

				if not successEncode then
					-- resultOrError is the error message from the failed JSONEncode
					local errorDetail = "Plugin internal error: Failed to JSON encode the tool's result structure: " .. tostring(resultOrError)
					log("[MCP] CRITICAL: " .. errorDetail)
					local errorCtResultTable = ToolHelpers.FormatErrorResult(errorDetail)
					-- Safely encode the new error table (this should ideally not fail if FormatErrorResult is simple)
					local finalErrorJsonSuccess, finalErrorJson = pcall(HttpService.JSONEncode, HttpService, errorCtResultTable)
					if finalErrorJsonSuccess then
						jsonEncodedCallToolResultStr = finalErrorJson
					else
						-- If even encoding the fallback error fails, create a very basic JSON string manually
						log("[MCP] CRITICAL: Failed to encode even the fallback error message! " .. tostring(finalErrorJson))
						jsonEncodedCallToolResultStr = "{\"content\":[{\"type\":\"text\",\"text\":\"Plugin critical error: Failed to construct JSON response.\"}],\"isError\":true}"
					end
				else
					-- resultOrError is the successfully encoded JSON string
					jsonEncodedCallToolResultStr = resultOrError
				end

				local payloadForRust = { -- This is the body for the POST to the /response endpoint
					id = id, -- MCP Transaction ID, captured from the incoming message
					response = jsonEncodedCallToolResultStr -- This is the JSON string of the CallToolResult-like table
				}

				local finalJsonToSend, finalEncodeErr = pcall(HttpService.JSONEncode, HttpService, payloadForRust)

				if not finalEncodeErr then
					log("[MCP] Sending response: " .. finalJsonToSend)
					client:Send(finalJsonToSend)
				else
					log("[MCP] CRITICAL: Failed to encode the final payload for /response: " .. tostring(finalJsonToSend) .. " for original message id: " .. id)
					-- Fallback for critical double encoding failure (extremely unlikely if first encode worked)
					local criticalErrorCtResult = ToolHelpers.FormatErrorResult("Plugin critical error: Failed to construct final JSON response.")
					local criticalErrorJson = HttpService:JSONEncode(criticalErrorCtResult)
					client:Send(HttpService:JSONEncode({ id = id, response = criticalErrorJson }))
				end
			end
		end

		local taskArgs = body.args
		if not taskArgs or type(taskArgs) ~= "table" then
			local errorResultTable = ToolHelpers.FormatErrorResult("Task arguments (body.args) are missing or not a table.")
			sendResponseOnce(errorResultTable, "unknown_task")
			return
		end

		local toolNameForExecution -- This is the name of the Luau script, e.g., "CreateInstance", "RunCode"
		local toolInputArgs = {} -- Arguments to pass to the Luau tool function
        local originalToolNameToRespondWith -- This is the name Gemini called, e.g. "CreateInstance"

		if taskArgs.ExecuteLuauByName and type(taskArgs.ExecuteLuauByName) == "table" then
			toolNameForExecution = taskArgs.ExecuteLuauByName.tool_name
            originalToolNameToRespondWith = toolNameForExecution -- For Luau tools, this is the same.
			local argumentsJson = taskArgs.ExecuteLuauByName.arguments_json

			if type(toolNameForExecution) ~= "string" or string.len(toolNameForExecution) == 0 then
				local errorResultTable = ToolHelpers.FormatErrorResult("ExecuteLuauByName: 'tool_name' is missing or invalid.")
				sendResponseOnce(errorResultTable, toolNameForExecution or "ExecuteLuauByName")
				return
			end
			if type(argumentsJson) ~= "string" then
				local errorResultTable = ToolHelpers.FormatErrorResult("ExecuteLuauByName: 'arguments_json' is missing or not a string.")
				sendResponseOnce(errorResultTable, toolNameForExecution)
				return
			end

			local decodeSuccess, decodedJsonArgs = pcall(HttpService.JSONDecode, HttpService, argumentsJson)
			if decodeSuccess then
				if type(decodedJsonArgs) == "table" then
					toolInputArgs = decodedJsonArgs
				else
					-- If JSON decoded to a non-table (e.g. just a string or number), wrap it if necessary or handle error
					log("[MCP] Warning: arguments_json for " .. toolNameForExecution .. " decoded to a non-table type: " .. type(decodedJsonArgs) .. ". Using as is or wrapping might be needed.")
					toolInputArgs = decodedJsonArgs -- Assuming tool can handle it or it's a simple value call
				end
			else
				log("[MCP] Error: Failed to JSONDecode arguments_json for tool " .. toolNameForExecution .. ": " .. tostring(decodedJsonArgs)) -- decodedJsonArgs is error msg here
				local errorResultTable = ToolHelpers.FormatErrorResult("ExecuteLuauByName: Failed to decode 'arguments_json': " .. tostring(decodedJsonArgs))
				sendResponseOnce(errorResultTable, toolNameForExecution)
				return
			end
			log("[MCP] Task Type: ExecuteLuauByName for tool: " .. toolNameForExecution)

		elseif taskArgs.RunCommand and type(taskArgs.RunCommand) == "table" then
			-- This case is for the Rust `run_command` tool, which we map to `RunCode.luau`
			toolNameForExecution = "RunCode"
            originalToolNameToRespondWith = "run_command" -- Gemini called "run_command" (or the Python agent mapped it)
			toolInputArgs = { command = taskArgs.RunCommand.command }
			if type(toolInputArgs.command) ~= "string" then
				local errorResultTable = ToolHelpers.FormatErrorResult("RunCommand: 'command' is missing or not a string.")
				sendResponseOnce(errorResultTable, originalToolNameToRespondWith)
				return
			end
			log("[MCP] Task Type: RunCommand, mapped to Luau tool: " .. toolNameForExecution)

		elseif taskArgs.InsertModel and type(taskArgs.InsertModel) == "table" then
			-- This case is for the Rust `insert_model` tool, which we map to `InsertModel.luau`
			toolNameForExecution = "InsertModel"
            originalToolNameToRespondWith = "insert_model" -- Gemini called "insert_model"
			toolInputArgs = { query = taskArgs.InsertModel.query }
			if type(toolInputArgs.query) ~= "string" then
				local errorResultTable = ToolHelpers.FormatErrorResult("InsertModel: 'query' is missing or not a string.")
				sendResponseOnce(errorResultTable, originalToolNameToRespondWith)
				return
			end
			log("[MCP] Task Type: InsertModel, mapped to Luau tool: " .. toolNameForExecution)
		else
			log("[MCP] Error: Unrecognized task structure in body.args: ", taskArgs)
			local errorResultTable = ToolHelpers.FormatErrorResult("Unrecognized task structure in body.args.")
			sendResponseOnce(errorResultTable, "unknown_task")
			return
		end

		if not toolNameForExecution then
			local errorResultTable = ToolHelpers.FormatErrorResult("Could not determine tool name for execution from task arguments.")
			sendResponseOnce(errorResultTable, originalToolNameToRespondWith or "unknown_tool")
			return
		end

        local toolFunc = toolFunctions[toolNameForExecution]
		if not toolFunc then
			local errorResultTable = ToolHelpers.FormatErrorResult("Tool function not found in toolFunctions map: " .. toolNameForExecution)
			sendResponseOnce(errorResultTable, originalToolNameToRespondWith)
			return
		end

		local recording = ChangeHistoryService:TryBeginRecording("StudioMCP - " .. toolNameForExecution)
		local success, result = pcall(toolFunc, toolInputArgs or {})

		if success then
			if type(result) == "table" and result.content then -- Assuming 'result' is the CallToolResult-like table
				sendResponseOnce(result, originalToolNameToRespondWith)
			else
				log("[MCP] Error: Tool " .. toolNameForExecution .. " returned unexpected result format: " .. tostring(result))
				local errorResultTable = ToolHelpers.FormatErrorResult("Tool " .. toolNameForExecution .. " returned an unexpected result format.")
				sendResponseOnce(errorResultTable, originalToolNameToRespondWith)
			end
		else
			log("[MCP] Error executing tool " .. toolNameForExecution .. ": " .. tostring(result))
			local errorResultTable = ToolHelpers.FormatErrorResult("Internal error executing tool " .. toolNameForExecution .. ": " .. tostring(result))
			sendResponseOnce(errorResultTable, originalToolNameToRespondWith)
		end

		if recording then
			ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
		end
		log("[MCP] Handled request for original tool: " .. (originalToolNameToRespondWith or "unknown") .. ", executed as Luau: " .. toolNameForExecution)
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
