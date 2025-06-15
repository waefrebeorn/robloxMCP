-- GetDescendantsOfInstance.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local instancePath = args.instance_path

        if not instancePath or type(instancePath) ~= "string" or instancePath == "" then
            return ToolHelpers.FormatErrorResult("'instance_path' is required and must be a non-empty string.")
        end

        local instance, err = ToolHelpers.FindInstanceByPath(instancePath)
        if not instance then
            return ToolHelpers.FormatErrorResult(("Instance not found at path: %s. %s"):format(instancePath, err or ""))
        end

        local descendants = instance:GetDescendants()
        local descendantsInfo = {}

        for _, descendant in ipairs(descendants) do
            table.insert(descendantsInfo, {
                name = descendant.Name,
                path = descendant:GetFullName(),
                class_name = descendant.ClassName
            })
        end

        return ToolHelpers.FormatSuccessResult({
            message = ("Found %d descendants for instance %s."):format(#descendantsInfo, instancePath),
            instance_path = instancePath,
            descendants = descendantsInfo
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in GetDescendantsOfInstance: " .. tostring(pcall_result))
    end
end

return execute
