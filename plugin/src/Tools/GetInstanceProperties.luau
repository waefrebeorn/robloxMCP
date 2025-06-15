-- GetInstanceProperties.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local path = args.path
        local propertyNames = args.property_names

        if not path or type(path) ~= "string" then
            return ToolHelpers.FormatErrorResult("'path' is required and must be a string.")
        end

        propertyNames = propertyNames or {} -- Default to empty if nil
        if type(propertyNames) ~= "table" then
            return ToolHelpers.FormatErrorResult("'property_names', if provided, must be an array of strings.")
        end

        for i, propName in ipairs(propertyNames) do
            if type(propName) ~= "string" then
                return ToolHelpers.FormatErrorResult("All 'property_names' must be strings. Found entry at index " .. i .. " with type: " .. type(propName))
            end
        end

        local instance, err = ToolHelpers.FindInstanceByPath(path)
        if not instance then
            return ToolHelpers.FormatErrorResult("Failed to find instance at path: " .. path .. ". " .. (err or ""))
        end

        local retrievedProperties = {}
        local accessErrors = {}

        for _, propNameString in ipairs(propertyNames) do
            local getSuccess, propValueOrError = pcall(function()
                return instance[propNameString]
            end)

            if getSuccess then
                -- RobloxValueToJson is still correct here as FormatSuccessResult expects a table that it will then encode.
                -- The values *within* that table should be JSON-representable.
                retrievedProperties[propNameString] = ToolHelpers.RobloxValueToJson(propValueOrError)
            else
                table.insert(accessErrors, {name = propNameString, error = tostring(propValueOrError)})
                print(("GetInstanceProperties: Error getting property '%s' for '%s': %s"):format(propNameString, path, propValueOrError))
            end
        end

        local message
        if #propertyNames == 0 then
            message = ("No properties requested for instance %s. Returning empty properties table."):format(path)
        elseif #accessErrors > 0 then
            message = ("Retrieved %d/%d requested properties for instance %s with some errors."):format(#propertyNames - #accessErrors, #propertyNames, path)
        else
            message = ("Successfully retrieved %d properties for instance %s."):format(#propertyNames, path)
        end

        local resultData = {
            message = message,
            instance_path = path,
            properties = retrievedProperties
        }
        if #accessErrors > 0 then
            resultData.errors = accessErrors
            -- As per previous logic, this is still a "successful" tool execution from pcall's perspective.
            -- The agent should check the 'errors' field in the JSON.
        end
        return ToolHelpers.FormatSuccessResult(resultData)
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in GetInstanceProperties: " .. tostring(pcall_result))
    end
end

return execute
