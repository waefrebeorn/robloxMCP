-- CreateInstance.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local className = args.class_name
        local properties = args.properties -- Table of properties

        if not className or type(className) ~= "string" then
            return ToolHelpers.FormatErrorResult("'class_name' is required and must be a string.")
        end

        properties = properties or {} -- Default to empty table if nil or not provided
        if type(properties) ~= "table" then
             return ToolHelpers.FormatErrorResult("'properties', if provided, must be a table.")
        end


        local createSuccess, newInstanceOrError = pcall(Instance.new, className)
        if not createSuccess then
            return ToolHelpers.FormatErrorResult(("Failed to create instance of type '%s': %s"):format(className, tostring(newInstanceOrError)))
        end
        local newInstance = newInstanceOrError

        local propertyErrors = {}
        local parentInstance = nil

        -- Handle Parent property separately if it exists in the properties table
        local parentPropertyProvided = false
        if properties.Parent ~= nil then -- Check if Parent key explicitly exists
            parentPropertyProvided = true
            local parentValue = properties.Parent
            if type(parentValue) == "string" then
                local foundParent, err = ToolHelpers.FindInstanceByPath(parentValue)
                if foundParent then
                    parentInstance = foundParent
                else
                    newInstance:Destroy()
                    return ToolHelpers.FormatErrorResult(("Failed to find specified Parent at path: %s. %s"):format(parentValue, err or "Unknown error"))
                end
            -- Check if parentValue is already an Instance (e.g. passed from another tool or pre-resolved)
            elseif typeof(parentValue) == "Instance" then
                parentInstance = parentValue
            else
                newInstance:Destroy()
                return ToolHelpers.FormatErrorResult("'Parent' property, if provided, must be a string path or an Instance. Got type: " .. typeof(parentValue))
            end
        end

        -- Apply other properties
        for propName, propValueInput in pairs(properties) do
            if string.lower(propName) ~= "parent" then
                -- Use JsonToRobloxValue for each property value, as it might be a JSON representation of a Roblox type
                local convertedValue, convertError = ToolHelpers.JsonToRobloxValue(propValueInput, newInstance.ClassName.."."..propName)
                if convertError then
                    table.insert(propertyErrors, ("Property '%s': Failed to convert input value: %s"):format(propName, convertError))
                else
                    local setSuccess, setError = pcall(function()
                        newInstance[propName] = convertedValue
                    end)
                    if not setSuccess then
                        table.insert(propertyErrors, ("Property '%s': Error setting value: %s"):format(propName, setError))
                    end
                end
            end
        end

        if #propertyErrors > 0 then
            newInstance:Destroy()
            return ToolHelpers.FormatErrorResult(("Error(s) applying properties to new %s: %s"):format(className, table.concat(propertyErrors, "; ")))
        end

        if parentInstance then
            newInstance.Parent = parentInstance
        end

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully created %s instance named '%s'."):format(className, newInstance.Name),
            instance_path = newInstance:GetFullName(),
            class_name = className
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in CreateInstance: " .. tostring(pcall_result))
    end
end

return execute
