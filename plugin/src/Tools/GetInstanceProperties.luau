-- GetInstanceProperties.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Types = require(Main.Types)

local function execute(args: Types.GetInstancePropertiesArgs)
    print(("[GetInstanceProperties] Executing. Path: %s, PropertyNames: %s, FetchAll: %s"):format(
        tostring(args.path),
        args.property_names and table.concat(args.property_names, ", ") or "nil (fetch all)",
        tostring(args.property_names == nil or (type(args.property_names) == "table" and #args.property_names == 0))
    ))
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
            -- The previous attempt to use GetProperties has been removed.
            -- We will now directly use the commonProps list, which includes class-specific additions.
            local allPropertiesToTry = commonProps
            print("[GetInstanceProperties] Fetching all common properties. List: ", table.concat(allPropertiesToTry, ", "))

			for _, propNameString in ipairs(allPropertiesToTry) do
                print("[GetInstanceProperties] Attempting to get property: " .. propNameString)
				local getSuccess, propValue = pcall(function()
					return instance[propNameString]
				end)

				if getSuccess then
                    print("[GetInstanceProperties] Successfully got property: " .. propNameString .. " Type: " .. typeof(propValue))
					retrievedProperties[propNameString] = propValue
				else
                    print("[GetInstanceProperties] Failed to get property: " .. propNameString .. " Error: " .. tostring(propValue))
					-- Silently ignore errors when fetching all, or add to errors if desired
					accessErrors[propNameString] = "Error fetching property: " .. tostring(propValue)
				end
			end
			if #accessErrors == 0 then -- Check if accessErrors is empty using #
				accessErrors = nil -- Set to nil if no errors
			end

		else -- Specific property names were provided
            print("[GetInstanceProperties] Fetching specific properties: ", propertyNamesInput and table.concat(propertyNamesInput, ", ") or "nil")
			for _, propNameString in ipairs(propertyNamesInput) do
				if type(propNameString) == "string" then
                    print("[GetInstanceProperties] Attempting to get property: " .. propNameString)
					local getSuccess, propValue = pcall(function()
						return instance[propNameString]
					end)

					if getSuccess then
                        print("[GetInstanceProperties] Successfully got property: " .. propNameString .. " Type: " .. typeof(propValue))
						retrievedProperties[propNameString] = propValue
					else
                        print("[GetInstanceProperties] Failed to get property: " .. propNameString .. " Error: " .. tostring(propValue))
						accessErrors[propNameString] = "Error getting property: " .. tostring(propValue)
					end
				else
                    print("[GetInstanceProperties] Invalid property name type in list: " .. type(propNameString) .. " Value: " .. tostring(propNameString))
					accessErrors[tostring(#accessErrors + 1)] = ("All 'property_names' must be strings. Found entry with type: %s"):format(type(propNameString))
				end
			end
			if #accessErrors == 0 then -- Check if accessErrors is empty using #
				accessErrors = nil -- Set to nil if no errors
			end
		end


		local messageText = ("Successfully retrieved %d properties for instance '%s'."):format(ToolHelpers.TableLength(retrievedProperties), path)
		if accessErrors then
			messageText = messageText .. (" Encountered %d errors retrieving some requested properties."):format(ToolHelpers.TableLength(accessErrors))
		end

        print(("[GetInstanceProperties] Preparing to return data. Properties count: %d, Errors count: %d"):format(
            ToolHelpers.TableLength(retrievedProperties),
            accessErrors and ToolHelpers.TableLength(accessErrors) or 0
        ))
		local dataToReturn = {
			message = messageText,
			instance_path = path,
			properties = retrievedProperties, -- retrievedProperties will be {} if main logic was previously commented
		}
		if accessErrors then
			dataToReturn.errors = accessErrors
		end

		return dataToReturn


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
			errors = { internal_error = tostring(resultOrError) }, -- Potential typo here: resultOrRrror should likely be resultOrError
		})
	end
end

return execute
