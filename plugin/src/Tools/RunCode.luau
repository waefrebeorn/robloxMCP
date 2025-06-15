
-- Simplified RunCode.luau - Step 1 of reintroducing functionality
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)


local function handleRunCode(args)
    if type(args.command) ~= "string" then
        return ToolHelpers.FormatErrorResult("Error: RunCode command argument is missing or not a string.")

    end

    local command = args.command
    local output_parts = {} -- Reintroduce output_parts
    local an_error_occurred_in_command = false

    -- Simplified addToOutput for this step
    local function addToOutput(tag, ...)
        local parts = {tag}
        for i = 1, select("#", ...) do
            table.insert(parts, tostring(select(i, ...)))
        end
        table.insert(output_parts, table.concat(parts, " ") .. "\n")
    end

    local pcall_success, execution_result = pcall(function()
        local func, load_err = loadstring(command)
        if not func then
            an_error_occurred_in_command = true
            addToOutput("[LOADSTRING ERROR]", load_err or "Unknown loadstring error")
            return -- Important: return from this anonymous function
        end

        local chunkfenv = getfenv(func)
        local oldPrint = chunkfenv.print or print
        chunkfenv.print = function(...)
            if oldPrint then oldPrint(...) end -- Call original print
            addToOutput("[OUTPUT]", ...)
        end

        local oldWarn = chunkfenv.warn or warn
        chunkfenv.warn = function(...)
            if oldWarn then oldWarn(...) end -- Call original warn
            addToOutput("[WARNING]", ...)
        end

        -- Capture errors without halting, record them via addToOutput
        local oldError = chunkfenv.error
        chunkfenv.error = function(...)
            an_error_occurred_in_command = true
            addToOutput("[ERROR]", ...)
            -- Do not call oldError here to prevent script halt if possible,
            -- error is recorded. For critical errors, pcall below handles it.
        end

        -- Execute the user's code
        local results = {pcall(func)}
        local run_success = results[1]
        local returned_values_from_command = {}
        for i = 2, #results do
            table.insert(returned_values_from_command, results[i])
        end

        if not run_success then
            an_error_occurred_in_command = true
            -- The error from pcall(func) is in returned_values_from_command[1]
            addToOutput("[RUNTIME ERROR]", returned_values_from_command[1])
        else
            if #returned_values_from_command > 0 then
                addToOutput("[RETURNED]", table.unpack(returned_values_from_command))
            end
        end
    end) -- End of main pcall for execution

    local final_output_str = table.concat(output_parts, "")

    if not pcall_success then
        -- This is a critical error in the Lua code of this tool itself (e.g. in addToOutput, etc.)
        -- This should ideally not happen with this simplified version.
        final_output_str = final_output_str .. "[CRITICAL TOOL ERROR] " .. tostring(execution_result) .. "\n"
        an_error_occurred_in_command = true -- Mark as error
        return ToolHelpers.FormatErrorResult(final_output_str)
    elseif an_error_occurred_in_command then
        return ToolHelpers.FormatErrorResult(final_output_str)
    else
        if final_output_str == "" then
            final_output_str = "Command executed successfully with no output or return values."
        end
        return ToolHelpers.FormatSuccessResult({ output = final_output_str })

    end
end

return handleRunCode
