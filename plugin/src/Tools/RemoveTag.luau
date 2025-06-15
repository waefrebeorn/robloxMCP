-- RemoveTag.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local CollectionService = game:GetService("CollectionService")

local function execute(args)
    -- Arguments are expected directly on args table
    local success, pcall_result = pcall(function()
        local instancePath = args.instance_path
        local tagName = args.tag_name

        if not instancePath or type(instancePath) ~= "string" then
            return ToolHelpers.FormatErrorResult("'instance_path' is required and must be a string.")
        end
        if not tagName or type(tagName) ~= "string" or tagName == "" then
            return ToolHelpers.FormatErrorResult("'tag_name' is required and must be a non-empty string.")
        end

        local instance, err = ToolHelpers.FindInstanceByPath(instancePath)
        if not instance then
            -- If instance doesn't exist, arguably the tag is "removed" from it.
            -- However, it's better to be explicit that the instance wasn't found.
            return ToolHelpers.FormatErrorResult("Failed to find instance at path: " .. instancePath .. ". " .. (err or ""))
        end

        local successRemove, errRemove = pcall(CollectionService.RemoveTag, CollectionService, instance, tagName)
        if not successRemove then
            return ToolHelpers.FormatErrorResult(("Failed to remove tag '%s' from instance %s: %s"):format(tagName, instancePath, tostring(errRemove)))
        end

        -- Check if the tag was actually there before removing. RemoveTag doesn't error if tag isn't present.
        -- This info might be useful for the agent.
        -- For now, a successful call to RemoveTag is treated as success.

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully removed tag '%s' from instance %s (if it was present)."):format(tagName, instancePath),
            instance_path = instancePath,
            tag_name = tagName
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in RemoveTag: " .. tostring(pcall_result))
    end
end

return execute
