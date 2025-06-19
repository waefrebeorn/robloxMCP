@echo off
setlocal

:: Script to automate the creation of a custom Ollama model for phi4-mini
:: configured for reliable function calling.

:: --- Configuration ---
set MODFILE_NAME=phi4_fc_ollama.Modelfile
set CUSTOM_MODEL_NAME=phi4-mini-functools
set BASE_MODEL_NAME=phi4-mini:latest

echo Creating Modelfile: %MODFILE_NAME%
echo.

:: --- Create the Modelfile ---
:: Overwrite if exists, then append
echo FROM %BASE_MODEL_NAME% > %MODFILE_NAME%
echo # Note: If your base model is named differently (e.g., after a specific download),^ >> %MODFILE_NAME%
echo # change '%BASE_MODEL_NAME%' above to match the name you see in 'ollama list'.^ >> %MODFILE_NAME%
echo. >> %MODFILE_NAME%
echo # Template for phi4-mini to encourage functools format^ >> %MODFILE_NAME%
echo TEMPLATE ^"""^<\|user\|^\> >> %MODFILE_NAME%
echo {{ .Prompt }}^<\|end\|^\> >> %MODFILE_NAME%
echo ^<\|assistant\|^\> >> %MODFILE_NAME%
echo {{if .ToolCalls }}functools[{{ range $idx, $tool := .ToolCalls }}^ >> %MODFILE_NAME%
echo  {^ >> %MODFILE_NAME%
echo   "name": "{{$tool.Function.Name}}",^ >> %MODFILE_NAME%
echo   "arguments": {{$tool.Function.Arguments}}^ >> %MODFILE_NAME%
echo  }{{end}}^ >> %MODFILE_NAME%
echo ]{{else}}{{ .Response }}{{end}}^<\|end\|^\>^ >> %MODFILE_NAME%
echo """ >> %MODFILE_NAME%
echo. >> %MODFILE_NAME%
echo SYSTEM ^"""You are a helpful AI assistant.^ >> %MODFILE_NAME%
echo You have access to the following tools:^ >> %MODFILE_NAME%
echo {{ range .Tools }}^ >> %MODFILE_NAME%
echo ^<tool_name^\>^ >> %MODFILE_NAME%
echo {{ .Name }}^ >> %MODFILE_NAME%
echo ^</tool_name^\>^ >> %MODFILE_NAME%
echo ^<tool_description^\>^ >> %MODFILE_NAME%
echo {{ .Description }}^ >> %MODFILE_NAME%
echo ^</tool_description^\>^ >> %MODFILE_NAME%
echo ^<tool_parameters^\>^ >> %MODFILE_NAME%
echo {{ .Parameters }}^ >> %MODFILE_NAME%
echo ^</tool_parameters^\>^ >> %MODFILE_NAME%
echo {{ end }}^ >> %MODFILE_NAME%
echo When you need to use a tool, respond with a JSON object in the following format inside `functools[...]`:`^ >> %MODFILE_NAME%
echo `functools[{"name": "^<tool_name^>", "arguments": {"^<param_name^>": "^<param_value^>"}}]`^ >> %MODFILE_NAME%
echo If you need to use multiple tools, include them in the list:^ >> %MODFILE_NAME%
echo `functools[{"name": "^<tool_name_1^>", "arguments": {...}}, {"name": "^<tool_name_2^>", "arguments": {...}}]`^ >> %MODFILE_NAME%
echo Only respond with the `functools[...]` structure if a tool is being called. Do not add any other text before or after it.^ >> %MODFILE_NAME%
echo If no tool is needed, respond with a regular text message.^ >> %MODFILE_NAME%
echo """ >> %MODFILE_NAME%
echo. >> %MODFILE_NAME%
echo # Recommended Parameters (adjust as needed)^ >> %MODFILE_NAME%
echo PARAMETER stop "^<\|end\|^\>" >> %MODFILE_NAME%
echo PARAMETER stop "^<\|user\|^\>" >> %MODFILE_NAME%
echo PARAMETER stop "^<\|assistant\|^\>" >> %MODFILE_NAME%
echo PARAMETER stop "functools[" >> %MODFILE_NAME%

echo Modelfile %MODFILE_NAME% created successfully.
echo.

:: --- Run ollama create ---
echo Running ollama create for %CUSTOM_MODEL_NAME%...
echo This may take a few moments.
ollama create %CUSTOM_MODEL_NAME% -f %MODFILE_NAME%

:: --- Check for errors ---
if errorlevel 1 (
    echo.
    echo [ERROR] 'ollama create' command failed.
    echo Please check the output above for error messages from Ollama.
    echo Ensure Ollama is running and the base model '%BASE_MODEL_NAME%' is available (run 'ollama list').
    echo You can also check Ollama server logs for more details.
    goto :eof
)

echo.
echo Successfully created Ollama model: %CUSTOM_MODEL_NAME%
echo.
echo --- Next Steps ---
echo 1. If you are using this with an agent (like the Roblox Studio AI Broker),
echo    update its configuration to use the model name: %CUSTOM_MODEL_NAME%
echo    (e.g., via command-line argument '--ollama_model %CUSTOM_MODEL_NAME%' or in a config file).
echo 2. Relaunch your agent.
echo.
echo The Modelfile (%MODFILE_NAME%) has been left in the current directory.
echo You can delete it if you no longer need it, or keep it for reference.

endlocal
:eof
echo.
pause
