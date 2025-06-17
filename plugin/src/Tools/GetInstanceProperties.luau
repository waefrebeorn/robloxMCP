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
			return { error_type = "InvalidArguments", message = "'path' is required and must be a string." }
		end

		local instance, err = ToolHelpers.FindInstanceByPath(path)
		if not instance then
			return { error_type = "InstanceNotFound", message = ("Failed to find instance at path: %s. %s"):format(path, err or "Unknown error") }
		end

		local retrievedProperties: { [string]: any } = {}
		local accessErrors: { [string]: string } = {} -- Changed to dictionary for easier property-specific errors

		local propertiesToFetch
		if propertyNamesInput == nil or (type(propertyNamesInput) == "table" and #propertyNamesInput == 0) then
			-- Default to a minimal set if no specific properties are requested
			propertiesToFetch = { "Name", "ClassName", "Parent" }
            print("[GetInstanceProperties] No specific properties requested, using default minimal set: Name, ClassName, Parent")
		elseif type(propertyNamesInput) == "table" then
			propertiesToFetch = propertyNamesInput
            print("[GetInstanceProperties] Fetching specific properties: ", table.concat(propertiesToFetch, ", "))
		else
			return { error_type = "InvalidArguments", message = "'property_names' must be an array of strings if provided." }
		end

        for _, propNameString in ipairs(propertiesToFetch) do
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
                accessErrors[tostring(ToolHelpers.TableLength(accessErrors) + 1)] = ("All 'property_names' must be strings. Found entry with type: %s"):format(type(propNameString))
            end
        end

        if ToolHelpers.TableLength(accessErrors) == 0 then
            accessErrors = nil -- Set to nil if no errors
        end

		local messageText
        local numRetrieved = ToolHelpers.TableLength(retrievedProperties)
        local numErrors = accessErrors and ToolHelpers.TableLength(accessErrors) or 0

        if numRetrieved > 0 and numErrors == 0 then
            messageText = ("Successfully retrieved %d properties for instance '%s'."):format(numRetrieved, path)
        elseif numRetrieved > 0 and numErrors > 0 then
            messageText = ("Retrieved %d properties for instance '%s' with %d errors."):format(numRetrieved, path, numErrors)
        elseif numRetrieved == 0 and numErrors > 0 then
            messageText = ("Failed to retrieve any properties for instance '%s'. Encountered %d errors."):format(path, numErrors)
        else -- numRetrieved == 0 and numErrors == 0 (e.g. requested empty list of props, or default list resulted in no valid props somehow)
            messageText = ("No properties were requested or retrieved for instance '%s'."):format(path)
        end

        print(("[GetInstanceProperties] Preparing to return data. Properties count: %d, Errors count: %d"):format(
            numRetrieved,
            numErrors
        ))
		local dataToReturn = {
			message = messageText,
			instance_path = path,
			properties = retrievedProperties,
		}
		if accessErrors then
			dataToReturn.errors = accessErrors
		end

		return dataToReturn
	end)

	if success then
        if resultOrError and resultOrError.error_type then -- Check for our custom error table structure
            return ToolHelpers.FormatErrorResult(resultOrError.message, resultOrError)
        else
            return ToolHelpers.FormatSuccessResult(resultOrError)
        end
    else
        -- This is a critical error in the pcall itself (e.g. syntax error in the protected code)
        return ToolHelpers.FormatErrorResult("Internal script error in GetInstanceProperties: " .. tostring(resultOrError), { internal_error_details = tostring(resultOrError) })
    end
end

return execute
