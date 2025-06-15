-- SelectInstances.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
local Selection = game:GetService("Selection")

local function execute(args)
    -- Arguments are expected directly on args table
    local success, pcall_result = pcall(function()
        local paths = args.paths

        if not paths or type(paths) ~= "table" then
            return ToolHelpers.FormatErrorResult("'paths' is required and must be an array of strings.")
        end

        local instancesToSelect = {}
        local findErrors = {}

        if #paths == 0 then
            -- Clear selection if an empty list of paths is provided
            local setEmptySuccess, setEmptyError = pcall(Selection.Set, Selection, {})
            if not setEmptySuccess then
                return ToolHelpers.FormatErrorResult("Failed to clear selection: " .. tostring(setEmptyError))
            end
            return ToolHelpers.FormatSuccessResult({
                message = "Selection cleared as an empty 'paths' array was provided.",
                selected_paths = {},
                selection_count = 0
            })
        end

        for _, pathString in ipairs(paths) do
            if type(pathString) == "string" then
                local instance, err = ToolHelpers.FindInstanceByPath(pathString)
                if instance then
                    table.insert(instancesToSelect, instance)
                else
                    table.insert(findErrors, {path = pathString, error = err or "Not found"})
                    -- Minimal logging, error details are in the response
                    print(("SelectInstances: Could not find instance for selection at path: %s. Error: %s"):format(pathString, err or "Not found"))
                end
            else
                table.insert(findErrors, {path = tostring(pathString), error = "Path entry is not a string."})
            end
        end

        -- Only attempt to set selection if there are valid instances to select,
        -- otherwise, if all paths failed, it's effectively an error or a partial success with only errors.
        if #instancesToSelect > 0 then
            local setSuccess, setError = pcall(Selection.Set, Selection, instancesToSelect)
            if not setSuccess then
                 -- This is a more critical error if setting the selection itself fails.
                 return ToolHelpers.FormatErrorResult("Failed to set selection with found instances: " .. tostring(setError))
            end
        elseif #findErrors > 0 and #instancesToSelect == 0 then
             -- All paths resulted in errors, no valid instances found to select.
            return ToolHelpers.FormatErrorResult("No valid instances found from provided paths to select.", {errors = findErrors})
        end


        local currentSelection = Selection:Get()
        local currentSelectionPaths = {}
        for _, selectedInstance in ipairs(currentSelection) do
            table.insert(currentSelectionPaths, selectedInstance:GetFullName())
        end

        local message
        if #findErrors > 0 then
            message = ("Partially set selection. %d instance(s) selected. %d path(s) resulted in errors."):format(#currentSelectionPaths, #findErrors)
        elseif #instancesToSelect == 0 and #paths > 0 then -- Paths provided, but none resolved and no errors (should be caught above)
            message = "No instances were selected. Provided paths might have been valid but resolved to no selectable instances or were empty."
        else
            message = ("Successfully selected %d instance(s)."):format(#currentSelectionPaths)
        end

        local resultData = {
            message = message,
            selected_paths = currentSelectionPaths,
            selection_count = #currentSelectionPaths
        }
        if #findErrors > 0 then
            resultData.errors_finding_paths = findErrors
        end

        return ToolHelpers.FormatSuccessResult(resultData)
    end)

    if success then
        return pcall_result
    else
        return ToolHelpers.FormatErrorResult("Internal error in SelectInstances: " .. tostring(pcall_result))
    end
end

return execute
