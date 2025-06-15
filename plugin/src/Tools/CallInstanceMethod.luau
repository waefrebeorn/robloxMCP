-- CallInstanceMethod.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local path = args.path
        local methodName = args.method_name
        local methodArguments = args.arguments -- Renamed from methodArgsJson for clarity, expecting array of values

        if not path or type(path) ~= "string" then
            return ToolHelpers.FormatErrorResult("'path' is required and must be a string.")
        end
        if not methodName or type(methodName) ~= "string" then
            return ToolHelpers.FormatErrorResult("'method_name' is required and must be a string.")
        end
        if not methodArguments or type(methodArguments) ~= "table" then
            return ToolHelpers.FormatErrorResult("'arguments' is required and must be an array (can be empty).")
        end

        local instance, err = ToolHelpers.FindInstanceByPath(path)
        if not instance then
            return ToolHelpers.FormatErrorResult("Failed to find instance at path: " .. path .. ". " .. (err or ""))
        end

        if type(instance[methodName]) ~= "function" then
            return ToolHelpers.FormatErrorResult(("Method '%s' not found or is not a function on instance %s (type is %s)."):format(methodName, path, type(instance[methodName])))
        end

        -- The 'arguments' received are expected to be Lua values already,
        -- potentially converted from JSON by the dispatcher if they were complex.
        -- JsonToRobloxValue was used in previous version, assuming arguments were JSON objects.
        -- If Main.server.luau now sends arguments already as proper Lua types (after its own JSONDecode of arguments_json),
        -- then direct usage is fine. Assuming 'arguments' from toolInputArgs are ready to be used.
        -- If they still need conversion from a specific JSON-like table structure, ToolHelpers.JsonToRobloxValue would be needed here.
        -- For now, proceeding with direct usage of methodArguments.

        local callSuccess, resultsPack = pcall(function()
            return table.pack(instance[methodName](instance, unpack(methodArguments, 1, #methodArguments)))
        end)

        if not callSuccess then
            return ToolHelpers.FormatErrorResult(("Error calling method '%s' on instance '%s': %s"):format(methodName, path, tostring(resultsPack)))
        end

        local resultsProcessed = {} -- Changed from resultsJson as they are now Lua values for ToolHelpers
        if resultsPack and resultsPack.n > 0 then
            for i = 1, resultsPack.n do
                -- ToolHelpers.RobloxValueToJson is still needed if the return values from the method
                -- need to be serialized into the final JSON string by FormatSuccessResult.
                -- FormatSuccessResult will handle the JSON encoding of the entire table passed to it.
                table.insert(resultsProcessed, resultsPack[i])
            end
        end

        local returnMessage
        if resultsPack and resultsPack.n > 0 then
            returnMessage = ("Successfully called method '%s' on instance %s. Method returned %d value(s)."):format(methodName, path, resultsPack.n)
        else
            returnMessage = ("Successfully called method '%s' on instance %s. Method returned no values."):format(methodName, path)
        end

        return ToolHelpers.FormatSuccessResult({
            message = returnMessage,
            results = resultsProcessed -- This table will be JSON encoded by FormatSuccessResult
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in CallInstanceMethod: " .. tostring(pcall_result))
    end
end

return execute
