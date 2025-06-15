-- GetSelection.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Selection = game:GetService("Selection")

return function(args)
	if not args["GetSelection"] then
		return ToolHelpers.FormatErrorResult("GetSelection: Invalid argument structure. Expected 'GetSelection' key.")
	end

	-- The GetSelection tool typically doesn't take additional parameters within args["GetSelection"],
	-- but if it did, they would be accessed here.
	-- local data = args["GetSelection"]

	local selectedObjects = Selection:Get()
	local results = {}

	for _, instance in ipairs(selectedObjects) do
		local objectData = {
			name = instance.Name,
			path = instance:GetFullName(),
			className = instance.ClassName,
			-- Potentially add more useful identifiers like a unique ID if available/needed
		}
		table.insert(results, objectData)
	end

	-- If no objects are selected, 'results' will be an empty table.
	-- FormatSuccessResult will correctly encode this as an empty JSON array.
	return ToolHelpers.FormatSuccessResult(results)
end
