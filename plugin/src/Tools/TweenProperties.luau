-- TweenProperties.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Types = require(Main.Types)
local TweenService = game:GetService("TweenService")

local function execute(args: Types.TweenPropertiesArgs)
    -- Arguments are expected directly on args table
    local success, pcall_result = pcall(function()
        local instancePath = args.instance_path
        local duration = args.duration
        local easingStyleStr = args.easing_style
        local easingDirectionStr = args.easing_direction
        local propertiesToTween = args.properties_to_tween -- Expecting Lua table {propName = value, ...}

        -- Optional params for TweenInfo
        local repeatCount = args.repeat_count
        local reverses = args.reverses
        local delayTime = args.delay_time

        if not instancePath or type(instancePath) ~= "string" then
            return ToolHelpers.FormatErrorResult("'instance_path' is required and must be a string.")
        end
        if not duration or type(duration) ~= "number" or duration <= 0 then
            return ToolHelpers.FormatErrorResult("'duration' must be a positive number.")
        end
        if not easingStyleStr or type(easingStyleStr) ~= "string" then
            return ToolHelpers.FormatErrorResult("'easing_style' (Enum.EasingStyle name) is required and must be a string.")
        end
        if not easingDirectionStr or type(easingDirectionStr) ~= "string" then
            return ToolHelpers.FormatErrorResult("'easing_direction' (Enum.EasingDirection name) is required and must be a string.")
        end
        if not propertiesToTween or type(propertiesToTween) ~= "table" then
            return ToolHelpers.FormatErrorResult("'properties_to_tween' is required and must be a table.")
        end
        if next(propertiesToTween) == nil then
             return ToolHelpers.FormatErrorResult("'properties_to_tween' table cannot be empty.")
        end

        local instance, err = ToolHelpers.FindInstanceByPath(instancePath)
        if not instance then
            return ToolHelpers.FormatErrorResult("Failed to find instance at path: " .. instancePath .. ". " .. (err or ""))
        end

        local easingStyle = Enum.EasingStyle[easingStyleStr]
        if not easingStyle then
            return ToolHelpers.FormatErrorResult("Invalid EasingStyle: " .. easingStyleStr .. ". Refer to Enum.EasingStyle.")
        end
        local easingDirection = Enum.EasingDirection[easingDirectionStr]
        if not easingDirection then
            return ToolHelpers.FormatErrorResult("Invalid EasingDirection: " .. easingDirectionStr .. ". Refer to Enum.EasingDirection.")
        end

        local tweenInfo = TweenInfo.new(
            duration,
            easingStyle,
            easingDirection,
            repeatCount or 0, -- Default to 0 if nil
            reverses or false,  -- Default to false if nil
            delayTime or 0    -- Default to 0 if nil
        )

        local propertiesGoal = {}
        -- local conversionErrors = {} -- Removed, direct assignment now
        for propName, propValueInput in pairs(propertiesToTween) do
            -- No conversion needed, propValueInput is expected to be the correct Luau type.
            -- ToolHelpers.JsonToRobloxValue call removed.
            -- Type errors will be caught by TweenService:Create if types are incompatible.
            propertiesGoal[propName] = propValueInput -- Use propValueInput directly
        end

        -- Removed conversionErrors check. If propertiesToTween was empty, next(propertiesGoal) will be nil.
        -- The original propertiesToTween emptiness check already covers this.
        if next(propertiesGoal) == nil then
            -- This check is technically redundant if the input 'properties_to_tween' cannot be empty (which it can't by an earlier check)
            -- but kept for safety in case that input check changes.
            return ToolHelpers.FormatErrorResult("No valid properties to tween (properties_to_tween was empty or became empty).")
        end

        local tweenCreateSuccess, tweenOrError = pcall(TweenService.Create, TweenService, instance, tweenInfo, propertiesGoal)
        if not tweenCreateSuccess then
             return ToolHelpers.FormatErrorResult("TweenService:Create failed: " .. tostring(tweenOrError))
        end
        local tween = tweenOrError

        tween:Play()
        -- This tool fires the tween and returns. It does not yield/wait for tween completion.

        return ToolHelpers.FormatSuccessResult({
            message = ("Tween started for instance %s with duration %.2fs."):format(instancePath, duration),
            instance_path = instancePath,
            duration = duration,
            easing_style_used = easingStyleStr,
            easing_direction_used = easingDirectionStr,
            properties_goal = propertiesGoal -- Pass the raw Lua table
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in TweenProperties: " .. tostring(pcall_result))
    end
end

return execute
