-- GetProperties.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)

return function(args)
	if not args["GetProperties"] then
		-- This indicates a mismatch in how the tool was called, likely an issue with the agent's request structure.
		return ToolHelpers.FormatErrorResult("GetProperties: Invalid argument structure. Expected 'GetProperties' key.")
	end

	local data = args["GetProperties"]
	local path = data.path
	local propertiesToGet = data.properties

	if not path or type(path) ~= "string" or not propertiesToGet or type(propertiesToGet) ~= "table" then
		return ToolHelpers.FormatErrorResult("GetProperties: Missing or invalid 'path' (string) or 'properties' (table) in arguments.")
	end

	-- Attempt to find the instance.
	local instance = workspace:FindFirstChild(path, true) -- Recursive search

	if not instance then
		return ToolHelpers.FormatErrorResult("GetProperties: Instance not found at path: " .. path)
	end

	local results = {}
	local anErrorOccurredInProperties = false
	for _, propName in ipairs(propertiesToGet) do
		local success, valueOrError = pcall(function()
			return instance[propName]
		end)

		if success then
			-- Serialize complex types to be JSON-friendly for FormatSuccessResult
			if typeof(valueOrError) == "Instance" then
				results[propName] = valueOrError:GetFullName()
			elseif typeof(valueOrError) == "Color3" then
				results[propName] = {r = valueOrError.R, g = valueOrError.G, b = valueOrError.B}
			elseif typeof(valueOrError) == "Vector3" then
				results[propName] = {x = valueOrError.X, y = valueOrError.Y, z = valueOrError.Z}
			elseif typeof(valueOrError) == "Vector2" then
				results[propName] = {x = valueOrError.X, y = valueOrError.Y}
			-- Consider adding more handlers for types like CFrame, EnumItem, NumberRange, etc.
			-- For types that SafeJsonEncode in ToolHelpers can handle (primitives, simple tables), direct assignment is fine.
			else
				results[propName] = valueOrError
			end
		else
			results[propName] = { error = "Property '" .. propName .. "' not found or not readable: " .. tostring(valueOrError) }
			anErrorOccurredInProperties = true -- Mark that at least one property had an issue.
		end
	end

	-- Even if some properties failed, the overall tool execution might be considered a success,
	-- returning the results obtained. The `isError` flag at this level indicates if the tool
	-- itself failed catastrophically (e.g. instance not found).
	-- If specific properties had errors, `anErrorOccurredInProperties` could be used by the agent
	-- to further inspect the `results` table.
	-- For now, the main `isError` reflects the tool's ability to find the instance and attempt gets.
	return ToolHelpers.FormatSuccessResult(results)
end
