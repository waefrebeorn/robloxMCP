-- CreateGuiElement.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local PlayersService = game:GetService("Players") -- Needed for PlayerGui
local StarterGuiService = game:GetService("StarterGui")

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local elementType = args.element_type
        local parentPathArg = args.parent_path -- Optional
        local properties = args.properties -- Optional, expecting a Lua table of properties

        if not elementType or type(elementType) ~= "string" then
            return ToolHelpers.FormatErrorResult("'element_type' is required and must be a string (e.g., 'Frame', 'TextButton').")
        end
        if parentPathArg ~= nil and type(parentPathArg) ~= "string" then
            return ToolHelpers.FormatErrorResult("'parent_path' argument must be a string if provided.")
        end
        if properties ~= nil and type(properties) ~= "table" then
            return ToolHelpers.FormatErrorResult("'properties' must be a table if provided.")
        end
        properties = properties or {} -- Default to empty table if nil

        local createSuccess, newElementOrError = pcall(Instance.new, elementType)
        if not createSuccess then
            return ToolHelpers.FormatErrorResult(("Failed to create element of type '%s': %s"):format(elementType, tostring(newElementOrError)))
        end
        local newElement = newElementOrError

        local actualParent = nil
        local parentDeterminationError = nil

        -- Determine effective parent path (from properties or argument)
        local effectiveParentPath = parentPathArg
        if properties.Parent then -- Assuming 'Parent' in properties is a string path or an Instance
            if type(properties.Parent) == "string" then
                effectiveParentPath = properties.Parent
            elseif typeof(properties.Parent) == "Instance" then
                 actualParent = properties.Parent -- If it's already an instance (e.g. from a previous tool step if chaining was supported)
                 effectiveParentPath = nil -- Clear path so we don't try to find it
            else
                parentDeterminationError = "'Parent' property must be a string path or an Instance value."
            end
        end

        if not parentDeterminationError and effectiveParentPath then
            if string.lower(effectiveParentPath) == "startergui" then
                actualParent = StarterGuiService
            else
                local foundParent, err = ToolHelpers.FindInstanceByPath(effectiveParentPath)
                if not foundParent then
                    parentDeterminationError = ("Failed to find specified parent at path: %s. %s"):format(effectiveParentPath, err or "")
                elseif elementType == "ScreenGui" and foundParent:IsA("Player") then
                    actualParent = foundParent:FindFirstChildOfClass("PlayerGui")
                    if not actualParent then
                        if foundParent == PlayersService.LocalPlayer then
                            actualParent = Instance.new("PlayerGui")
                            actualParent.Parent = foundParent
                        else
                             parentDeterminationError = ("PlayerGui not found for player: %s. Cannot parent ScreenGui there."):format(foundParent.Name)
                        end
                    end
                elseif not (foundParent:IsA("GuiBase") or foundParent:IsA("GuiObject") or foundParent:IsA("BasePlayerGui") or foundParent:IsA("StarterGui") or foundParent:IsA("Folder") or foundParent:IsA("Model") or foundParent == workspace) then
                     parentDeterminationError = ("Parent '%s' (type: %s) is not a standard GUI container or common parent type."):format(effectiveParentPath, foundParent:GetClass())
                else
                    actualParent = foundParent
                end
            end
        elseif not parentDeterminationError and elementType == "ScreenGui" and not actualParent then -- Only if not already resolved by properties.Parent being an Instance
            local localPlayer = PlayersService.LocalPlayer
            if localPlayer then
                actualParent = localPlayer:FindFirstChildOfClass("PlayerGui")
                if not actualParent then
                    actualParent = Instance.new("PlayerGui")
                    actualParent.Parent = localPlayer
                end
            else
                parentDeterminationError = "ScreenGui needs a parent (e.g., Player path for PlayerGui, or 'StarterGui'). LocalPlayer not available for default PlayerGui, and no parent_path or Parent property provided."
            end
        end

        -- Apply other properties. Arguments in 'properties' table are expected to be Lua types.
        -- JsonToRobloxValue was used when properties was 'propertiesJson'. If 'properties' now contains direct Lua values, it's simpler.
        local propertyErrors = {}
        for propName, propValue in pairs(properties) do
            if string.lower(propName) ~= "parent" then
                -- Assuming propValue is already the correct Lua type.
                -- If propValue came from a JSON structure and needs conversion (e.g. table to Vector3),
                -- ToolHelpers.JsonToRobloxValue(propValue, newElement:GetClass().."."..propName) would be needed.
                -- For this refactor, assuming 'properties' contains ready-to-use Lua values.
                local setSuccess, setError = pcall(function()
                    newElement[propName] = propValue
                end)
                if not setSuccess then
                    table.insert(propertyErrors, ("Property '%s': Error setting value: %s"):format(propName, setError))
                end
            end
        end

        if #propertyErrors > 0 then
            newElement:Destroy()
            return ToolHelpers.FormatErrorResult(("Error(s) applying properties to new %s: %s"):format(elementType, table.concat(propertyErrors, "; ")))
        end

        if parentDeterminationError then
            if not actualParent then
                 newElement:Destroy()
                 return ToolHelpers.FormatErrorResult(parentDeterminationError)
            end
        end

        if actualParent then
            newElement.Parent = actualParent
        elseif elementType == "ScreenGui" and not actualParent then
            newElement:Destroy()
            return ToolHelpers.FormatErrorResult("ScreenGui element could not be parented. Ensure LocalPlayer is available or specify a parent.")
        end

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully created GUI element '%s' of type %s."):format(newElement.Name, elementType),
            element_path = newElement:GetFullName(),
            element_type = elementType,
            parent_path_used = actualParent and actualParent:GetFullName() or (newElement.Parent and newElement.Parent:GetFullName() or "None")
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in CreateGuiElement: " .. tostring(pcall_result))
    end
end

return execute
