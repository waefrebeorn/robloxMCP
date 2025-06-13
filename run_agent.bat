@echo OFF
SETLOCAL ENABLEDELAYEDEXPANSION

REM === Configuration ===
SET "VENV_DIR=venv"
SET "AGENT_SCRIPT=main.py"

REM === Main Logic ===
CALL :ActivateVenv
IF !ERRORLEVEL! NEQ 0 GOTO :eof

CALL :RunAgent
IF !ERRORLEVEL! NEQ 0 GOTO :eof

REM === Completion ===
ECHO.
ECHO Agent execution finished or was interrupted.
GOTO :eof

REM === Subroutines ===
:ActivateVenv
    ECHO.
    ECHO Activating virtual environment from '!VENV_DIR!'...
    IF NOT EXIST "!VENV_DIR!\Scripts\activate.bat" (
        ECHO ERROR: Virtual environment activation script not found at '!VENV_DIR!\Scripts\activate.bat'.
        ECHO Please run the 'setup_venv.bat' script first to create the virtual environment.
        EXIT /B 1
    )
    CALL "!VENV_DIR!\Scripts\activate.bat"
    ECHO Virtual environment activated.
EXIT /B 0

:RunAgent
    ECHO.
    ECHO Starting the Roblox Agent ('!AGENT_SCRIPT!')...
    IF NOT EXIST "!AGENT_SCRIPT!" (
        ECHO ERROR: Agent script '!AGENT_SCRIPT!' not found.
        EXIT /B 1
    )
    python "!AGENT_SCRIPT!"

    REM Capturing the error level from the python script itself
    SET "PYTHON_ERRORLEVEL=!ERRORLEVEL!"
    IF !PYTHON_ERRORLEVEL! NEQ 0 (
        ECHO WARNING: The agent script exited with error code !PYTHON_ERRORLEVEL!.
    ) ELSE (
        ECHO Agent script completed.
    )
    REM Propagate the python script's error level
    EXIT /B !PYTHON_ERRORLEVEL!

REM === Final Exit Point ===
:eof
ENDLOCAL
ECHO.
PAUSE
EXIT /B %ERRORLEVEL%
