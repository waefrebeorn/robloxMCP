local Main = script:FindFirstAncestor("MCPStudioPlugin")
local MockWebSocketService = require(Main.MockWebSocketService)
local Types = require(Main.Types)
local ToolHelpers = require(Main.ToolHelpers) -- Add this line

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
			print("[MCP] Error: Failed to decode JSON message or invalid format: " .. (body or message))
			return
		end

		local id = body.id
		if not id or type(id) ~= "string" then
			print("[MCP] Error: Message ID is missing or not a string in body: ", body)
			return
		end

		local responseSent = false
		local function sendResponseOnce(responseCallToolResultTable, originalToolNameForResponse) -- Removed isError param as it's in the table
			if not responseSent then
				responseSent = true

				-- responseCallToolResultTable is the Lua table like {content={{type="text",...}}, isError=...}
				-- This is what needs to be JSON encoded and sent as the 'response' field of the body to /response
				print("[MCP Diagnostics] sendResponseOnce: Attempting to encode responseCallToolResultTable. Content:")
				-- Safe deep print of the table
				local function safeDeepPrint(tbl, indent)
					indent = indent or 0
					if type(tbl) ~= "table" then
						print(string.rep("  ", indent) .. "- " .. tostring(tbl))
						return
					end
					if indent > 4 then -- Prevent excessively deep recursion for huge tables
						 print(string.rep("  ", indent) .. "- Table (depth limit reached)")
						return
					end
					for k, v in pairs(tbl) do
						print(string.rep("  ", indent) .. tostring(k) .. ":")
						safeDeepPrint(v, indent + 1)
					end
				end
				safeDeepPrint(responseCallToolResultTable)
				print("[MCP Diagnostics] sendResponseOnce: End of responseCallToolResultTable content.")

				local successEncode, resultOrError = pcall(HttpService.JSONEncode, HttpService, responseCallToolResultTable)
				local jsonEncodedCallToolResultStr

				if not successEncode then
					local errorMessageFromEncode = tostring(resultOrError) -- This is the error from JSONEncode
					print("[MCP Diagnostics] sendResponseOnce: First JSONEncode pcall FAILED. Error: " .. errorMessageFromEncode)

					local errorDetail = "Plugin internal error: Failed to JSON encode the tool's result structure: " .. errorMessageFromEncode
					-- log("[MCP] CRITICAL: " .. errorDetail) -- Keep conditional log or change to print
					print("[MCP CRITICAL] " .. errorDetail) -- Make it unconditional for now

					local errorCtResultTable = ToolHelpers.FormatErrorResult(errorDetail)
					print("[MCP Diagnostics] sendResponseOnce: Attempting to encode fallback errorCtResultTable. Content:")
					safeDeepPrint(errorCtResultTable)
					print("[MCP Diagnostics] sendResponseOnce: End of fallback errorCtResultTable content.")

					local finalErrorJsonSuccess, finalErrorJsonOrMsg = pcall(HttpService.JSONEncode, HttpService, errorCtResultTable)
					if finalErrorJsonSuccess then
						jsonEncodedCallToolResultStr = finalErrorJsonOrMsg
					else
						local fallbackEncodeErrorMessage = tostring(finalErrorJsonOrMsg)
						print("[MCP CRITICAL] Failed to encode even the fallback error message! Fallback Encode Error: " .. fallbackEncodeErrorMessage)
						jsonEncodedCallToolResultStr = "{\"content\":[{\"type\":\"text\",\"text\":\"Plugin critical error: Failed to construct final JSON response. Fallback encode error: " .. HttpService:JSONEncode(fallbackEncodeErrorMessage) .. "\"}],\"isError\":true}"
					end
				else
					print("[MCP Diagnostics] sendResponseOnce: First JSONEncode pcall SUCCEEDED.")

					jsonEncodedCallToolResultStr = resultOrError
				end

				local payloadForRust = { -- This is the body for the POST to the /response endpoint
					id = id, -- MCP Transaction ID, captured from the incoming message
					response = jsonEncodedCallToolResultStr -- This is the JSON string of the CallToolResult-like table
				}
				print("[MCP Diagnostics] sendResponseOnce: payloadForRust before second JSONEncode. Content:")
				safeDeepPrint(payloadForRust)
				print("[MCP Diagnostics] sendResponseOnce: End of payloadForRust content.")

				local successFinalEncode, resultOrErrorFinal = pcall(HttpService.JSONEncode, HttpService, payloadForRust)
				local finalJsonToSend -- This will be the string to send to client:Send

				if successFinalEncode then
					finalJsonToSend = resultOrErrorFinal
					print("[MCP Diagnostics] sendResponseOnce: Successfully encoded final payloadForRust into finalJsonToSend.")
					-- log("[MCP] Sending response: " .. finalJsonToSend) -- Keep original log call if it's preferred
					print("[MCP] Sending response: " .. finalJsonToSend) -- Or use print for visibility
					client:Send(finalJsonToSend)
				else
					-- resultOrErrorFinal is the error message from encoding payloadForRust
					local payloadEncodeErrorMsg = tostring(resultOrErrorFinal)
					print("[MCP CRITICAL] Failed to encode the final payload (payloadForRust). Error: " .. payloadEncodeErrorMsg)

					local criticalErrorMsg = "Plugin critical error: Failed to construct final JSON response. Error encoding payloadForRust: " .. payloadEncodeErrorMsg
					local criticalErrorCtResult = ToolHelpers.FormatErrorResult(criticalErrorMsg)

					local successCriticalEncode, jsonForCriticalError = pcall(HttpService.JSONEncode, HttpService, criticalErrorCtResult)
					local responseContentForAgent

					if successCriticalEncode then
						responseContentForAgent = jsonForCriticalError
					else
						local criticalEncodeErrorMsg = tostring(jsonForCriticalError)
						print("[MCP CRITICAL] Failed to encode even the criticalErrorCtResult. Error: " .. criticalEncodeErrorMsg)
						-- Manually craft the JSON string for responseContentForAgent
						responseContentForAgent = string.format("{\"content\":[{\"type\":\"text\",\"text\":\"Plugin meltdown. Cannot encode error responses. Initial error: %s. Fallback error: %s\"}],\"isError\":true}", HttpService:JSONEncode(payloadEncodeErrorMsg), HttpService:JSONEncode(criticalEncodeErrorMsg))
					end

					-- Now, construct the final payload string for the agent, ensuring this step is also safe
					local finalPayloadTable = { id = id, response = responseContentForAgent }
					local successUltimateEncode, ultimatePayloadString = pcall(HttpService.JSONEncode, HttpService, finalPayloadTable)

					if successUltimateEncode then
						client:Send(ultimatePayloadString)
					else
						local ultimateEncodeErrorMsg = tostring(ultimatePayloadString)
						print("[MCP CRITICAL] Failed to encode the absolute final fallback payload. Error: " .. ultimateEncodeErrorMsg)
						-- As a very last resort, send a completely hardcoded string if possible, though client:Send might expect specific structure
						-- This situation indicates HttpService:JSONEncode is fundamentally broken or id is problematic.
						client:Send(string.format("{\"id\":\"%s\",\"response\":\"{\\\"content\\\":[{\\\"type\\\":\\\"text\\\",\\\"text\\\":\\\"MELTDOWN (%s)\\\"}],\\\"isError\\\":true}\"}", tostring(id), HttpService:JSONEncode(ultimateEncodeErrorMsg)))
					end
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
			local argumentsLuau = taskArgs.ExecuteLuauByName.arguments_luau -- Changed from arguments_json

			if type(toolNameForExecution) ~= "string" or string.len(toolNameForExecution) == 0 then
				local errorResultTable = ToolHelpers.FormatErrorResult("ExecuteLuauByName: 'tool_name' is missing or invalid.")
				sendResponseOnce(errorResultTable, originalToolNameToRespondWith or "ExecuteLuauByName") -- Use originalToolNameToRespondWith
				return
			end
			if type(argumentsLuau) ~= "string" then -- Check argumentsLuau
				local errorResultTable = ToolHelpers.FormatErrorResult("ExecuteLuauByName: 'arguments_luau' is missing or not a string.")
				sendResponseOnce(errorResultTable, originalToolNameToRespondWith) -- Use originalToolNameToRespondWith
				return
			end

			-- Load and execute the Luau string for arguments
			local func, load_err = loadstring(argumentsLuau)
			if not func then
				print("[MCP] Error: Failed to load 'arguments_luau' string for tool " .. toolNameForExecution .. ": " .. tostring(load_err))
				local errorResultTable = ToolHelpers.FormatErrorResult("ExecuteLuauByName: Failed to load 'arguments_luau' string: " .. tostring(load_err))
				sendResponseOnce(errorResultTable, originalToolNameToRespondWith)
				return
			end

			local success_call, result_args = pcall(func)
			if not success_call then
				print("[MCP] Error: Failed to execute 'arguments_luau' function for tool " .. toolNameForExecution .. ": " .. tostring(result_args))
				local errorResultTable = ToolHelpers.FormatErrorResult("ExecuteLuauByName: Failed to execute 'arguments_luau' function: " .. tostring(result_args))
				sendResponseOnce(errorResultTable, originalToolNameToRespondWith)
				return
			end

			-- Ensure result_args is a table, as toolFunc expects it.
			-- If the loaded string returns multiple values, they are packed into a table by pcall if success_call is true and result_args is the first value.
			-- However, loadstring itself returns a function. When that function is called via pcall(func),
			-- if func returns multiple values, result_args will be the first value, and subsequent values are lost unless func itself returns a table.
			-- The requirement is that arguments_luau is a string like "return {foo='bar'}", so func() should return a table.
			if type(result_args) ~= "table" then
				print("[MCP] Warning: 'arguments_luau' function for " .. toolNameForExecution .. " did not return a table. Received type: " .. type(result_args) .. ". Wrapping in a table.")
				-- This might not be what the tool expects if the string was not "return {...}".
				-- However, tools are generally expected to receive a table of arguments.
				-- If the string was e.g. "return 123", toolInputArgs becomes {123} which is likely not desired.
				-- The contract is that arguments_luau is "return {arg1=val1, ...}"
				-- If it's not, this is an issue with how arguments_luau was constructed.
				-- For now, we will assign it directly, and tools must handle non-table args if that's a valid case,
				-- or the calling side (Rust) must ensure arguments_luau returns a table.
				-- Based on the prompt, result_args should be the Lua table.
                toolInputArgs = result_args
			else
				toolInputArgs = result_args -- This is now the Lua table
			end

			log("[MCP] Task Type: ExecuteLuauByName for tool: " .. toolNameForExecution .. " with Luau arguments")

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
			print("[MCP] Error: Unrecognized task structure in body.args: ", taskArgs)
			local errorResultTable = ToolHelpers.FormatErrorResult("Unrecognized task structure in body.args.")
			sendResponseOnce(errorResultTable, "unknown_task")
			return
		end

		if not toolNameForExecution then
			local errorResultTable = ToolHelpers.FormatErrorResult("Could not determine tool name for execution from task arguments.")
			sendResponseOnce(errorResultTable, originalToolNameToRespondWith or "unknown_tool")
			return
		end

		-- ADD DIAGNOSTICS HERE
		print("[MCP Diagnostics] MessageReceived: Attempting to find tool. toolNameForExecution = '" .. tostring(toolNameForExecution) .. "'")
		local currentToolKeys = {}
		for k, _ in pairs(toolFunctions) do
			table.insert(currentToolKeys, "'" .. tostring(k) .. "'")
		end
		print("[MCP Diagnostics] MessageReceived: Current keys in toolFunctions: {" .. table.concat(currentToolKeys, ", ") .. "}")
		-- Check explicitly if the key exists
		if toolFunctions[toolNameForExecution] then
			print("[MCP Diagnostics] MessageReceived: toolFunctions[toolNameForExecution] IS found. Type: " .. type(toolFunctions[toolNameForExecution]))
		else
			print("[MCP Diagnostics] MessageReceived: toolFunctions[toolNameForExecution] IS NIL.")
		end

		local toolFunc = toolFunctions[toolNameForExecution]
		if not toolFunc then
            -- This is the path currently taken for RunCode
			local errorResultTable = ToolHelpers.FormatErrorResult("Tool function not found in toolFunctions map: " .. tostring(toolNameForExecution))
			sendResponseOnce(errorResultTable, originalToolNameToRespondWith)
			return
		end

		local recording = ChangeHistoryService:TryBeginRecording("StudioMCP - " .. toolNameForExecution)
		local success, result = pcall(toolFunc, toolInputArgs or {})

		if success then
			if type(result) == "table" and result.content then -- Assuming 'result' is the CallToolResult-like table
				sendResponseOnce(result, originalToolNameToRespondWith)
			else
				print("[MCP] Error: Tool " .. toolNameForExecution .. " returned unexpected result format: " .. tostring(result))
				local errorResultTable = ToolHelpers.FormatErrorResult("Tool " .. toolNameForExecution .. " returned an unexpected result format.")
				sendResponseOnce(errorResultTable, originalToolNameToRespondWith)
			end
		else
			print("[MCP] Error executing tool " .. toolNameForExecution .. ": " .. tostring(result))
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
