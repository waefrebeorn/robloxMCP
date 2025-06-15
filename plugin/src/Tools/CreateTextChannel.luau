-- CreateTextChannel.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local TextChatService = game:GetService("TextChatService")

local function execute(args)
    -- Arguments are now expected directly on args table
    local success, pcall_result = pcall(function()
        local channelName = args.channel_name
        local properties = args.properties -- Optional, expecting a Lua table

        if not channelName or type(channelName) ~= "string" or channelName == "" then
            return ToolHelpers.FormatErrorResult("'channel_name' is required and must be a non-empty string.")
        end

        properties = properties or {} -- Default to empty table
        if type(properties) ~= "table" then
            return ToolHelpers.FormatErrorResult("'properties', if provided, must be a table.")
        end

        if not TextChatService then
            return ToolHelpers.FormatErrorResult("TextChatService not available. This service is essential for TextChannel creation.")
        end

        if TextChatService:FindFirstChild(channelName) then
            return ToolHelpers.FormatErrorResult(("TextChannel '%s' already exists in TextChatService."):format(channelName))
        end

        local newChannel = Instance.new("TextChannel")
        newChannel.Name = channelName

        local propertyErrors = {}
        if properties then
            for propName, propValueInput in pairs(properties) do
                if string.lower(propName) == "parent" then
                    -- TextChannels are always parented to TextChatService.
                    print("CreateTextChannel: 'Parent' property in 'properties' table is ignored.")
                    goto continue_loop
                end

                -- Use JsonToRobloxValue for each property value
                local convertedValue, convertError = ToolHelpers.JsonToRobloxValue(propValueInput, "TextChannel."..propName)
                if convertError then
                    table.insert(propertyErrors, ("Property '%s': Failed to convert input value: %s"):format(propName, convertError))
                else
                    local setSuccess, setError = pcall(function()
                        newChannel[propName] = convertedValue
                    end)
                    if not setSuccess then
                        table.insert(propertyErrors, ("Property '%s': Error setting value: %s"):format(propName, setError))
                    end
                end
                ::continue_loop::
            end
        end

        if #propertyErrors > 0 then
            newChannel:Destroy()
            return ToolHelpers.FormatErrorResult(("Error(s) applying properties to new TextChannel '%s': %s"):format(channelName, table.concat(propertyErrors, "; ")))
        end

        newChannel.Parent = TextChatService

        return ToolHelpers.FormatSuccessResult({
            message = ("Successfully created TextChannel '%s'."):format(channelName),
            channel_name = newChannel.Name,
            channel_path = newChannel:GetFullName()
        })
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in CreateTextChannel: " .. tostring(pcall_result))
    end
end

return execute
