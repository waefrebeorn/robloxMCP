-- CreateInstance.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Types = require(Main.Types) -- Added

local function execute(args: Types.CreateInstanceArgs) -- Type annotation added
    local success, resultOrError = pcall(function()
        local className = args.class_name
        local properties = args.properties or {} -- Default to empty table
        local arg_parent_path = args.parent_path -- Store original arg

        if not className or type(className) ~= "string" then
            return "'class_name' is required and must be a string." -- Return error string
        end

        if type(properties) ~= "table" then
             return "'properties', if provided, must be a table." -- Return error string
        end

        local createSuccess, newInstanceOrError = pcall(Instance.new, className)
        if not createSuccess then
            return ("Failed to create instance of type '%s': %s"):format(className, tostring(newInstanceOrError)) -- Return error string
        end
        local newInstance = newInstanceOrError

        local propertyErrors = {}
        local parentInstance = nil

        -- Determine parent:
        -- 1. Prioritize explicit parent_path argument from args.
        -- 2. Fallback to properties.Parent if args.parent_path is not provided.
        local effectiveParentPath = arg_parent_path
        if not effectiveParentPath and properties.Parent then
            if type(properties.Parent) == "string" then
                effectiveParentPath = properties.Parent
            else
                newInstance:Destroy() -- Clean up
                return ("'Parent' property in 'properties' table must be a string path. Got type: %s"):format(typeof(properties.Parent))
            end
        end

        if effectiveParentPath then
            -- This check is a bit redundant now if properties.Parent has been type-checked, but good for safety
            if type(effectiveParentPath) == "string" then
                local foundParent, err = ToolHelpers.FindInstanceByPath(effectiveParentPath)
                if foundParent then
                    parentInstance = foundParent
                else
                    newInstance:Destroy() -- Clean up
                    return ("Failed to find specified Parent at path: %s. %s"):format(effectiveParentPath, err or "Unknown error")
                end
            else
                newInstance:Destroy() -- Clean up
                -- This case should ideally not be reached if the logic above is correct
                return ("Internal Error: Effective parent path resolved to a non-string. Path: %s"):format(tostring(effectiveParentPath))
            end
        end

        -- Apply other properties
        for propName, propValueInput in pairs(properties) do
            local propNameLower = string.lower(propName)
            if propNameLower ~= "parent" then -- Parent is now fully handled by parentInstance logic above
                -- No conversion needed, propValueInput is expected to be the correct Luau type.
                -- ToolHelpers.JsonToRobloxValue call removed.
                local setPropSuccess, setError = pcall(function()
                    newInstance[propName] = propValueInput -- Use propValueInput directly
                end)
                if not setPropSuccess then
                    table.insert(propertyErrors, ("Property '%s': Error setting value: %s"):format(propName, setError))
                end
            end
        end

        if #propertyErrors > 0 then
            newInstance:Destroy() -- Clean up
            return ("Error(s) applying properties to new %s: %s"):format(className, table.concat(propertyErrors, "; ")) -- Return error string
        end

        if parentInstance then
            newInstance.Parent = parentInstance
        end

        -- Return CreateInstanceResultData table
        local resultData: Types.CreateInstanceResultData = {
            message = ("Successfully created %s instance named '%s'."):format(className, newInstance.Name),
            instance_path = newInstance:GetFullName(),
            class_name = className,
        }
        return resultData
    end)

    if success then
		if type(resultOrError) == "string" then -- An error message string was returned
			return ToolHelpers.FormatErrorResult(resultOrError)
		elseif resultOrError == nil then -- pcall succeeded but function returned nil (shouldn't happen with current logic but good to cover)
			return ToolHelpers.FormatErrorResult("CreateInstance returned nil unexpectedly.")
		else -- A resultData table was returned
			return ToolHelpers.FormatSuccessResult(resultOrError)
		end
    else
		-- pcall itself failed
        return ToolHelpers.FormatErrorResult("Internal error in CreateInstance: " .. tostring(resultOrError))
    end
end

return execute
