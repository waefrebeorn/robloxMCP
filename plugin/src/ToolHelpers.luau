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

function ToolHelpers.ConvertTableToRobloxType(inputTable, propertyName, instance)
    if type(inputTable) ~= "table" then
        return inputTable, nil -- Not a table, no conversion needed
    end

    -- Infer type from property name (case-insensitive)
    local lowerPropName = string.lower(propertyName)

    if string.find(lowerPropName, "color") then -- Matches "Color", "BackgroundColor3", "TextColor3", etc.
        if inputTable.r ~= nil and inputTable.g ~= nil and inputTable.b ~= nil then
            local r, g, b = tonumber(inputTable.r), tonumber(inputTable.g), tonumber(inputTable.b)
            if r and g and b then
                return Color3.new(r, g, b), nil
            else
                return inputTable, "Invalid Color3 components: r, g, b must be numbers."
            end
        else
            return inputTable, "Missing r, g, or b fields for Color3."
        end
    elseif lowerPropName == "position" or lowerPropName == "size" or string.find(lowerPropName, "vector3") then
        -- Check if it's for a GUI object's Position/Size (UDim2) vs a Part's Position/Size (Vector3)
        local isGui = false
        if instance then
            pcall(function() if instance:IsA("GuiObject") or instance:IsA("GuiBase2d") then isGui = true end end)
        end

        if isGui and (lowerPropName == "position" or lowerPropName == "size") then -- UDim2 for GuiObject
            if inputTable.x_scale ~= nil and inputTable.x_offset ~= nil and inputTable.y_scale ~= nil and inputTable.y_offset ~= nil then
                local xs, xo, ys, yo = tonumber(inputTable.x_scale), tonumber(inputTable.x_offset), tonumber(inputTable.y_scale), tonumber(inputTable.y_offset)
                if xs and xo and ys and yo then
                    return UDim2.new(xs, xo, ys, yo), nil
                else
                    return inputTable, "Invalid UDim2 components: x_scale, x_offset, y_scale, y_offset must be numbers."
                end
            else
                return inputTable, "Missing x_scale, x_offset, y_scale, or y_offset for UDim2."
            end
        elseif not isGui and (lowerPropName == "position" or lowerPropName == "size" or string.find(lowerPropName, "vector3")) then -- Vector3
            if inputTable.x ~= nil and inputTable.y ~= nil and inputTable.z ~= nil then
                local x, y, z = tonumber(inputTable.x), tonumber(inputTable.y), tonumber(inputTable.z)
                if x and y and z then
                    return Vector3.new(x, y, z), nil
                else
                    return inputTable, "Invalid Vector3 components: x, y, z must be numbers."
                end
            else
                return inputTable, "Missing x, y, or z fields for Vector3."
            end
        end
    elseif string.find(lowerPropName, "vector2") then
        if inputTable.x ~= nil and inputTable.y ~= nil then
            local x, y = tonumber(inputTable.x), tonumber(inputTable.y)
            if x and y then
                return Vector2.new(x, y), nil
            else
                return inputTable, "Invalid Vector2 components: x, y must be numbers."
            end
        else
            return inputTable, "Missing x or y fields for Vector2."
        end
    elseif string.find(lowerPropName, "udim2") then -- Explicit UDim2
        if inputTable.x_scale ~= nil and inputTable.x_offset ~= nil and inputTable.y_scale ~= nil and inputTable.y_offset ~= nil then
            local xs, xo, ys, yo = tonumber(inputTable.x_scale), tonumber(inputTable.x_offset), tonumber(inputTable.y_scale), tonumber(inputTable.y_offset)
            if xs and xo and ys and yo then
                return UDim2.new(xs, xo, ys, yo), nil
            else
                return inputTable, "Invalid UDim2 components: x_scale, x_offset, y_scale, y_offset must be numbers."
            end
        else
            return inputTable, "Missing x_scale, x_offset, y_scale, or y_offset for UDim2."
        end
    elseif string.find(lowerPropName, "udim") then -- Catch UDim (single scale/offset)
        if inputTable.scale ~= nil and inputTable.offset ~= nil then
            local s, o = tonumber(inputTable.scale), tonumber(inputTable.offset)
            if s and o then
                return UDim.new(s, o), nil
            else
                return inputTable, "Invalid UDim components: scale, offset must be numbers."
            end
        else
            return inputTable, "Missing scale or offset fields for UDim."
        end
    elseif string.find(lowerPropName, "rect") then
         if inputTable.min_x ~= nil and inputTable.min_y ~= nil and inputTable.max_x ~= nil and inputTable.max_y ~= nil then
            local minx, miny, maxx, maxy = tonumber(inputTable.min_x), tonumber(inputTable.min_y), tonumber(inputTable.max_x), tonumber(inputTable.max_y)
            if minx and miny and maxx and maxy then
                return Rect.new(minx, miny, maxx, maxy), nil
            else
                return inputTable, "Invalid Rect components: min_x, min_y, max_x, max_y must be numbers."
            end
        else
            return inputTable, "Missing min_x, min_y, max_x, or max_y for Rect."
        end
    elseif string.find(lowerPropName, "numberrange") then
        if inputTable.min_value ~= nil and inputTable.max_value ~= nil then
            local minVal, maxVal = tonumber(inputTable.min_value), tonumber(inputTable.max_value)
            if minVal and maxVal then
                return NumberRange.new(minVal, maxVal), nil
            else
                return inputTable, "Invalid NumberRange components: min_value, max_value must be numbers."
            end
        else
            return inputTable, "Missing min_value or max_value for NumberRange."
        end
    end

    -- If no specific conversion rule matched, return the original table
    return inputTable, nil
end

return ToolHelpers
