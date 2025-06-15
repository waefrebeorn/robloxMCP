-- SetProperties.luau (Refactored to match SetInstanceProperties.luau)
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are expected directly on args table
	-- This tool is an alias for SetInstanceProperties, so the argument key is "SetProperties"
	if not args["SetProperties"] then
		return ToolHelpers.FormatErrorResult("SetProperties: Invalid argument structure. Expected 'SetProperties' key containing path and properties.")
	end
	local toolArgs = args["SetProperties"] -- Keep this if Main.server.luau sends { SetProperties = {path="...", props=...} }
                                         -- If Main.server.luau sends {path="...", props=...} directly, then toolArgs = args

    local success, pcall_result = pcall(function()
        -- Assuming toolArgs holds the actual parameters like path and properties
        -- If args directly holds path and properties (after potential correction in Main.server.luau):
        -- local path = args.path
        -- local properties = args.properties

        -- For now, stick to the established pattern from other corrected tools,
        -- assuming Main.server.luau might still be sending the nested structure for some tools,
        -- OR that the user of this specific "SetProperties" tool expects to provide arguments under that key.
        -- The prompt for THIS SUBTASK says "args.property_name", implying direct access.
        -- So, I will assume direct access for 'path' and 'properties' from the 'args' table.

        local path = args.path
        local properties = args.properties

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
            local convertedValue, convertError = ToolHelpers.JsonToRobloxValue(propValueInput, instance:GetClass().."."..propName)

            if convertError then
                table.insert(failedProperties, {
                    name = propName,
                    error = "Value conversion failed: " .. convertError,
                    original_value = propValueInput
                })
                print(("SetProperties: Error converting value for property '%s' on instance '%s': %s"):format(propName, path, convertError))
            else
                local setSuccess, setError = pcall(function()
                    instance[propName] = convertedValue
                end)

                if setSuccess then
                    table.insert(appliedProperties, propName)
                else
                    table.insert(failedProperties, {
                        name = propName,
                        error = tostring(setError),
                        value_tried = convertedValue
                    })
                    print(("SetProperties: Error setting property '%s' on instance '%s': %s"):format(propName, path, setError))
                end
            end
        end

        if #failedProperties > 0 then
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
        return ToolHelpers.FormatErrorResult("Internal error in SetProperties: " .. tostring(pcall_result))
    end
end

return execute
