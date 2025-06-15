-- GetWorkspaceProperty.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are expected directly on args table
    local success, pcall_result = pcall(function()
        local propertyName = args.property_name

        if not propertyName or type(propertyName) ~= "string" then
            return ToolHelpers.FormatErrorResult("'property_name' is required and must be a string.")
        end

        -- Check if property actually exists before trying to access it
        local propertyExists = false
        local getPropertiesSuccess, properties = pcall(workspace.GetProperties, workspace) -- Less common, but GetProperties exists
        if getPropertiesSuccess then
            for _, propInfo in ipairs(properties) do
                if propInfo.Name == propertyName then
                    propertyExists = true
                    break
                end
            end
        else
            -- Fallback if GetProperties itself errors or isn't found (shouldn't happen for Workspace)
            -- For most Roblox instances, direct pcall access is the main way to check.
            local _, errTest = pcall(function() local _ = workspace[propertyName] end)
            propertyExists = errTest == nil -- If no error on access, it likely exists (though value could be nil)
        end

        -- A simpler, though less ideal check if GetProperties isn't used:
        -- local _, accessError = pcall(function() local _ = workspace[propertyName] end)
        -- if accessError and not string.match(tostring(accessError), "not a valid member") then
        --    -- some other error occurred during access, not necessarily that it doesn't exist
        -- end
        -- For robust check, it's better to iterate through scriptable members if possible, or rely on pcall only for value get.


        if not propertyExists then
             -- We make a distinction: if pcall below fails due to "not a member", it's clear.
             -- This check is more about valid, readable properties.
             -- Some properties might exist but not be scriptable, leading to pcall error.
             -- For now, let pcall handle non-scriptable or truly non-existent.
             -- This was an attempt to pre-validate, but pcall is the ultimate validator for readable properties.
             -- Removing the custom propertyExists check here and relying on pcall for actual get.
        end

        local getSuccess, propertyValueOrError = pcall(function()
            return workspace[propertyName]
        end)

        if not getSuccess then
            -- Check if the error is due to the property not being a valid member
            if string.find(tostring(propertyValueOrError), "is not a valid member of Workspace") then
                 return ToolHelpers.FormatErrorResult(("Property '%s' is not a valid member of Workspace."):format(propertyName))
            end
            return ToolHelpers.FormatErrorResult(("Failed to get Workspace property '%s': %s"):format(propertyName, tostring(propertyValueOrError)))
        end

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully retrieved Workspace property '%s'."):format(propertyName),
            property_name = propertyName,
            value = ToolHelpers.RobloxValueToJson(propertyValueOrError)
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in GetWorkspaceProperty: " .. tostring(pcall_result))
    end
end

return execute
