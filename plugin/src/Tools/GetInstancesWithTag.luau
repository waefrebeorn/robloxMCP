-- GetInstancesWithTag.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local CollectionService = game:GetService("CollectionService")

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local tagName = args.tag_name

        if not tagName or type(tagName) ~= "string" or tagName == "" then
            return ToolHelpers.FormatErrorResult("'tag_name' is required and must be a non-empty string.")
        end

        local taggedInstances = CollectionService:GetTagged(tagName)
        local instancesInfo = {}

        for _, instance in ipairs(taggedInstances) do
            if instance and instance.Parent ~= nil then
                table.insert(instancesInfo, {
                    name = instance.Name,
                    path = instance:GetFullName(),
                    class_name = instance.ClassName
                })
            end
        end

        return ToolHelpers.FormatSuccessResult({
            message = ("Found %d instance(s) with tag '%s'."):format(#instancesInfo, tagName),
            tag_name = tagName,
            instances = instancesInfo
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in GetInstancesWithTag: " .. tostring(pcall_result))
    end
end

return execute
