-- GetInstanceProperties.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Types = require(Main.Types)

local function execute(args: Types.GetInstancePropertiesArgs)
	local success, resultOrError = pcall(function()
		local path = args.path
		local propertyNamesInput = args.property_names -- Renamed to avoid conflict with loop variable

		if not path or type(path) ~= "string" then
			return {
				message = "Error: 'path' is required and must be a string.",
				instance_path = path or "nil",
				properties = {},
				errors = { path_error = "'path' is required and must be a string." },
			}
		end

		local instance, err = ToolHelpers.FindInstanceByPath(path)
		if not instance then
			return {
				message = ("Failed to find instance at path: %s. %s"):format(path, err or "Unknown error"),
				instance_path = path,
				properties = {},
				errors = { instance_error = ("Failed to find instance at path: %s. %s"):format(path, err or "Unknown error") },
			}
		end

		local retrievedProperties: { [string]: any } = {}
		local accessErrors: { [string]: string } = {} -- Changed to dictionary for easier property-specific errors

		local fetchAllProperties = false
		if propertyNamesInput == nil or (type(propertyNamesInput) == "table" and #propertyNamesInput == 0) then
			fetchAllProperties = true
		elseif type(propertyNamesInput) ~= "table" then
			return {
				message = "Error: 'property_names' must be an array of strings if provided.",
				instance_path = path,
				properties = {},
				errors = { property_names_error = "'property_names' must be an array of strings if provided." },
			}
		end

		if fetchAllProperties then
			-- Attempt to get all scriptable properties
			-- Note: Instance:GetProperties() is Studio-only and might not work in all contexts
			-- For now, we'll rely on a simpler approach if GetProperties isn't directly available
			-- or fallback to a predefined set if necessary. This example tries to get common ones.
			-- A more robust solution might involve specific handling for different ClassNames.
			local commonProps = { "Name", "ClassName", "Parent", "Position", "Size", "Color", "Transparency", "Material", "Anchored", "CanCollide", "CFrame", "Orientation", "Position" }
			local classSpecificProps = {}

			if typeof(instance) == "Instance" and instance:IsA("BasePart") then
				table.insert(commonProps, "Shape")
				table.insert(commonProps, "BrickColor")
			elseif typeof(instance) == "Instance" and instance:IsA("Humanoid") then
				table.insert(commonProps, "Health")
				table.insert(commonProps, "MaxHealth")
				table.insert(commonProps, "WalkSpeed")
			end

			-- For now, just use a combined list of common and some class-specific props as a proxy for "all"
            -- A true "all scriptable" is hard without :GetProperties() in all environments or a massive lookup table.
            -- The provided `instance:GetProperties()` is the ideal if available.
            -- This simplified approach will try to get the common ones.

            local allPropertiesToTry = {}
            if instance.GetProperties then -- Check if method exists
                pcall(function() -- Wrap in pcall in case GetProperties itself errors
                    local studioProps = instance:GetProperties()
                    for _, propInfo in ipairs(studioProps) do
                        if type(propInfo) == "table" and propInfo.Name then
                            table.insert(allPropertiesToTry, propInfo.Name)
                        elseif type(propInfo) == "string" then -- Some versions might return array of strings
                             table.insert(allPropertiesToTry, propInfo)
                        end
                    end
                end)
            end
            -- If GetProperties wasn't available or didn't populate, use common ones
            if #allPropertiesToTry == 0 then
                allPropertiesToTry = commonProps -- Fallback to commonProps
            end

			for _, propNameString in ipairs(allPropertiesToTry) do
				local getSuccess, propValue = pcall(function()
					return instance[propNameString]
				end)

				if getSuccess then
					retrievedProperties[propNameString] = ToolHelpers.SerializeValue(propValue)
				else
					-- Silently ignore errors when fetching all, or add to errors if desired
					-- accessErrors[propNameString] = "Error fetching property: " .. tostring(propValue)
				end
			end
			if #accessErrors == 0 then -- Check if accessErrors is empty using #
				accessErrors = nil -- Set to nil if no errors
			end

		else -- Specific property names were provided
			for _, propNameString in ipairs(propertyNamesInput) do
				if type(propNameString) ~= "string" then
					accessErrors[tostring(#accessErrors + 1)] = ("All 'property_names' must be strings. Found entry with type: %s"):format(type(propNameString))
					goto continueLoop -- Skips to next iteration using goto
				end

				local getSuccess, propValue = pcall(function()
					return instance[propNameString]
				end)

				if getSuccess then
					retrievedProperties[propNameString] = ToolHelpers.SerializeValue(propValue)
				else
					accessErrors[propNameString] = "Error getting property: " .. tostring(propValue)
				end
				::continueLoop::
			end
			if #accessErrors == 0 then -- Check if accessErrors is empty using #
				accessErrors = nil -- Set to nil if no errors
			end
		end

		local message = ("Successfully retrieved %d properties for instance '%s'."):format(ToolHelpers.TableLength(retrievedProperties), path)
		if accessErrors then
			message = message .. (" Encountered %d errors retrieving some requested properties."):format(ToolHelpers.TableLength(accessErrors))
		end

		local resultData: Types.GetInstancePropertiesResultData = {
			message = message,
			instance_path = path,
			properties = retrievedProperties,
		}
		if accessErrors then -- only include errors table if there are errors
			resultData.errors = accessErrors
		end
		return resultData
	end)

	if success then
		if resultOrError.message and resultOrError.message:match("^Error:") then -- Check if it's one of my custom error tables
			return ToolHelpers.FormatErrorResult(resultOrError)
		else
			return ToolHelpers.FormatSuccessResult(resultOrError)
		end
	else
		-- This is a critical error in the pcall itself (e.g. syntax error in the protected code)
		return ToolHelpers.FormatErrorResult({
			message = "Internal script error in GetInstanceProperties: " .. tostring(resultOrError),
			instance_path = args.path or "nil",
			properties = {},
			errors = { internal_error = tostring(resultOrError) },
		})
	end
end

return execute
