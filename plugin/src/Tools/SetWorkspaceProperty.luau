-- SetWorkspaceProperty.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Types = require(Main.Types) -- Added

local function execute(args: Types.SetWorkspacePropertyArgs) -- Type annotation added
    local success, resultOrError = pcall(function()
        local propertyName = args.property_name
        local propertyValue = args.value -- Expecting direct Luau value

        if not propertyName or type(propertyName) ~= "string" then
            return "'property_name' is required and must be a string."
        end
        if propertyValue == nil then
            return "'value' is required for the property."
        end

        -- No conversion needed, propertyValue is expected to be the correct Luau type.
        -- ToolHelpers.JsonToRobloxValue call removed.
        -- convertError check removed.

        local setSuccess, setError = pcall(function()
            workspace[propertyName] = propertyValue -- Use propertyValue directly
        end)

        if not setSuccess then
            if string.find(tostring(setError), "not a valid member") or string.find(tostring(setError), "cannot be assigned to") then
                 return ("Property '%s' on Workspace is not settable or does not exist. Error: %s"):format(propertyName,tostring(setError))
            end
            return ("Failed to set Workspace property '%s': %s"):format(propertyName, tostring(setError))
        end

        local actualValue = workspace[propertyName]
        local resultData: Types.SetWorkspacePropertyResultData = {
            property_name = propertyName,
            new_value_set = actualValue, -- Raw Roblox value
        }
        return resultData
    end)

    if success then
        if type(resultOrError) == "string" then
            return ToolHelpers.FormatErrorResult(resultOrError)
        else
            return ToolHelpers.FormatSuccessResult(resultOrError)
        end
    else
        return ToolHelpers.FormatErrorResult("Internal error in SetWorkspaceProperty: " .. tostring(resultOrError))
    end
end

return execute
