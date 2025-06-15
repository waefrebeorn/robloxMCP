
-- Simplified RunCode.luau - Correcting syntax in toStrTable
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
-- HttpService remains removed

--[[

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
		return tostring(arg) or "UNABLE_TO_SERIALIZE" -- Fallback for userdata
	end
	return arg
end
--]]

--[[
local function deepClone(t, cache)
    cache = cache or {}
	local clone = {}
	for key, value in t do
		local newKey = key
		if typeof(key) == "table" then
			if not cache[key] then
                cache[key] = {}
				cache[key] = deepClone(key, cache)
			end
			newKey = cache[key]
		end

		local newValue = value
		if typeof(value) == "table" then
			if not cache[value] then
                cache[value] = {}
				cache[value] = deepClone(value, cache)
			end
			newValue = cache[value]
		end
		clone[newKey] = newValue
	end
	return clone
end
--]]


-- Modified toStrTable for one-level deep table string representation
local function toStrTable(t) -- t is from table.pack
    local strTable = {}
    if t and t.n then -- Check if it looks like a packed table from table.pack
        for i = 1, t.n do
            local val = t[i]
            if type(val) == "table" then
                local innerParts = {}
                for k, v in pairs(val) do
                    table.insert(innerParts, tostring(k) .. "=" .. tostring(v))
                end
                strTable[i] = "{ " .. table.concat(innerParts, ", ") .. " }"
            else
                strTable[i] = tostring(val)
            end
        end
    elseif type(t) == "table" then -- Fallback if not a packed table (e.g. if toStrTable is called with a single table directly)
        local fallbackParts = {}
        for k,v in pairs(t) do
             table.insert(fallbackParts, tostring(k) .. "=" .. tostring(v))
        end
        -- This case should return a table of strings, so wrap the single string in a table
        return {"{ " .. table.concat(fallbackParts, ", ") .. " }"}

    elseif t == nil then -- Corrected 'else if' to 'elseif'

        return {"nil"} -- Handle nil input explicitly if it can occur
    else
        -- For any other non-table, non-nil type passed directly.
        return {tostring(t)}
    end
    return strTable

end

-- Main function from previous step
local function handleRunCode(args)
    if type(args.command) ~= "string" then
        return ToolHelpers.FormatErrorResult("Error: RunCode command argument is missing or not a string.")
    end



-- Main function from previous step
local function handleRunCode(args)
    if type(args.command) ~= "string" then
        return ToolHelpers.FormatErrorResult("Error: RunCode command argument is missing or not a string.")
    end



-- Main function from previous step
local function handleRunCode(args)
    if type(args.command) ~= "string" then
        return ToolHelpers.FormatErrorResult("Error: RunCode command argument is missing or not a string.")
    end

    local command = args.command
    local output_parts = {}
    local an_error_occurred_in_command = false


    local function addToOutput(tag, ...)
        local packedArgs = table.pack(...)
        if packedArgs.n == 0 then
            table.insert(output_parts, tag .. "\n")
            return
        end

        -- Now uses the toStrTable with one-level deep serialization
        local strResults = toStrTable(packedArgs)
        table.insert(output_parts, tag .. " " .. table.concat(strResults, "\t") .. "\n")
    end

    local pcall_success, execution_result = pcall(function()
        local func, load_err = loadstring(command)
        if not func then
            an_error_occurred_in_command = true
            addToOutput("[LOADSTRING ERROR]", load_err or "Unknown loadstring error")
            return
        end

        local chunkfenv = getfenv(func)
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

        local oldError = chunkfenv.error
        chunkfenv.error = function(...)
            an_error_occurred_in_command = true
            addToOutput("[ERROR]", ...)
        end

        local results = {pcall(func)}
        local run_success = results[1]
        local returned_values_from_command = {}
        for i = 2, #results do
            table.insert(returned_values_from_command, results[i])
        end


        if not run_success then
            an_error_occurred_in_command = true
            addToOutput("[RUNTIME ERROR]", returned_values_from_command[1])
        else
            if #returned_values_from_command > 0 then

                addToOutput("[RETURNED]", table.unpack(returned_values_from_command))
            end
        end
    end)


    local final_output_str = table.concat(output_parts, "")

    if not pcall_success then
        final_output_str = final_output_str .. "[CRITICAL TOOL ERROR] " .. tostring(execution_result) .. "\n"
        an_error_occurred_in_command = true
        return ToolHelpers.FormatErrorResult(final_output_str)
    elseif an_error_occurred_in_command then
        return ToolHelpers.FormatErrorResult(final_output_str)
    else
        if final_output_str == "" then
            final_output_str = "Command executed successfully with no output or return values."
        end
        return ToolHelpers.FormatSuccessResult({ output = final_output_str })

    end
end

return handleRunCode
