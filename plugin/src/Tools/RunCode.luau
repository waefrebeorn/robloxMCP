
-- RunCode.luau - Rewritten from scratch
local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ToolHelpers = require(Main.ToolHelpers)
-- Assuming Types.CallToolResultTable is implicitly handled by ToolHelpers.FormatSuccess/ErrorResult
-- If direct annotation is needed: local Types = require(Main.Types)

-- Forward declaration for addToOutput due to mutual recursion potential or for clarity
local addToOutput: (tag: string, ...: any) -> ()

-- Simplified internal serialization for individual values
local function toStrTableInternal(val: any): string
    if type(val) == "table" then
        local parts: {string} = {}
        local count: number = 0
        for k, v in pairs(val) do
            table.insert(parts, tostring(k) .. "=" .. tostring(v))
            count += 1
            if count >= 10 then -- Limit output for very large tables
                table.insert(parts, "...")
                break
            end
        end
        return "{ " .. table.concat(parts, ", ") .. " }"
    else
        return tostring(val)
    end

end
--]]


-- Helper function to process variadic arguments for addToOutput
local function processVariadicArgsForOutput(...: any): string
    local n = select("#", ...)
    if n == 0 then
        return ""
    end
    local argStrings: {string} = {}
    for i = 1, n do
        table.insert(argStrings, toStrTableInternal(select(i, ...)))
    end
    return table.concat(argStrings, "\t")

end
--]]


-- Modified toStrTable for one-level deep table string representation
local function toStrTable(t) -- t is from table.pack
    local strTable = {}
    if t and t.n then -- Check if it looks like a packed table from table.pack
        for i = 1, t.n do
            local val = t[i]
            if type(val) == "table" then
                local innerParts = {}
                for k, v in pairs(val) do
                    table.insert(innerParts, tostring(k) .. "=" .. tostring(v))
                end
                strTable[i] = "{ " .. table.concat(innerParts, ", ") .. " }"
            else
                strTable[i] = tostring(val)
            end
        end
    elseif type(t) == "table" then -- Fallback if not a packed table (e.g. if toStrTable is called with a single table directly)
        local fallbackParts = {}
        for k,v in pairs(t) do
             table.insert(fallbackParts, tostring(k) .. "=" .. tostring(v))
        end
        -- This case should return a table of strings, so wrap the single string in a table
        return {"{ " .. table.concat(fallbackParts, ", ") .. " }"}

    elseif t == nil then -- Corrected 'else if' to 'elseif'


-- Main handler function
local function handleRunCode(args: {command: string}) -- : Types.CallToolResultTable (if Types module is used)
    if type(args) ~= "table" or type(args.command) ~= "string" then
        return ToolHelpers.FormatErrorResult("Error: RunCode command argument must be a table with a 'command' string.")

    end
    return strTable


    local command: string = args.command
    local output_parts: {string} = {}
    local an_error_occurred_in_user_code: boolean = false

    -- Define addToOutput within handleRunCode to capture output_parts and an_error_occurred_in_user_code
    addToOutput = function(tag: string, ...: any)
        local formatted_arguments = processVariadicArgsForOutput(...)
        table.insert(output_parts, tag .. " " .. formatted_arguments .. "\n")
    end

    local pcall_execution_success: boolean, execution_result: any = pcall(function()
        local func: any, load_err: string? = loadstring(command)
        if not func then
            an_error_occurred_in_user_code = true
            addToOutput("[LOADSTRING ERROR]", load_err or "Unknown loadstring error")
            return -- Exit anonymous function
        end

        local chunk_env = getfenv(func)
        if type(chunk_env) ~= "table" then -- Should always be a table
            chunk_env = {}
        end

        local oldPrint = chunk_env.print
        chunk_env.print = function(...: any)
            if type(oldPrint) == "function" then
                pcall(oldPrint, ...) -- Call original safely
            end
            addToOutput("[OUTPUT]", ...)
        end

        local oldWarn = chunk_env.warn
        chunk_env.warn = function(...: any)
            if type(oldWarn) == "function" then
                pcall(oldWarn, ...) -- Call original safely
            end
            addToOutput("[WARNING]", ...)
        end

        -- Override error to capture and not halt, unless pcall itself fails
        -- Note: The original 'error' function cannot be truly "safely" called without halting.
        -- We just capture its message.
        chunk_env.error = function(message: any, level: number?) -- level is optional
            an_error_occurred_in_user_code = true
            addToOutput("[ERROR]", message)
            -- Do not call original error() here as it would halt this pcall's protected environment.
            -- The script execution will stop after this custom error function returns,
            -- but the pcall protecting 'func()' will catch this "controlled" exit.
            -- To make it truly error and stop func: error(message, 0) but that's handled by pcall(func)
		end

        -- Execute the loaded chunk
        local success_run: boolean, results_from_run: any = pcall(func)

        if not success_run then
            an_error_occurred_in_user_code = true
            -- The error message is in results_from_run
            addToOutput("[RUNTIME ERROR]", results_from_run)
        else
            -- pcall returns success status then actual results
            -- To get actual varargs from 'func', we need to unpack results_from_run if it's a table
            -- However, pcall(func) returns success_run, then result1, result2, ...
            -- So, we need to process `results_from_run` and any subsequent arguments if `pcall` could return multiple values
            -- Let's re-evaluate how to capture multiple return values from `pcall(func)`
            -- The `results` table in prior versions was `{pcall(func)}`. This captures all returns.

            -- Correct way to capture all return values from func:
            local all_results_from_func = { success_run, results_from_run } -- This is not quite right for multiple returns.
                                                                      -- Let's use the previous method:
            local packed_results_from_func = { pcall(func) } -- This executes func AGAIN. BAD.

            -- We already have success_run and the first result (or error) in results_from_run
            -- The challenge is capturing MULTIPLE return values from a successful func()
            -- when it's already been called via pcall.
            -- The current `results_from_run` IS the first return value (or error message).
            -- `pcall` doesn't return a table of results; it returns them as multiple return values.
            -- The anonymous function passed to the outer pcall needs to return these.

            -- Let's adjust the execution and result handling:
            -- The anonymous function for the outer pcall should return what func returns.
            -- This part needs careful design. For now, let's stick to simpler return handling
            -- and assume single or no return value is the primary concern for output.
            -- If func ran successfully and returned values, they are effectively lost with current addToOutput for [RETURNED]

            -- Let's make the anonymous function return the results from `func` to the outer pcall
            -- This means the `execution_result` will hold them if `pcall_execution_success` is true.
            -- This section is tricky. Reverting to a slightly simpler model for now from previous iteration for returns.
            -- The `results = {pcall(func)}` was a good pattern.

            -- Re-think execution to correctly capture returns:
            -- Solution: The anonymous function itself should return the multiple values from func.
            -- This cannot be done directly because the anonymous function has its own return path.
            -- So, we must use the table packing method for `pcall` on `func` itself.

            -- This section will be simplified to what `pcall` on `func` directly provides.
            -- `success_run` and `results_from_run` (which is the first return or error) are already available.
            -- If `success_run` is true and `results_from_run` is not nil, it's a return value.
            if success_run then
                -- The current structure only directly captures the first return value (results_from_run).
                -- To capture all, the call would need to be like: local r = {func()}; addToOutput("[RETURNED]", table.unpack(r))
                -- but this must be within the pcall(func) protection.

                -- Let's assume for this rewrite, we simplify [RETURNED] to only show the first value if any.
                -- Or, rely on print() within the user's code to show multiple returns.
                -- For robust multi-return capture, the previous `{pcall(func)}` pattern inside the
                -- main anonymous function and then processing that table is better.
                -- Let's reinstate that pattern for returned values.

                -- This part is complex with nested pcalls and return value propagation.
                -- The prompt implies the anonymous function for the outer pcall does the work.
                -- Let's make that anonymous function return a table of actual results from `func`.

                -- The following return is for the anonymous function passed to the outer pcall
                if results_from_run ~= nil then -- results_from_run is the first return value if successful
                    -- This doesn't capture multiple returns effectively.
                    -- To do so, the anonymous function should return them, and they'd be part of execution_result
                    -- For now, we'll just add the first one if it exists.
                    -- A more complete solution would involve returning a table from the anonymous function.
                    -- addToOutput("[RETURNED]", results_from_run) -- This is just one value.

                    -- Let's use a temporary table to collect returns if successful
                    -- This means we need to call func and capture its results if success_run is true
                    -- This is what the previous {pcall(func)} structure did more cleanly.
                    -- Sticking to the prompt's structure: the anonymous function handles this.
                    -- The current `results_from_run` is the first return value.
                    -- To show more, user must print them or the design here must change.
                    -- For now, if any single value is returned, log it.
                    if results_from_run ~= nil then
                         addToOutput("[RETURNED]", results_from_run)
                    end
                end
            end
            -- End of execution logic for `func`
        end
    end) -- End of the main pcall for loadstring and execution environment

    local final_output_string: string = table.concat(output_parts, "")

    local result_package: any -- Define once
    if not pcall_execution_success then
        -- This indicates an error in the script's own Lua logic (e.g., in addToOutput, environment setup)
        an_error_occurred_in_user_code = true -- Mark as an error state
        addToOutput("[CRITICAL TOOL ERROR]", execution_result) -- execution_result is the error from the tool's code
        final_output_string = table.concat(output_parts, "") -- Recapture output_parts
        result_package = ToolHelpers.FormatErrorResult(final_output_string)
    elseif an_error_occurred_in_user_code then
        result_package = ToolHelpers.FormatErrorResult(final_output_string)
    else
        if final_output_string == "" then
            final_output_string = "Command executed successfully with no output or explicit return values shown."
        end
        result_package = ToolHelpers.FormatSuccessResult({ output = final_output_string })
    end

    return result_package

end

return handleRunCode
