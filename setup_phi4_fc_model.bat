@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

:: ============================================================================
:: Batch File: setup_phi4_fc_model.bat
:: Version: 1.0
:: Description: Creates a custom Ollama model for phi4-mini with a specific
::              template for reliable function calling (functools format).
:: Design Doc: Batch File Design Document v1.0 (inferred)
:: ============================================================================

:: --- Configuration ---
SET "MODFILE_NAME=phi4_fc_ollama.Modelfile"
SET "CUSTOM_MODEL_NAME=phi4-mini-functools"
SET "BASE_MODEL_NAME=phi4-mini:latest"
SET "SCRIPT_NAME=setup_phi4_fc_model.bat"

echo [!SCRIPT_NAME!] Starting setup for custom Ollama model: !CUSTOM_MODEL_NAME!
echo [!SCRIPT_NAME!] Using Modelfile name: !MODFILE_NAME!
echo [!SCRIPT_NAME!] Base model for FROM line: !BASE_MODEL_NAME!
echo.

:: --- Prepare Modelfile Content ---
echo [!SCRIPT_NAME!] Preparing Modelfile content...

(
    echo FROM !BASE_MODEL_NAME!
    echo # Note: If your base model is named differently (e.g., after a specific download),
    echo # change '!BASE_MODEL_NAME!' above to match the name you see in 'ollama list'.
    echo.
    echo # Template for phi4-mini to encourage functools format
    echo TEMPLATE ^"""^<\|user\|^\>
    echo {{ .Prompt }}^<\|end\|^\>
    echo ^<\|assistant\|^\>
    echo {{if .ToolCalls }}functools[{{ range $idx, $tool := .ToolCalls }}
    echo  {
    echo   "name": "{{$tool.Function.Name}}",
    echo   "arguments": {{$tool.Function.Arguments}}
    echo  }{{end}}
    echo ]{{else}}{{ .Response }}{{end}}^<\|end\|^\>
    echo ^"""
    echo.
    echo SYSTEM ^"""You are a helpful AI assistant.
    echo You have access to the following tools:
    echo {{ range .Tools }}
    echo ^<tool_name^\>
    echo {{ .Name }}
    echo ^</tool_name^\>
    echo ^<tool_description^\>
    echo {{ .Description }}
    echo ^</tool_description^\>
    echo ^<tool_parameters^\>
    echo {{ .Parameters }}
    echo ^</tool_parameters^\>
    echo {{ end }}
    echo When you need to use a tool, respond with a JSON object in the following format inside `functools[...]`:
    echo `functools[{"name": "^<tool_name^>", "arguments": {"^<param_name^>": "^<param_value^>"}}]`
    echo If you need to use multiple tools, include them in the list:
    echo `functools[{"name": "^<tool_name_1^>", "arguments": {...}}, {"name": "^<tool_name_2^>", "arguments": {...}}]`
    echo Only respond with the `functools[...]` structure if a tool is being called. Do not add any other text before or after it.
    echo If no tool is needed, respond with a regular text message.
    echo ^"""
    echo.
    echo # Recommended Parameters (adjust as needed)
    echo PARAMETER stop "^<\|end\|^\>"
    echo PARAMETER stop "^<\|user\|^\>"
    echo PARAMETER stop "^<\|assistant\|^\>"
    echo PARAMETER stop "functools["
) > "!MODFILE_NAME!"

IF !ERRORLEVEL! NEQ 0 (
    echo [!SCRIPT_NAME!] ERROR: Failed to write Modelfile "%MODFILE_NAME%".
    GOTO :EndScript
)

echo [!SCRIPT_NAME!] Modelfile "%MODFILE_NAME%" created successfully.
echo.

:: --- Run ollama create ---
echo [!SCRIPT_NAME!] Attempting to create Ollama model "!CUSTOM_MODEL_NAME!"...
echo [!SCRIPT_NAME!] This command may take a few moments if the base model needs to be downloaded.
echo [!SCRIPT_NAME!] Executing: ollama create "!CUSTOM_MODEL_NAME!" -f "!MODFILE_NAME!"
ollama create "!CUSTOM_MODEL_NAME!" -f "!MODFILE_NAME!"

IF !ERRORLEVEL! NEQ 0 (
    echo.
    echo [!SCRIPT_NAME!] ERROR: 'ollama create' command failed with error code !ERRORLEVEL!.
    echo [!SCRIPT_NAME!] Please check the output above for error messages from Ollama.
    echo [!SCRIPT_NAME!] Ensure Ollama service is running and the base model '!BASE_MODEL_NAME!' is available.
    echo [!SCRIPT_NAME!] You can verify by running 'ollama list' in a separate terminal.
    echo [!SCRIPT_NAME!] Also, check Ollama server logs for more detailed information.
    GOTO :EndScript
)

echo.
echo [!SCRIPT_NAME!] Successfully created Ollama model: "!CUSTOM_MODEL_NAME!"
echo.
echo   --- Next Steps ---
echo   1. If you are using this with an agent (like the Roblox Studio AI Broker),
echo      update its configuration to use the model name: "!CUSTOM_MODEL_NAME!"
echo      (e.g., via command-line argument '--ollama_model !CUSTOM_MODEL_NAME!' or in a config file).
echo   2. Relaunch your agent.
echo.
echo [!SCRIPT_NAME!] The Modelfile ("!MODFILE_NAME!") has been created in the current directory.
echo [!SCRIPT_NAME!] You can keep it for reference or delete it if no longer needed.
echo.

:EndScript
echo [!SCRIPT_NAME!] Script finished.
ENDLOCAL
REM Adding a pause here so the user can see the output before the window closes if run by double-click
pause
