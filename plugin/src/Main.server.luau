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

	client.MessageReceived:Connect(function(message: string) -- Ensured valid type annotation / corrected if malformed
		log("[MCP] Message received")


		-- Check for empty or whitespace-only message
		if message == nil or string.match(message, "^%s*$") then
			-- More subdued log, not an "Error"
			print(("[MCP Diagnostic] Received empty or whitespace-only message, ignoring. Raw message: [%s]"):format(tostring(message)))
			return
		end

		local loadedFunction, loadError = loadstring(message)
		if not loadedFunction then
			print(("[MCP Error] Failed to load incoming message string as Luau code. Load Error: %s. Original raw message was: [%s]"):format(tostring(loadError), message))
			-- Potentially send a formatted error response back to the server if expected
			-- For now, just log and return, as the message is fundamentally unparsable as code.
			-- local errResponse = ToolHelpers.FormatErrorResult("Plugin Error: Incoming message is not valid Luau code: " .. tostring(loadError))
			-- sendResponseOnce(errResponse, "unknown_malformed_request") -- Need to define sendResponseOnce to handle this scenario if it can't get an ID
			return
		end

		local successCall, resultOrError = pcall(loadedFunction)
		if not successCall then
			print(("[MCP Error] Failed to execute compiled Luau message. Execution Error: %s. Original raw message was: [%s]"):format(tostring(resultOrError), message))
			-- Potentially send a formatted error response
			return
		end

		local body = resultOrError
		if type(body) ~= "table" then
			print(("[MCP Error] Executed Luau message did not return a table. Returned type: %s. Original raw message was: [%s]"):format(type(body), message))
			-- Potentially send a formatted error response

			return
		end

		local id = body.id
		if not id or type(id) ~= "string" then
			print("[MCP] Error: Message ID is missing or not a string in body: ", body)
			return
		end

		local responseSent = false
		local function sendResponseOnce(responseCallToolResultTable, originalToolNameForResponse)
			if not responseSent then
				responseSent = true
				print("[MCP Diagnostics] sendResponseOnce: Attempting to serialize responseCallToolResultTable. Original Tool Name: " .. tostring(originalToolNameForResponse))
				-- Optional: safeDeepPrint(responseCallToolResultTable) for debugging input table

				local responseLuauString, responseSerialError = ToolHelpers.TableToLuauString(responseCallToolResultTable)

				if responseSerialError then
					print(("[MCP CRITICAL] Failed to serialize tool's direct result table for tool '%s'. Error: %s"):format(tostring(originalToolNameForResponse), tostring(responseSerialError)))
					local fallbackErrorTable = ToolHelpers.FormatErrorResult("Plugin critical error: Failed to serialize tool's result: " .. tostring(responseSerialError))

					-- Attempt to serialize the fallback error table itself
					local fallbackLuauString, fallbackSerialError = ToolHelpers.TableToLuauString(fallbackErrorTable)
					if fallbackSerialError then
						print(("[MCP CRITICAL] Failed to serialize even the fallback error table for tool '%s'. Fallback Error: %s"):format(tostring(originalToolNameForResponse), tostring(fallbackSerialError)))
						-- Manually craft a Luau string representing the innermost error, ensuring it's a valid "return ..." statement
						responseLuauString = "return { content={{type='text',text='Plugin critical error: Result serialization failed catastrophically.'}}, isError=true }"
					else
						responseLuauString = fallbackLuauString
					end
				end


				-- responseLuauString now holds a string like "return {content=..., isError=...}"

				local outerPayloadTable = {
					id = id, -- Captured from the incoming request's parsed body
					response = responseLuauString -- This is a string that starts with "return ..."
				}

				print("[MCP Diagnostics] sendResponseOnce: Attempting to serialize outerPayloadTable.")
				-- Optional: safeDeepPrint(outerPayloadTable) for debugging

				local finalLuauStringToSend, outerSerialError = ToolHelpers.TableToLuauString(outerPayloadTable)

				if outerSerialError then
					print(("[MCP CRITICAL] Failed to serialize the final outer payload for ID '%s'. Error: %s"):format(tostring(id), tostring(outerSerialError)))


					-- Construct the ultimate fallback Luau string manually
					-- The 'response' field needs to be a string that itself is a Luau return statement.
					local ultimateFallbackResponseLuauStr, ultimateFallbackErr = ToolHelpers.TableToLuauString(
						ToolHelpers.FormatErrorResult("PLUGIN MELTDOWN: Final payload serialization failed: " .. tostring(outerSerialError))
					)
					if ultimateFallbackErr then
						-- If even serializing this simple error table fails, use a hardcoded string for the inner response
						ultimateFallbackResponseLuauStr = "return {content={{type='text', text='PLUGIN MELTDOWN AND UNABLE TO SERIALIZE BASIC ERROR'}}, isError=true}"
					end


					local idStringForFormatInFallback
					if type(id) == "string" then
						idStringForFormatInFallback = string.format("%q", id)
					elseif type(id) == "number" then
						idStringForFormatInFallback = tostring(id)
					elseif type(id) == "boolean" then
						idStringForFormatInFallback = tostring(id)
					elseif id == nil then
						idStringForFormatInFallback = "nil"
					else
						-- Fallback for unexpected ID types, ensuring it's a valid string in the output table
						idStringForFormatInFallback = string.format("%q", "INVALID_ID_TYPE:" .. tostring(id))
					end

					-- ToolHelpers.TableToLuauString(ultimateFallbackResponseLuauStr) correctly makes
					-- the "return..." string into a string literal like ""return {...}""
					finalLuauStringToSend = string.format("return { id = %s, response = %s }",
						idStringForFormatInFallback,
						ToolHelpers.TableToLuauString(ultimateFallbackResponseLuauStr)
					)

				end

				print("[MCP] Sending response (as Luau code string): " .. finalLuauStringToSend)
				client:Send(finalLuauStringToSend)
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
