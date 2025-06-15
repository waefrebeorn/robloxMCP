-- DeleteInstance.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local path = args.path

        if not path or type(path) ~= "string" then
            return ToolHelpers.FormatErrorResult("'path' is required and must be a string.")
        end

        local instance, err = ToolHelpers.FindInstanceByPath(path)
        if not instance then
            return ToolHelpers.FormatSuccessResult({
                message = "Instance at path '" .. path .. "' not found, presumed already deleted. " .. (err or ""),
                path_not_found = path
            })
        end

        if instance == workspace or instance:IsA("ServiceProvider") or instance:IsA("Terrain") then
             return ToolHelpers.FormatErrorResult("Cannot delete core services, the workspace root, or Terrain: " .. path)
        end

        local destroySuccess, destroyError = pcall(instance.Destroy, instance)

        if not destroySuccess then
            return ToolHelpers.FormatErrorResult(("Failed to delete instance at path '%s': %s"):format(path, tostring(destroyError)))
        end

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully deleted instance at path %s."):format(path),
            deleted_path = path
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in DeleteInstance: " .. tostring(pcall_result))
    end
end

return execute
