-- PlaySoundId.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Types = require(Main.Types)

local function execute(args: Types.PlaySoundIdArgs)
    -- Arguments are expected directly on args table
    local success, pcall_result = pcall(function()
        local soundId = args.sound_id
        local parentPath = args.parent_path -- Optional, if nil, sound is parented to a temporary container or not at all if not playing.
        local properties = args.properties or {}

        if not soundId or type(soundId) ~= "string" then
            return ToolHelpers.FormatErrorResult("'sound_id' is required and must be a string (e.g., 'rbxassetid://123').")
        end
        if parentPath ~= nil and type(parentPath) ~= "string" then -- Only validate if provided
            return ToolHelpers.FormatErrorResult("'parent_path' must be a string if provided.")
        end
        if type(properties) ~= "table" then
            return ToolHelpers.FormatErrorResult("'properties' must be a table if provided.")
        end

        local parentInstance = nil
        if parentPath then
            local foundParent, err = ToolHelpers.FindInstanceByPath(parentPath)
            if not foundParent then
                return ToolHelpers.FormatErrorResult(("Specified 'parent_path' (%s) not found. Error: %s"):format(parentPath, err or "Not found"))
            end
            parentInstance = foundParent
        else
            -- If no parentPath, sound will be created but not parented by default.
            -- PlayOnRemove will handle cleanup if it's temporary.
            -- Alternatively, create a temporary container in SoundService or Workspace.
            -- For now, let it be nil and rely on PlayOnRemove or explicit parenting in properties.
        end

        local soundInstance = Instance.new("Sound")
        -- soundInstance.SoundId = soundId -- Original line to be wrapped

        local assignIdSuccess, assignIdError = pcall(function()
            soundInstance.SoundId = soundId
        end)

        if not assignIdSuccess then
            soundInstance:Destroy() -- Clean up the created sound instance
            return ToolHelpers.FormatErrorResult(("Failed to assign SoundId '%s': %s"):format(tostring(soundId), tostring(assignIdError)))
        end

        local HttpService = game:GetService("HttpService") -- Ensure it's available
        local propertyErrors = {}
        for propName, propValueInput in pairs(properties) do
            if string.lower(propName) == "parent" then
                -- ... (existing parent logic remains unchanged)
                if parentInstance then
                    table.insert(propertyErrors, "Cannot set 'Parent' via properties if 'parent_path' argument is also used. Parent is already determined.")
                else
                    if type(propValueInput) == "string" then
                        local foundParentFromProp, errProp = ToolHelpers.FindInstanceByPath(propValueInput)
                        if foundParentFromProp then
                            parentInstance = foundParentFromProp
                        else
                            table.insert(propertyErrors, ("Parent path '%s' from properties not found. Error: %s"):format(propValueInput, errProp or ""))
                        end
                    elseif typeof(propValueInput) == "Instance" then
                        parentInstance = propValueInput
                    else
                        table.insert(propertyErrors, "'Parent' property must be a string path or Instance.")
                    end
                end
            else
                local finalValueToSet = propValueInput
                local conversionErrorMsg = nil

                if type(propValueInput) == "table" then
                    local converted_value, err_msg = ToolHelpers.ConvertTableToRobloxType(propValueInput, propName, soundInstance)
                    if err_msg then
                        conversionErrorMsg = err_msg
                    else
                        finalValueToSet = converted_value
                    end
                end

                if conversionErrorMsg then
                    table.insert(propertyErrors, ("Property '%s': Conversion error: %s. Original: %s"):format(
                        propName,
                        conversionErrorMsg,
                        HttpService:JSONEncode(propValueInput)
                    ))
                else
                    local setSuccess, setError = pcall(function()
                        soundInstance[propName] = finalValueToSet
                    end)
                    if not setSuccess then
                        table.insert(propertyErrors, ("Property '%s': Error setting value: %s. Original: %s, Attempted: %s"):format(
                            propName,
                            tostring(setError),
                            HttpService:JSONEncode(propValueInput),
                            HttpService:JSONEncode(finalValueToSet)
                        ))
                    end
                end
            end
        end

        if #propertyErrors > 0 then
            soundInstance:Destroy()
            return ToolHelpers.FormatErrorResult(("Error(s) applying properties to new Sound: %s"):format(table.concat(propertyErrors, "; ")))
        end

        if parentInstance then
            soundInstance.Parent = parentInstance
        else
            -- If no parent determined from args or properties, parent to SoundService for playing globally
            -- or consider not parenting if PlayOnRemove is true (which is default for SoundService children)
            soundInstance.Parent = game:GetService("SoundService")
            if not properties.PlayOnRemove then soundInstance.PlayOnRemove = true end
        end

        if not soundInstance.IsLoaded then
            soundInstance.Loaded:Wait(5) -- Increased wait time
        end

        if not soundInstance.IsLoaded then
            local msg = ("Sound '%s' (ID: %s) created under %s but failed to load in time. Playback skipped."):format(soundInstance.Name, soundId, soundInstance.Parent and soundInstance.Parent:GetFullName() or "SoundService")
            -- This is still a "success" in terms of tool execution (sound instance created), but playback failed.
            return ToolHelpers.FormatSuccessResult({
                message = msg,
                sound_path = soundInstance:GetFullName(),
                sound_id = soundId,
                is_playing = false,
                details = "Sound not loaded after wait time."
            })
        end

        soundInstance:Play()

        return ToolHelpers.FormatSuccessResult({
            message = ("Sound '%s' (ID: %s) is now playing under %s."):format(soundInstance.Name, soundId, soundInstance.Parent and soundInstance.Parent:GetFullName() or "SoundService"),
            sound_path = soundInstance:GetFullName(),
            sound_id = soundId,
            is_playing = soundInstance.IsPlaying,
            duration = soundInstance.TimeLength
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in PlaySoundId: " .. tostring(pcall_result))
    end
end

return execute
