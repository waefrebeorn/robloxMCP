@echo OFF
SETLOCAL ENABLEDELAYEDEXPANSION

:: ============================================================================
:: Batch File: setup_phi4_fc_model.bat
:: Version: 2.4 (Production Ready)
:: Description: Creates a custom Ollama model for phi4-mini with a specific
::              template for reliable function calling (functools format).
:: ============================================================================

:: --- Configuration ---
SET "MODFILE_NAME=phi4_fc_ollama.Modelfile"
SET "CUSTOM_MODEL_NAME=phi4-mini-functools"
SET "BASE_MODEL_NAME=phi4-mini:latest"
SET "SCRIPT_NAME=%~nx0"
SET "ERROR_FLAG=0"

:: Define a single quote and triple quote reliably
SET "Q="" 
SET "TQ=!Q!!Q!!Q!"

echo [!SCRIPT_NAME!] SCRIPT START
echo [!SCRIPT_NAME!] Using custom model name: !CUSTOM_MODEL_NAME!, base model: !BASE_MODEL_NAME!
echo.

:: --- Clean up old Modelfile ---
IF EXIST "!MODFILE_NAME!" (
    echo [!SCRIPT_NAME!] Deleting existing Modelfile: !MODFILE_NAME!
    DEL /F /Q "!MODFILE_NAME!"
    IF ERRORLEVEL 1 (
        echo [!SCRIPT_NAME!] ERROR: Could not delete old Modelfile "!MODFILE_NAME!". Permissions?
        SET "ERROR_FLAG=1"
        GOTO :EndScript
    ) ELSE (
        echo [!SCRIPT_NAME!] Old Modelfile deleted.
    )
)
echo.

:: --- Define Modelfile Content as Variables ---
SET "MF_LINE_01=FROM !BASE_MODEL_NAME!"
SET "MF_LINE_02=# Note: If your base model is named differently (e.g., after a specific download),"
SET "MF_LINE_03=# change '!BASE_MODEL_NAME!' above to match the name you see in 'ollama list'."
SET "MF_LINE_04="
SET "MF_LINE_05=# Template for phi4-mini to encourage functools format"
SET "MF_LINE_06=TEMPLATE !TQ!"
SET "MF_LINE_07=^<\|user\|^\>"
SET "MF_LINE_08={{ .Prompt }}^<\|end\|^\>"
SET "MF_LINE_09=^<\|assistant\|^\>"
SET "MF_LINE_10={{if .ToolCalls }}functools[{{ range $idx, $tool := .ToolCalls }}"
SET "MF_LINE_11= { "
SET "MF_LINE_12=  "name": "{{$tool.Function.Name}}","
SET "MF_LINE_13=  "arguments": {{$tool.Function.Arguments}}"
SET "MF_LINE_14= }{{end}}"
SET "MF_LINE_15=]{{else}}{{ .Response }}{{end}}^<\|end\|^\>"
SET "MF_LINE_16=!TQ!"
SET "MF_LINE_17="
SET "MF_LINE_18=SYSTEM !TQ!"
SET "MF_LINE_19=You are a helpful AI assistant."
SET "MF_LINE_20=You have access to the following tools:"
SET "MF_LINE_21=REMEMBER: THIS IS A PLACEHOLDER. REPLACE WITH ACTUAL TOOL DEFINITIONS."
SET "MF_LINE_22=^<tool_name^\>"
SET "MF_LINE_23=mcp_tool_listing"
SET "MF_LINE_24=^</tool_name^\>"
SET "MF_LINE_25="
SET "MF_LINE_26=^<tool_description^\>"
SET "MF_LINE_27=Lists all available MCP tools."
SET "MF_LINE_28=^</tool_description^\>"
SET "MF_LINE_29="
SET "MF_LINE_30=^<tool_parameters^\>"
SET "MF_LINE_31={}"
SET "MF_LINE_32=^</tool_parameters^\>"
SET "MF_LINE_33="
SET "MF_LINE_34={{ range .Tools }}"
SET "MF_LINE_35=^<tool_name^\>"
SET "MF_LINE_36={{ .Name }}"
SET "MF_LINE_37=^</tool_name^\>"
SET "MF_LINE_38=^<tool_description^\>"
SET "MF_LINE_39={{ .Description }}"
SET "MF_LINE_40=^</tool_description^\>"
SET "MF_LINE_41=^<tool_parameters^\>"
SET "MF_LINE_42={{ .Parameters }}"
SET "MF_LINE_43=^</tool_parameters^\>"
SET "MF_LINE_44={{ end }}"
SET "MF_LINE_45=When you need to use a tool, respond with a JSON object in the following format inside `functools[...]`:"
SET "MF_LINE_46=`functools[{"name": "^<tool_name^>", "arguments": {"^<param_name^>": "^<param_value^>"}}]`"
SET "MF_LINE_47=If you need to use multiple tools, include them in the list:"
SET "MF_LINE_48=`functools[{"name": "^<tool_name_1^>", "arguments": {...}}, {"name": "^<tool_name_2^>", "arguments": {...}}]`"
SET "MF_LINE_49=Only respond with the `functools[...]` structure if a tool is being called. Do not add any other text before or after it."
SET "MF_LINE_50=If no tool is needed, respond with a regular text message."
SET "MF_LINE_51=!TQ!"
SET "MF_LINE_52="
SET "MF_LINE_53=# Recommended Parameters (adjust as needed)"
SET "MF_LINE_54=PARAMETER stop ^<\|end\|^\>"
SET "MF_LINE_55=PARAMETER stop ^<\|user\|^\>"
SET "MF_LINE_56=PARAMETER stop ^<\|assistant\|^\>"
SET "MF_LINE_57=PARAMETER stop functools["
echo [!SCRIPT_NAME!] Modelfile content defined.
echo.

:: --- Write Modelfile from Variables ---
echo [!SCRIPT_NAME!] Writing Modelfile "!MODFILE_NAME!"...
(
    echo(!MF_LINE_01!
    echo(!MF_LINE_02!
    echo(!MF_LINE_03!
    echo(!MF_LINE_04!
    echo(!MF_LINE_05!
    echo(!MF_LINE_06!
    echo(!MF_LINE_07!
    echo(!MF_LINE_08!
    echo(!MF_LINE_09!
    echo(!MF_LINE_10!
    echo(!MF_LINE_11!
    echo(!MF_LINE_12!
    echo(!MF_LINE_13!
    echo(!MF_LINE_14!
    echo(!MF_LINE_15!
    echo(!MF_LINE_16!
    echo(!MF_LINE_17!
    echo(!MF_LINE_18!
    echo(!MF_LINE_19!
    echo(!MF_LINE_20!
    echo(!MF_LINE_21!
    echo(!MF_LINE_22!
    echo(!MF_LINE_23!
    echo(!MF_LINE_24!
    echo(!MF_LINE_25!
    echo(!MF_LINE_26!
    echo(!MF_LINE_27!
    echo(!MF_LINE_28!
    echo(!MF_LINE_29!
    echo(!MF_LINE_30!
    echo(!MF_LINE_31!
    echo(!MF_LINE_32!
    echo(!MF_LINE_33!
    echo(!MF_LINE_34!
    echo(!MF_LINE_35!
    echo(!MF_LINE_36!
    echo(!MF_LINE_37!
    echo(!MF_LINE_38!
    echo(!MF_LINE_39!
    echo(!MF_LINE_40!
    echo(!MF_LINE_41!
    echo(!MF_LINE_42!
    echo(!MF_LINE_43!
    echo(!MF_LINE_44!
    echo(!MF_LINE_45!
    echo(!MF_LINE_46!
    echo(!MF_LINE_47!
    echo(!MF_LINE_48!
    echo(!MF_LINE_49!
    echo(!MF_LINE_50!
    echo(!MF_LINE_51!
    echo(!MF_LINE_52!
    echo(!MF_LINE_53!
    echo(!MF_LINE_54!
    echo(!MF_LINE_55!
    echo(!MF_LINE_56!
    echo(!MF_LINE_57!
) > "!MODFILE_NAME!"

IF !ERRORLEVEL! NEQ 0 (
    echo [!SCRIPT_NAME!] CRITICAL ERROR: Failed to write Modelfile "%MODFILE_NAME%".
    SET "ERROR_FLAG=1"
    GOTO :EndScript
)
echo [!SCRIPT_NAME!] Modelfile "%MODFILE_NAME%" written successfully.
echo.

:: --- Run ollama create ---
echo [!SCRIPT_NAME!] Attempting to create Ollama model "!CUSTOM_MODEL_NAME!"...
ollama create "!CUSTOM_MODEL_NAME!" -f "!MODFILE_NAME!"
SET "OLLAMA_CREATE_ERRORLEVEL=!ERRORLEVEL!"
echo [!SCRIPT_NAME!] 'ollama create' command finished with ERRORLEVEL: !OLLAMA_CREATE_ERRORLEVEL!

SET "TEST_VAR=Value" & REM This simple command seems to prevent a cmd.exe parsing error after ollama create. Do not remove.

IF "!OLLAMA_CREATE_ERRORLEVEL!" NEQ "0" (
    echo.
    echo [!SCRIPT_NAME!] ERROR: 'ollama create' command failed with error code !OLLAMA_CREATE_ERRORLEVEL!.
    echo [!SCRIPT_NAME!] Please check Ollama output above and its server logs for more details.
    SET "ERROR_FLAG=1"
    GOTO :EndScript
)

echo.
echo [!SCRIPT_NAME!] Successfully created Ollama model: "!CUSTOM_MODEL_NAME!"
echo.
echo   --- Next Steps ---
echo   1. If using with an agent, update its configuration to use: "!CUSTOM_MODEL_NAME!"
echo   2. Relaunch your agent.
echo   The Modelfile ("!MODFILE_NAME!") is in the current directory for reference.
echo.

GOTO :EndScript

:EndScript
IF "!ERROR_FLAG!" EQU "1" (
    echo [!SCRIPT_NAME!] SCRIPT FINISHED WITH ERRORS.
) ELSE (
    echo [!SCRIPT_NAME!] SCRIPT FINISHED SUCCESSFULLY.
)
ENDLOCAL
echo.
echo Press any key to continue . . .
pause
EXIT /B %ERROR_FLAG%