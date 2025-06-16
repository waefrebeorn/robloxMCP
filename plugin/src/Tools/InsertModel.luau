-- InsertModel.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)
local ToolHelpers = require(Main.ToolHelpers)

local InsertService = game:GetService("InsertService")
local CollectionService = game:GetService("CollectionService") -- For tagging if needed later

local INSERT_MAX_SEARCH_DEPTH = 2048
local INSERT_MAX_DISTANCE_AWAY = 20

local function getInsertPosition()
	local camera = workspace.CurrentCamera
	if not camera then return Vector3.new(0, 5, 0) end

	local viewportPoint = camera.ViewportSize / 2
	local unitRay = camera:ViewportPointToRay(viewportPoint.X, viewportPoint.Y, 0)

	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = game:GetService("Selection"):Get()

	local result = workspace:Raycast(unitRay.Origin, unitRay.Direction * INSERT_MAX_SEARCH_DEPTH, params)

	if result then
		return result.Position
	else
		return camera.CFrame.Position + unitRay.Direction * INSERT_MAX_DISTANCE_AWAY
	end
end

local function toTitleCase(str: string): string
	local function titleCase(first: string, rest: string)
		return first:upper() .. rest:lower()
	end
	local intermediate = string.gsub(str, "(%a)([%w_']*)", titleCase :: (string) -> string)
	return intermediate:gsub("%s+", "")
end

local function collapseObjectsIntoContainer(objects: { Instance }): Instance?
	if #objects == 0 then return nil end

	local isPhysical = false
	for _, object in objects do
		if object:IsA("PVInstance") then
			isPhysical = true
			break
		end
	end

	if isPhysical then
		local model = Instance.new("Model")
		for _, object in objects do
			object.Parent = model
		end
		return model
	end

	if #objects > 1 then
		local folder = Instance.new("Folder")
		for _, object in objects do
			object.Parent = folder
		end
		return folder
	end
	return objects[1]
end

local function actualLoadAsset(assetId: number): (boolean, Instance?, string?)
	local success, objects = pcall(InsertService.LoadAsset, InsertService, assetId) -- Use InsertService.LoadAsset
	if not success then
		return false, nil, "InsertService:LoadAsset() failed for asset ID: " .. tostring(assetId) .. ". Error: " .. tostring(objects) -- objects is error message
	end

    -- LoadAsset returns a Model instance
	if not (objects and typeof(objects) == "Instance" and objects:IsA("Model")) then
		return false, nil, "InsertService:LoadAsset() did not return a valid Model for asset ID: " .. tostring(assetId)
	end

	return true, objects :: Instance, nil
end


local function getAssetIdFromString(query: string): (boolean, number?, string?)
    local isAssetId = tonumber(query)
    if isAssetId then
        return true, isAssetId, nil
    end

	local success, results = pcall(InsertService.GetFreeModels, InsertService, query, 0)
	if not success then
		return false, nil, "InsertService:GetFreeModels() failed for query: '" .. query .. "'. Error: " .. tostring(results)
	end

	if results and results[1] and results[1].Results and #results[1].Results > 0 then
		return true, results[1].Results[1].AssetId, nil
	else
		return false, nil, "No assets found for query: '" .. query .. "'"
	end
end

-- Main logic for inserting asset
local function performInsert(query: string, parentPath: string?): (Types.InsertModelResultData?, string?)
	local assetIdOk, assetId, errorMsg = getAssetIdFromString(query)
	if not assetIdOk then
		return nil, errorMsg
	end

	local loadOk, instance, loadErrorMsg = actualLoadAsset(assetId :: number)
	if not loadOk then
		return nil, loadErrorMsg
	end

	local parent = workspace -- Default parent
	if parentPath then
		local foundParent, findError = ToolHelpers.FindInstanceByPath(parentPath)
		if not foundParent then
			(instance :: Instance):Destroy() -- Cleanup
			return nil, "Failed to find specified parent at path '" .. parentPath .. "'. " .. (findError or "")
		end
		parent = foundParent
	end

    -- Name the instance (model)
	local baseName = toTitleCase((instance :: Instance).Name or query) -- Use model's name or query
	if string.len(baseName) == 0 then baseName = "Model" end

	local name = baseName
	local i = 1
	while parent:FindFirstChild(name) do
		i += 1
		name = baseName .. i
	end
	(instance :: Instance).Name = name
	(instance :: Instance).Parent = parent

	if (instance :: Instance):IsA("Model") then
		(instance :: Instance):PivotTo(CFrame.new(getInsertPosition()))
	elseif (instance :: Instance):IsA("BasePart") then
		(instance :: Instance).Position = getInsertPosition()
	end

    local resultData: Types.InsertModelResultData = {
        message = ("Successfully inserted asset ID %d as '%s' into '%s'."):format(assetId :: number, (instance :: Instance).Name, (instance :: Instance).Parent:GetFullName()),
        instance_path = (instance :: Instance):GetFullName(),
        asset_id = assetId,
    }
	return resultData, nil
end

local function handleInsertModel(args: Types.InsertModelArgs)
    local success, resultOrError = pcall(function()
        if type(args.query) ~= "string" or string.len(args.query) == 0 then

            return { __isError = true, message = "InsertModel: 'query' argument (asset ID or search term) is missing, empty, or not a string." }
        end
        if args.parent_path and type(args.parent_path) ~= "string" then
            return { __isError = true, message = "InsertModel: 'parent_path', if provided, must be a string." }

        end

        return performInsert(args.query, args.parent_path) -- This returns (data, errorString) or (nil, errorString)
    end)

    if success then
        if resultOrError and resultOrError.__isError then -- Check for our custom error table
            return ToolHelpers.FormatErrorResult(resultOrError.message)
        else
            -- This path means performInsert was called.
            -- resultOrError here is the direct return of performInsert,
            -- which is (data, errorString) or (nil, errorString)
            local data, errStr = resultOrError
            if errStr then
                return ToolHelpers.FormatErrorResult(errStr)
            else
                return ToolHelpers.FormatSuccessResult(data)
            end
        end
    else
        -- Error from the pcall itself
        return ToolHelpers.FormatErrorResult("Internal error in InsertModel: " .. tostring(resultOrError))
    end
end

return handleInsertModel
