-- GetChildrenOfInstance.luau
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

        local children = instance:GetChildren()
        local childrenInfo = {}

        for _, child in ipairs(children) do
            table.insert(childrenInfo, {
                name = child.Name,
                path = child:GetFullName(),
                class_name = child.ClassName
            })
        end

        return ToolHelpers.FormatSuccessResult({
            message = ("Found %d children for instance %s."):format(#childrenInfo, instancePath),
            instance_path = instancePath,
            children = childrenInfo
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in GetChildrenOfInstance: " .. tostring(pcall_result))
    end
end

return execute
