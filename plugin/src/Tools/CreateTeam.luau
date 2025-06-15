-- CreateTeam.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local TeamsService = game:GetService("Teams")

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local teamName = args.team_name
        local teamColorBrickColorString = args.team_color_brickcolor_string
        local autoAssignable = if args.auto_assignable == nil then true else args.auto_assignable

        if not teamName or type(teamName) ~= "string" then
            return ToolHelpers.FormatErrorResult("'team_name' is required and must be a string.")
        end
        if not teamColorBrickColorString or type(teamColorBrickColorString) ~= "string" then
            return ToolHelpers.FormatErrorResult("'team_color_brickcolor_string' is required and must be a string (e.g., 'Bright red').")
        end
        if type(autoAssignable) ~= "boolean" then
            return ToolHelpers.FormatErrorResult("'auto_assignable' must be a boolean.")
        end

        if TeamsService:FindFirstChild(teamName) then
            return ToolHelpers.FormatErrorResult(("Team '%s' already exists."):format(teamName))
        end

        local teamColor = BrickColor.new(teamColorBrickColorString)
        -- As noted before, BrickColor.new() defaults to white for invalid strings.
        -- This behavior is kept unless stricter validation is required in a future task.

        local newTeam = Instance.new("Team")
        newTeam.Name = teamName
        newTeam.TeamColor = teamColor
        newTeam.AutoAssignable = autoAssignable
        newTeam.Parent = TeamsService

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully created team '%s'."):format(teamName),
            team_name = newTeam.Name,
            team_color = tostring(newTeam.TeamColor),
            auto_assignable = newTeam.AutoAssignable,
            team_path = newTeam:GetFullName()
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in CreateTeam: " .. tostring(pcall_result))
    end
end

return execute
