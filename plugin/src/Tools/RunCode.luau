-- Simplified RunCode.luau
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers) -- Assuming ToolHelpers is still needed for FormatErrorResult/FormatSuccessResult

local function handleRunCode(args)
    if type(args.command) ~= "string" then
        return ToolHelpers.FormatErrorResult("Error: RunCode command argument is missing or not a string.")
    end

    local command = args.command
    local output_text = ""
    local is_error = false

    local success, result = pcall(function()
        local func, err = loadstring(command)
        if not func then
            return { message = "LOADSTRING ERROR: " .. tostring(err), is_error = true }
        end

        local results = {pcall(func)} -- Execute and capture results

        local run_success = results[1]
        local return_values = {}
        for i = 2, #results do
            table.insert(return_values, results[i])
        end

        if not run_success then
            return { message = "RUNTIME ERROR: " .. tostring(return_values[1]), is_error = true }
        else
            local output_parts = {}
            for i, val in ipairs(return_values) do
                table.insert(output_parts, tostring(val))
            end
            if #output_parts > 0 then
                 return { message = "Output: " .. table.concat(output_parts, "\t"), is_error = false }
            else
                return { message = "Command executed successfully with no return value.", is_error = false }
            end
        end
    end)

    if not success then
        -- This is an error in the pcall wrapping loadstring/execution itself
        output_text = "CRITICAL EXECUTION ERROR: " .. tostring(result)
        is_error = true
        return ToolHelpers.FormatErrorResult(output_text)
    elseif result.is_error then
        -- Error from loadstring or runtime
        return ToolHelpers.FormatErrorResult(result.message)
    else
        -- Success from execution
        return ToolHelpers.FormatSuccessResult({ output = result.message })
    end
end

return handleRunCode
