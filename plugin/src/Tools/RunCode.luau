local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types) -- Assuming Types.ToolFunction expects the CallToolResult-like table
local HttpService = game:GetService("HttpService")

-- Keep existing helper functions: getTableType, serializeTable, deepClone, toStrTable
-- as they are used for constructing the output string, not the final return structure.
local function getTableType(arg)
	local hasArray = false
	local hasTable = false
	for key, _value in arg do
		if typeof(key) == "number" then
			hasArray = true
		else
			hasTable = true
		end
		if hasArray and hasTable then
			break
		end
	end
	return hasArray, hasTable
end

local function serializeTable(arg)
	if typeof(arg) == "table" then
		local _, isTable = getTableType(arg)
		local newArg = {}
		for key, value in arg do
			local newKey = serializeTable(key)
			newArg[if isTable then tostring(newKey) else newKey] = serializeTable(value)
		end
		return newArg
	elseif type(arg) == "userdata" then
		return tostring(arg) or "UNABLE_TO_SERIALIZE"
	end
	return arg
end

local function deepClone(t, cache)
    cache = cache or {} -- Ensure cache is initialized
	local clone = {}
	for key, value in t do
		local newKey = key
		if typeof(key) == "table" then
			if not cache[key] then
                cache[key] = {} -- Placeholder to break cycles for keys
				cache[key] = deepClone(key, cache)
			end
			newKey = cache[key]
		end

		local newValue = value
		if typeof(value) == "table" then
			if not cache[value] then
                cache[value] = {} -- Placeholder to break cycles for values
				cache[value] = deepClone(value, cache)
			end
			newValue = cache[value]
		end
		clone[newKey] = newValue
	end
	return clone
end

local function toStrTable(t: { any }): { string }
    local clonedTable = {}
    -- Wrap deepClone in a pcall in case of complex userdata that can't be cached well or other issues
    local cloneSuccess, result = pcall(deepClone, t, {})
    if cloneSuccess then
        clonedTable = result
    else
        -- Fallback for cloning failure: try tostring on elements directly
        local strTableMinimal = table.create(#t)
        for i, arg_elem in ipairs(t) do
            strTableMinimal[i] = tostring(arg_elem)
        end
        return strTableMinimal
    end

	local strTable = table.create(#clonedTable)
	for i, arg_elem in ipairs(clonedTable) do -- Use ipairs for array part
		local serializedArg = serializeTable(arg_elem)
		strTable[i] = if typeof(serializedArg) == "table"
			then HttpService:JSONEncode(serializedArg)
			else tostring(serializedArg) -- Ensure it's a string
		end
	end
	return strTable
end


-- Modified runCodeWithOutput to return both output string and an error flag
local function runCodeWithOutput(command: string): (string, boolean)
	local output_parts = {} -- Store parts of output to join later
    local anErrorOccurred = false

	local function addToOutput(header: string, ...) do
        local packedArgs = table.pack(...)
        if packedArgs.n == 0 then -- Handle calls like print() with no arguments
            table.insert(output_parts, header .. "\n")
            return
        end
		local strResults = toStrTable(packedArgs) -- Pass the packed table directly
		table.insert(output_parts, header .. " " .. table.concat(strResults, "\t") .. "\n")
	end

	local function executeCode()
		local chunk, loadErr = loadstring(command)
        if not chunk then
            anErrorOccurred = true
            addToOutput("[LOADSTRING ERROR]", loadErr or "Unknown loadstring error")
            return nil -- Explicitly return nil as chunk is nil
        end

		local chunkfenv = getfenv(chunk)

		local oldPrint = chunkfenv.print or print
		chunkfenv.print = function(...)
			if oldPrint then oldPrint(...) end
			addToOutput("[OUTPUT]", ...)
		end

		local oldWarn = chunkfenv.warn or warn
		chunkfenv.warn = function(...)
			if oldWarn then oldWarn(...) end
			addToOutput("[WARNING]", ...)
		end


		local oldError = chunkfenv.error or error
		local function customErrorForChunk(...)
			anErrorOccurred = true
			addToOutput("[ERROR]", ...)
            -- No need to call oldError here as it would halt execution;
            -- The error is captured by addToOutput.
            -- Unlike the original, we don't call the actual error() here to allow script to continue
            -- and capture more output if possible, or let pcall handle the halt.
            -- For true halting behavior, the pcall below is the primary catcher.
		end
		chunkfenv.error = customErrorForChunk

		-- Execute the chunk
        local success, results = pcall(chunk) -- Use pcall here for safety

        if not success then
            anErrorOccurred = true
            addToOutput("[RUNTIME ERROR]", results) -- 'results' is the error message here
            return -- Stop further processing of results
        end

        -- Process actual return values if pcall was successful
		if results and type(results) == "table" and results.n ~= nil and results.n > 0 then -- Check if it's a packed table from pcall
            local unpackedResults = {}
            for i = 1, results.n do
                table.insert(unpackedResults, results[i])
            end
			addToOutput("[RETURNED]", table.unpack(unpackedResults, 1, results.n))
		end

	end

	-- The main pcall for executeCode itself (though internal execution is also pcalled now)
	local overallOk, overallErrorMessage = pcall(executeCode)
	if not overallOk then
		anErrorOccurred = true
		addToOutput("[CRITICAL EXECUTION ERROR]", overallErrorMessage)
	end

	return table.concat(output_parts, ""), anErrorOccurred
end

-- Modified handleRunCode to accept args directly and return the correct table structure
local function handleRunCode(args: Types.RunCodeArgs): Types.CallToolResultTable
	-- The 'args' here is toolInputArgs from Main.server.luau,
    -- which for RunCode is expected to be { command = "string" }
	if type(args.command) ~= "string" then
		-- This case should ideally be caught by argument validation in Main.server.luau based on JSON schema
		return {
			content = {{ type = "text", text = "Error: RunCode command argument is missing or not a string." }},
			isError = true
		}
	end

	local outputString, hasError = runCodeWithOutput(args.command)

	return {
		content = {{ type = "text", text = outputString }},
		isError = hasError
	}
end

return handleRunCode -- Ensure this matches the expected Type.ToolFunction signature
