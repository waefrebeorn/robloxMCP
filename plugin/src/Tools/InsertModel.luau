local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)
local ToolHelpers = require(Main.ToolHelpers)

local INSERT_MAX_SEARCH_DEPTH = 2048
local INSERT_MAX_DISTANCE_AWAY = 20

local function getInsertPosition()
	local camera = workspace.CurrentCamera
	if not camera then return Vector3.new(0, 5, 0) end -- Fallback if no camera

	local viewportPoint = camera.ViewportSize / 2
	local unitRay = camera:ViewportPointToRay(viewportPoint.X, viewportPoint.Y, 0)

	local ray = Ray.new(unitRay.Origin, unitRay.Direction * INSERT_MAX_SEARCH_DEPTH)
	local params = RaycastParams.new()
	-- params.BruteForceAllSlow = true -- This is deprecated
	params.FilterType = Enum.RaycastFilterType.Exclude -- Example: Exclude selection
	params.FilterDescendantsInstances = game:GetService("Selection"):Get()


	local result = workspace:Raycast(ray.Origin, ray.Direction, params)

	if result then
		return result.Position
	else
		return camera.CFrame.Position + unitRay.Direction * INSERT_MAX_DISTANCE_AWAY
	end
end

local InsertService = game:GetService("InsertService")

type GetFreeModelsResponse = {
	[number]: {
		CurrentStartIndex: number,
		TotalCount: number,
		Results: {
			[number]: {
				Name: string,
				AssetId: number,
				AssetVersionId: number,
				CreatorName: string,
			},
		},
	},
}

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

local function loadAsset(assetId: number): (boolean, Instance | string)
	local success, objects = pcall(game.GetObjects, game, "rbxassetid://" .. assetId)
	if not success or not objects then
		return false, "Failed to call GetObjects or no objects returned for asset ID: " .. tostring(assetId)
	end

	local container = collapseObjectsIntoContainer(objects)
	if not container then
		return false, "Failed to collapse objects into container for asset ID: " .. tostring(assetId)
	end
	return true, container
end

local function getAssets(query: string): (boolean, number? | string)
	local success, results = pcall(InsertService.GetFreeModels, InsertService, query, 0)
	if not success or not results then
		return false, "InsertService:GetFreeModels failed for query: " .. query .. ". Error: " .. tostring(results)
	end

	if results[1] and results[1].Results and #results[1].Results > 0 then
		return true, results[1].Results[1].AssetId -- Return the first asset ID
	else
		return false, "No assets found for query: " .. query
	end
end

-- Modified to return a table indicating success/failure and data/error message
local function insertFromMarketplace(query: string): { success: boolean, data: { name: string, fullName: string }?, error: string? }
	local assetOk, assetIdOrError = getAssets(query)
	if not assetOk then
		return { success = false, error = assetIdOrError }
	end
	local assetId = assetIdOrError :: number

	local loadOk, instanceOrError = loadAsset(assetId)
	if not loadOk then
		return { success = false, error = instanceOrError }
	end
	local instance = instanceOrError :: Instance

	local baseName = toTitleCase(query)
	if string.len(baseName) == 0 then baseName = "Model" end -- Fallback name

	local name = baseName
	local i = 1
	while workspace:FindFirstChild(name) do
		name = baseName .. i
		i += 1
	end

	instance.Name = name
	instance.Parent = workspace

	if instance:IsA("Model") then
		instance:PivotTo(CFrame.new(getInsertPosition()))
	elseif instance:IsA("BasePart") then -- Handle single parts too
		instance.Position = getInsertPosition()
	end

	return { success = true, data = { name = instance.Name, fullName = instance:GetFullName() } }
end

local function handleInsertModel(args: Types.ToolArgs): Types.CallToolResultTable
	if not args["InsertModel"] then
		return ToolHelpers.FormatErrorResult("InsertModel: Invalid argument structure. Expected 'InsertModel' key.")
	end

	local insertModelArgs: Types.InsertModelArgs = args["InsertModel"]
	if type(insertModelArgs.query) ~= "string" or string.len(insertModelArgs.query) == 0 then
		return ToolHelpers.FormatErrorResult("InsertModel: 'query' argument is missing, empty, or not a string.")
	end

	local result = insertFromMarketplace(insertModelArgs.query)

	if result.success then
		local successData = {
			message = "Successfully inserted model: " .. result.data.name,
			model_name = result.data.name,
			model_path = result.data.fullName,
		}
		return ToolHelpers.FormatSuccessResult(successData)
	else
		return ToolHelpers.FormatErrorResult(result.error or "InsertModel: An unknown error occurred during insertion.")
	end
end

return handleInsertModel :: Types.ToolFunction
