-- SetInstanceProperties.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Types = require(Main.Types) -- Added

local function execute(args: Types.SetInstancePropertiesArgs) -- Type annotation added
    local success, resultOrError = pcall(function()
        local path = args.path
        local propertiesToSet = args.properties

        if not path or type(path) ~= "string" then
            return "'path' is required and must be a string."
        end
        if not propertiesToSet or type(propertiesToSet) ~= "table" then
            return "'properties' is required and must be a table."
        end
        if next(propertiesToSet) == nil then
            return "'properties' table cannot be empty."
        end

        local instance, err = ToolHelpers.FindInstanceByPath(path)
        if not instance then
            return ("Failed to find instance at path: %s. %s"):format(path, err or "Unknown error")
        end

        local propertyResults: {Types.PropertyWriteResult} = {}
        local overallSuccess = true
        local setPropsCount = 0
        local failedPropsCount = 0

        for propName, propValueInput in pairs(propertiesToSet) do
            local finalValueToSet = propValueInput
            local conversionErrorMsg = nil

            if type(propValueInput) == "table" then -- Only attempt conversion if it's a table
                local converted_value_from_helper, err_msg_from_helper = ToolHelpers.ConvertTableToRobloxType(propValueInput, propName, instance)
                if err_msg_from_helper then
                    conversionErrorMsg = err_msg_from_helper
                    -- finalValueToSet remains propValueInput, which is correct for reporting original_value
                else
                    finalValueToSet = converted_value_from_helper -- Use the successfully converted value
                end
            end

            if conversionErrorMsg then
                table.insert(propertyResults, {
                    name = propName,
                    status = "conversion_error",
                    error_message = conversionErrorMsg,
                    original_value = propValueInput -- Value that was attempted
                })
                failedPropsCount += 1
                overallSuccess = false
            else
                -- Proceed with setting the property using finalValueToSet
                local setSuccess, setError = pcall(function()
                    instance[propName] = finalValueToSet
                end)

                if setSuccess then
                    table.insert(propertyResults, {
                        name = propName,
                        status = "success"
                        -- Optional: add 'value_set = finalValueToSet' if needed,
                        -- but be careful with complex types in results for SimpleTableToString
                    })
                    setPropsCount += 1
                else
                    table.insert(propertyResults, {
                        name = propName,
                        status = "set_error",
                        error_message = tostring(setError),
                        original_value = propValueInput, -- Show what was originally intended
                        attempted_value = finalValueToSet -- Show what was attempted after conversion (if any)
                    })
                    failedPropsCount += 1
                    overallSuccess = false
                end
            end
        end

        local message: string
        if failedPropsCount > 0 then
            message = ("Attempted to set %d properties for %s. %d succeeded, %d failed."):format(setPropsCount + failedPropsCount, path, setPropsCount, failedPropsCount)
        else
            message = ("Successfully set %d properties for instance %s."):format(setPropsCount, path)
        end

        local resultData: Types.SetInstancePropertiesResultData = {
            instance_path = path,
            results = propertyResults,
            message = message,
        }

        -- If any individual property failed, the overall operation might still be considered "successful"
        -- at the tool level, with detailed errors in the results.
        -- If we want to return a top-level error for partial failures, this logic would change.
        -- For now, returning full result data. If overallSuccess is false, an error string could be returned instead.
        if not overallSuccess then
             -- Optionally, could return an error string here to make FormatErrorResult handle it
             -- return message -- This would make it an error. For now, let's return the detailed data.
        end
        return resultData
    end)

    if success then
        if type(resultOrError) == "string" then
            return ToolHelpers.FormatErrorResult(resultOrError)
        else
            -- Check if the resultData itself indicates a complete failure and should be an error
            -- For now, FormatSuccessResult handles the table.
            return ToolHelpers.FormatSuccessResult(resultOrError)
        end
    else
        return ToolHelpers.FormatErrorResult("Internal error in SetInstanceProperties: " .. tostring(resultOrError))
    end
end

return execute
