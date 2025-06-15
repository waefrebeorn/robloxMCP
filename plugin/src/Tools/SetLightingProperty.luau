-- SetLightingProperty.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Lighting = game:GetService("Lighting")

local function execute(args)
    -- Arguments are expected directly on args table
    local success, pcall_result = pcall(function()
        local propertyName = args.property_name
        local propertyValue = args.value -- Expecting this to be a Lua value, potentially complex (table for Color3, etc.)

        if not propertyName or type(propertyName) ~= "string" then
            return ToolHelpers.FormatErrorResult("'property_name' is required and must be a string.")
        end
        if propertyValue == nil then -- Explicitly check for nil
            return ToolHelpers.FormatErrorResult("'value' is required for the property.")
        end

        -- Check if property exists and is scriptable before attempting to set
        local descriptor = Lighting:GetProperties()[propertyName]
        if not descriptor then
            return ToolHelpers.FormatErrorResult(("Property '%s' does not exist on Lighting service."):format(propertyName))
        end
        if descriptor.Security.Write ~= Enum.RobloxScriptSecurity.None then -- Assuming 'None' means scriptable by plugins
            -- Note: Actual scriptability might depend on context (e.g. plugin vs command bar script).
            -- This is a basic check. Some properties might be read-only ("None" security but not settable).
            -- The pcall below will ultimately catch if it's truly not settable.
            -- For now, this check is more about existence and very basic scriptability.
            -- A more accurate check would be to see if it's not Enum.RobloxScriptSecurity.RobloxScript (internal)
            -- or if it's explicitly marked read-only in some API dump if available.
            -- Let's simplify: the pcall is the true test of settability.
            -- We'll just check for existence via GetProperties.
        end


        -- Convert the input Lua value (which might be a table for Color3, Vector3 etc.) to the actual Roblox type
        local convertedValue, convertError = ToolHelpers.JsonToRobloxValue(propertyValue, "Lighting."..propertyName)
        if convertError then
            return ToolHelpers.FormatErrorResult(("Invalid value format for Lighting property '%s': %s"):format(propertyName, convertError))
        end

        local setSuccess, setError = pcall(function()
            Lighting[propertyName] = convertedValue
        end)

        if not setSuccess then
            if string.find(tostring(setError), "not a valid member") or string.find(tostring(setError), "cannot be assigned to") then
                 return ToolHelpers.FormatErrorResult(("Property '%s' on Lighting is not settable or does not exist. Error: %s"):format(propertyName,tostring(setError)))
            end
            return ToolHelpers.FormatErrorResult(("Failed to set Lighting property '%s': %s"):format(propertyName, tostring(setError)))
        end

        -- Fetch the actual value after setting to confirm
        local actualValue = Lighting[propertyName]

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully set Lighting property '%s'."):format(propertyName),
            property_name = propertyName,
            new_value_set = ToolHelpers.RobloxValueToJson(actualValue) -- Confirm by sending back the actual value
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in SetLightingProperty: " .. tostring(pcall_result))
    end
end

return execute
