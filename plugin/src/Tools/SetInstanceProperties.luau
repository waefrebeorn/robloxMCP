-- SetInstanceProperties.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are expected directly on args table
    local success, pcall_result = pcall(function()
        local path = args.path
        local properties = args.properties -- Expecting a Lua table {propName = value, ...}

        if not path or type(path) ~= "string" then
            return ToolHelpers.FormatErrorResult("'path' is required and must be a string.")
        end
        if not properties or type(properties) ~= "table" then
            return ToolHelpers.FormatErrorResult("'properties' is required and must be a table.")
        end
        if next(properties) == nil then -- Check if properties table is empty
            return ToolHelpers.FormatErrorResult("'properties' table cannot be empty.")
        end

        local instance, err = ToolHelpers.FindInstanceByPath(path)
        if not instance then
            return ToolHelpers.FormatErrorResult("Failed to find instance at path: " .. path .. ". " .. (err or ""))
        end

        local appliedProperties = {}
        local failedProperties = {}

        for propName, propValueInput in pairs(properties) do
            -- Values from 'properties' table might need conversion if they represent Roblox types in JSON-like tables
            local convertedValue, convertError = ToolHelpers.JsonToRobloxValue(propValueInput, instance:GetClass().."."..propName)

            if convertError then
                table.insert(failedProperties, {
                    name = propName,
                    error = "Value conversion failed: " .. convertError,
                    original_value = propValueInput
                })
                print(("SetInstanceProperties: Error converting value for property '%s' on instance '%s': %s"):format(propName, path, convertError))
                goto continue_loop
            end

            local setSuccess, setError = pcall(function()
                instance[propName] = convertedValue
            end)

            if setSuccess then
                table.insert(appliedProperties, propName)
            else
                table.insert(failedProperties, {
                    name = propName,
                    error = tostring(setError),
                    value_tried = convertedValue -- Or propValueInput if more useful
                })
                print(("SetInstanceProperties: Error setting property '%s' on instance '%s': %s"):format(propName, path, setError))
            end
            ::continue_loop::
        end

        if #failedProperties > 0 then
            -- If any property failed, the operation is considered an error at the top level.
            local summaryMessage = ("Error setting some properties for %s. %d succeeded, %d failed."):format(
                path,
                #appliedProperties,
                #failedProperties
            )
            return ToolHelpers.FormatErrorResult(summaryMessage, {
                applied_properties = appliedProperties,
                failed_properties_details = failedProperties,
                instance_path = path
            })
        else
            return ToolHelpers.FormatSuccessResult({
                message = ("Successfully set %d properties for instance %s."):format(#appliedProperties, path),
                applied_properties = appliedProperties,
                instance_path = path
            })
        end
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in SetInstanceProperties: " .. tostring(pcall_result))
    end
end

return execute
