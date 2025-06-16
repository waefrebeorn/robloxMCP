-- ToolHelpers.luau
local ToolHelpers = {}

local HttpService = game:GetService("HttpService")

function ToolHelpers.FindInstanceByPath(pathString)
    if not pathString or type(pathString) ~= "string" or pathString == "" then
        return nil, "Path is nil, not a string, or empty."
    end

    local lowerPath = string.lower(pathString)
    if lowerPath == "workspace" then return workspace, nil end
    if lowerPath == "lighting" then return game:GetService("Lighting"), nil end
    if lowerPath == "soundservice" then return game:GetService("SoundService"), nil end
    if lowerPath == "replicatedstorage" then return game:GetService("ReplicatedStorage"), nil end
    if lowerPath == "serverstorage" then return game:GetService("ServerStorage"), nil end
    if lowerPath == "serverplayers" or lowerPath == "players" then return game:GetService("Players"), nil end
    if lowerPath == "starterplayer" then return game:GetService("StarterPlayer"), nil end
    if lowerPath == "starterplayerscripts" then return game:GetService("StarterPlayer").StarterPlayerScripts, nil end
    if lowerPath == "startercharacterscripts" then return game:GetService("StarterPlayer").StarterCharacterScripts, nil end
    if lowerPath == "startergui" then return game:GetService("StarterGui"), nil end
    if lowerPath == "starterpack" then return game:GetService("StarterPack"), nil end
    if lowerPath == "serverscriptservice" then return game:GetService("ServerScriptService"), nil end
    if lowerPath == "teams" then return game:GetService("Teams"), nil end
    if lowerPath == "textchatservice" then return game:GetService("TextChatService"), nil end
    if lowerPath == "userinputservice" then return game:GetService("UserInputService"), nil end
     -- Path for PlayerGui typically needs player name, e.g. "Players.LocalPlayer.PlayerGui"
    -- However, if just "PlayerGui" is passed for a ScreenGui, some tools might try to resolve LocalPlayer.PlayerGui.
    -- For direct access, a full path is better. This helper won't assume LocalPlayer here.


    local current = game
    for part in string.gmatch(pathString, "[^%.]+") do
        if not current or typeof(current) ~= "Instance" then
             return nil, "Invalid path segment: " .. part .. " - parent is not an Instance or nil."
        end
        current = current:FindFirstChild(part)
        if not current then
            return nil, "Instance not found at segment: " .. part .. " in path " .. pathString
        end
    end
    return current
end

-- Standard response formatters

function ToolHelpers.SimpleTableToString(data)
    if type(data) ~= "table" then
        return "nil (not a table)"
    end

    local parts = {}
    local count = 0
    local totalLength = 0
    local maxPairs = 10
    local maxLength = 200
    -- complexValueFound is not strictly needed with the simpleValuesCount logic later
    -- local complexValueFound = false

    for key, value in pairs(data) do
        count = count + 1
        if count > maxPairs and key ~= "message" then -- Allow message to be processed even if it exceeds pair limit initially
            table.insert(parts, "...")
            break
        end

        local keyStr = tostring(key)
        local valueStr

        local valueType = type(value)
        if valueType == "string" or valueType == "number" or valueType == "boolean" then
            valueStr = tostring(value)
        elseif valueType == "table" then
            valueStr = "[table]"
            -- complexValueFound = true
        elseif valueType == "nil" then
            valueStr = "nil"
        else
            valueStr = "[" .. valueType .. "]"
            -- complexValueFound = true
        end

        if keyStr == "message" and (valueType == "string" or valueType == "number" or valueType == "boolean") then
            if string.len(valueStr) < maxLength - 5 and string.len(valueStr) > 0 then -- -5 for "..." buffer
                return valueStr -- Prioritize and return message directly if it's suitable
            elseif count > maxPairs then -- If message was the one that exceeded pair limit, but is too long
                 local truncatedMessage = string.sub(valueStr, 1, maxLength - 3) .. "..."
                 return truncatedMessage
            end
        end

        local pairStr = keyStr .. "=" .. valueStr
        -- Check length before adding, ensuring "..." can also fit if this is the last item before truncation
        if totalLength + string.len(pairStr) + 1 > maxLength - (if count >= maxPairs then 0 else string.len("...;")) then
            table.insert(parts, "...")
            break
        end
        table.insert(parts, pairStr)
        totalLength = totalLength + string.len(pairStr) + 1 -- +1 for semicolon
    end

    if #parts == 0 then
        if count > 0 and data.message then -- Handle case where only a long message existed
            local valueStr = tostring(data.message)
            local truncatedMessage = string.sub(valueStr, 1, maxLength - 3) .. "..."
            return truncatedMessage
        end
        return "empty table"
    end

    local simpleValuesCount = 0
    for _, partStr in ipairs(parts) do
        if not string.match(partStr, "%[table%]") and not string.match(partStr, "%[.+%]") and partStr ~= "..." then
            simpleValuesCount = simpleValuesCount + 1
        end
    end

    if simpleValuesCount == 0 and #parts > 0 then
        local firstPart = parts[1]
        if firstPart ~= "empty table" and firstPart ~= "nil (not a table)" and not (data.message and count==1) then
             -- if it's just a "message" field that was too long and got truncated to "...", return that.
            if data.message and count == 1 and parts[1] == "..." and string.len(tostring(data.message)) > maxLength then
                 local truncatedMessage = string.sub(tostring(data.message), 1, maxLength - 3) .. "..."
                 return truncatedMessage
            end
            return nil
        end
    end

    local finalStr = table.concat(parts, ";")
    if finalStr ~= "..." and finalStr ~= "" and not string.match(finalStr, ";$") then -- Add trailing semicolon if not just "..." or empty
        finalStr = finalStr .. ";"
    end
    -- Ensure final string does not exceed maxLength due to joining/semicolons, though previous checks should mostly prevent this.
    if string.len(finalStr) > maxLength then
        finalStr = string.sub(finalStr, 1, maxLength - 3) .. "..."
    end

    return finalStr
end

function ToolHelpers.FormatSuccessResult(data)
    local formattedString = ToolHelpers.SimpleTableToString(data)

    if formattedString and #formattedString > 0 then
        -- Ensure the 'text' field is the potentially simplified string.
        return { content = { { type = "text", text = formattedString } }, isError = false }
    else
        -- If SimpleTableToString returns nil or empty, use a generic success message.
        return { content = { { type = "text", text = "Operation successful." } }, isError = false }
    end
end

function ToolHelpers.FormatErrorResult(errorMessageString, _errorType) -- _errorType is not used in the new format
    return { content = { { type = "text", text = errorMessageString or "An unspecified error occurred." } }, isError = true }
end

function ToolHelpers.StringToEnum(enumString)
    if type(enumString) ~= "string" then return nil, "Input not a string" end
    if string.sub(enumString, 1, 5) ~= "Enum." then return nil, "Not an Enum string format" end

    local parts = {}
    for part in string.gmatch(enumString, "[^%.]+") do table.insert(parts, part) end

    if #parts < 3 then return nil, "Enum string format incorrect (e.g., Enum.Category.Item)" end

    local enumCategoryName = parts[2]
    local enumItemName = table.concat(parts, ".", 3) -- Handles cases like Enum.UserInputType.MouseButton1

    if Enum[enumCategoryName] then
        local enumCategory = Enum[enumCategoryName]
        if enumCategory[enumItemName] then
            return enumCategory[enumItemName]
        else
            return nil, ("Enum item '%s' not found in Enum.%s"):format(enumItemName, enumCategoryName)
        end
    else
        return nil, ("Enum category '%s' not found."):format(enumCategoryName)
    end
end

function ToolHelpers.TableLength(t)
    if type(t) ~= "table" then
        return 0
    end
    local count = 0
    for _ in pairs(t) do
        count = count + 1
    end
    return count
end

return ToolHelpers
