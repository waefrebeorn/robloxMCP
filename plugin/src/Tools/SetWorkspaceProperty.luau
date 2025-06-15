-- SetWorkspaceProperty.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are expected directly on args table
    local success, pcall_result = pcall(function()
        local propertyName = args.property_name
        local propertyValue = args.value -- Expecting this to be a Lua value, potentially complex

        if not propertyName or type(propertyName) ~= "string" then
            return ToolHelpers.FormatErrorResult("'property_name' is required and must be a string.")
        end
        if propertyValue == nil then
            return ToolHelpers.FormatErrorResult("'value' is required for the property.")
        end

        -- Minimal check for existence; pcall will handle actual writability
        local descriptor = workspace:GetProperties()[propertyName]
        if not descriptor then
            -- This check might not catch all cases (e.g. non-scriptable but existing internal properties)
            -- The pcall below is the definitive test.
            local propExists = false
            local _, accessError = pcall(function() local _ = workspace[propertyName] end)
            if accessError == nil or not string.find(tostring(accessError), "not a valid member") then
                propExists = true -- It exists or error is not "not a member" (e.g. lacks permissions but exists)
            end
            if not propExists then
                 return ToolHelpers.FormatErrorResult(("Property '%s' does not appear to be a valid member of Workspace."):format(propertyName))
            end
        end


        local convertedValue, convertError = ToolHelpers.JsonToRobloxValue(propertyValue, "Workspace."..propertyName)
        if convertError then
            return ToolHelpers.FormatErrorResult(("Invalid value format for Workspace property '%s': %s"):format(propertyName, convertError))
        end

        local setSuccess, setError = pcall(function()
            workspace[propertyName] = convertedValue
        end)

        if not setSuccess then
            if string.find(tostring(setError), "not a valid member") or string.find(tostring(setError), "cannot be assigned to") then
                 return ToolHelpers.FormatErrorResult(("Property '%s' on Workspace is not settable or does not exist. Error: %s"):format(propertyName, tostring(setError)))
            end
            return ToolHelpers.FormatErrorResult(("Failed to set Workspace property '%s': %s"):format(propertyName, tostring(setError)))
        end

        local actualValue = workspace[propertyName]

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully set Workspace property '%s'."):format(propertyName),
            property_name = propertyName,
            new_value_set = ToolHelpers.RobloxValueToJson(actualValue)
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in SetWorkspaceProperty: " .. tostring(pcall_result))
    end
end

return execute
