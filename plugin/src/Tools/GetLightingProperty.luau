-- GetLightingProperty.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Lighting = game:GetService("Lighting")

local function execute(args)
    -- Arguments are expected directly on args table
    local success, pcall_result = pcall(function()
        local propertyName = args.property_name

        if not propertyName or type(propertyName) ~= "string" then
            return ToolHelpers.FormatErrorResult("'property_name' is required and must be a string.")
        end

        -- Check if property actually exists before trying to access it
        local propertyExists = false
        local getInstancePropertySuccess, _ = pcall(function()
            propertyExists = Lighting[propertyName] ~= nil -- Accessing it might error for some internal properties
        end)
        -- More robust check:
        local properties = Lighting:GetProperties()
        propertyExists = false -- reset
        for _, propInfo in ipairs(properties) do
            if propInfo.Name == propertyName then
                propertyExists = true
                break
            end
        end


        if not propertyExists then
            return ToolHelpers.FormatErrorResult(("Property '%s' does not exist on Lighting service."):format(propertyName))
        end


        local getSuccess, propertyValueOrError = pcall(function()
            return Lighting[propertyName]
        end)

        if not getSuccess then
            return ToolHelpers.FormatErrorResult(("Failed to get Lighting property '%s': %s"):format(propertyName, tostring(propertyValueOrError)))
        end

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully retrieved Lighting property '%s'."):format(propertyName),
            property_name = propertyName,
            value = ToolHelpers.RobloxValueToJson(propertyValueOrError) -- Value is already prepared for JSON by RobloxValueToJson
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in GetLightingProperty: " .. tostring(pcall_result))
    end
end

return execute
