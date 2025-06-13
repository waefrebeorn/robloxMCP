@echo OFF
SETLOCAL ENABLEDELAYEDEXPANSION

REM === Configuration ===
SET "SERVER_EXE_PATH=target\release\rbx-studio-mcp.exe"

REM === Main Logic ===
ECHO Starting Rust MCP Server...
ECHO.

IF NOT EXIST "!SERVER_EXE_PATH!" (
    ECHO ERROR: Rust MCP Server executable not found at '!SERVER_EXE_PATH!'.
    ECHO Please build the server first by running 'build_rust_server.bat'.
    EXIT /B 1
)

ECHO Attempting to run server: "!SERVER_EXE_PATH!" --stdio
ECHO Press Ctrl+C in this window to stop the server manually if needed.
ECHO.
"!SERVER_EXE_PATH!" --stdio

IF !ERRORLEVEL! NEQ 0 (
    ECHO.
    ECHO =====================================================================
    ECHO WARNING: Rust MCP Server exited with error code !ERRORLEVEL!.
    ECHO Review any messages above from the server.
    ECHO =====================================================================
    EXIT /B !ERRORLEVEL!
)

ECHO.
ECHO =====================================================================
ECHO Rust MCP Server has finished execution.
ECHO =====================================================================

REM === Cleanup ===
ENDLOCAL
EXIT /B 0
