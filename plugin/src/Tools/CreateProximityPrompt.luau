-- CreateProximityPrompt.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local parentPartPath = args.parent_part_path
        local properties = args.properties -- Optional, expecting a Lua table

        if not parentPartPath or type(parentPartPath) ~= "string" then
            return ToolHelpers.FormatErrorResult("'parent_part_path' is required and must be a string.")
        end

        properties = properties or {} -- Default to empty table
        if type(properties) ~= "table" then
            return ToolHelpers.FormatErrorResult("'properties', if provided, must be a table.")
        end


        local parentPart, err = ToolHelpers.FindInstanceByPath(parentPartPath)
        if not parentPart then
            return ToolHelpers.FormatErrorResult("Failed to find parent part at path: " .. parentPartPath .. ". " .. (err or ""))
        end
        if not parentPart:IsA("BasePart") and not parentPart:IsA("Attachment") and not parentPart:IsA("Model") and not parentPart:IsA("Accessory") then
             return ToolHelpers.FormatErrorResult("Parent for ProximityPrompt must be a BasePart, Attachment, Model, or Accessory. Found: " .. parentPart:GetClass())
        end

        local prompt = Instance.new("ProximityPrompt")
        local propertyErrors = {}

        if properties then
            for propName, propValueInput in pairs(properties) do
                if string.lower(propName) == "parent" then
                    -- The parent is determined by parent_part_path, not this property.
                    -- Could warn or ignore. For now, ignoring to prevent error if user includes it.
                    print("CreateProximityPrompt: 'Parent' property in 'properties' table is ignored. Use 'parent_part_path' argument.")
                else
                    -- Use JsonToRobloxValue for each property value, as it might be a JSON representation of a Roblox type
                    local convertedValue, convertError = ToolHelpers.JsonToRobloxValue(propValueInput, "ProximityPrompt."..propName)
                    if convertError then
                        table.insert(propertyErrors, ("Property '%s': Failed to convert input value: %s"):format(propName, convertError))
                    else
                        local setSuccess, setError = pcall(function()
                            prompt[propName] = convertedValue
                        end)
                        if not setSuccess then
                            table.insert(propertyErrors, ("Property '%s': Error setting value: %s"):format(propName, setError))
                        end
                    end
                end
            end
        end

        if #propertyErrors > 0 then
            prompt:Destroy()
            return ToolHelpers.FormatErrorResult(("Error(s) applying properties to new ProximityPrompt: %s"):format(table.concat(propertyErrors, "; ")))
        end

        prompt.Parent = parentPart

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully created ProximityPrompt under %s."):format(parentPartPath),
            prompt_path = prompt:GetFullName(),
            action_text = prompt.ActionText,
            object_text = prompt.ObjectText,
            max_activation_distance = prompt.MaxActivationDistance
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in CreateProximityPrompt: " .. tostring(pcall_result))
    end
end

return execute
