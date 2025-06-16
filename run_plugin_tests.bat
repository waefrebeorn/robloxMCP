@echo OFF
SETLOCAL ENABLEDELAYEDEXPANSION

REM === Configuration ===
SET "VENV_DIR=venv"
SET "AGENT_SCRIPT=main.py"
SET "ERROR_COUNT=0"

REM === Define Test Commands ===
SET "TEST_CMD_1=create a part named TestPartFromBatch"
SET "TEST_CMD_2=get the properties of Workspace.TestPartFromBatch"
SET "TEST_CMD_3=run code print('Hello from Batch RunCode')"
SET "TEST_CMD_4=select the part named TestPartFromBatch"
SET "TEST_CMD_5=delete Workspace.TestPartFromBatch"
SET "TEST_CMD_6=What is the current time of day in lighting?"
SET "TEST_CMD_7=Create a sound in workspace with sound ID rbxts://textures/ui/click.wav and name it ClickSound then play it and then delete it"
SET "NUM_TEST_CMDS=7"

REM === Main Logic ===
CALL :ActivateVenv
IF !ERRORLEVEL! NEQ 0 (
    ECHO ERROR: Failed to activate virtual environment. Script will now exit.
    PAUSE
    ENDLOCAL
    EXIT /B !ERRORLEVEL!
)

ECHO.
ECHO Starting Plugin Test Command Sequence...
ECHO Agent Script: "%~dp0!AGENT_SCRIPT!"
ECHO =====================================

FOR /L %%I IN (1,1,%NUM_TEST_CMDS%) DO (
    SET "CURRENT_COMMAND_VAR=TEST_CMD_%%I"
    CALL SET "CURRENT_COMMAND=%%%CURRENT_COMMAND_VAR%%%"

    ECHO.
    ECHO Running test %%I of %NUM_TEST_CMDS%: "!CURRENT_COMMAND!"
    ECHO -------------------------------------------------

    python "%~dp0!AGENT_SCRIPT!" --test_command "!CURRENT_COMMAND!"
    SET "CMD_ERRORLEVEL=!ERRORLEVEL!"

    IF !CMD_ERRORLEVEL! NEQ 0 (
        ECHO WARNING: Test "!CURRENT_COMMAND!" failed with error code !CMD_ERRORLEVEL!.
        SET /A ERROR_COUNT+=1
    ) ELSE (
        ECHO Test completed successfully.
    )
    ECHO -------------------------------------------------

    IF %%I NEQ %NUM_TEST_CMDS% (
        ECHO Waiting for 7 seconds...
        TIMEOUT /T 7 /NOBREAK
    )
)

ECHO.
ECHO =====================================
ECHO ---- Test Run Summary ----
IF !ERROR_COUNT! EQU 0 (
    ECHO All %NUM_TEST_CMDS% tests passed successfully.
) ELSE (
    ECHO !ERROR_COUNT! out of %NUM_TEST_CMDS% tests failed.
)
ECHO =====================================
ECHO.

PAUSE
ENDLOCAL & EXIT /B !ERROR_COUNT!

REM === Subroutines ===
:ActivateVenv
    ECHO.
    ECHO Activating virtual environment from '!VENV_DIR!'...
    IF NOT EXIST "%~dp0!VENV_DIR!\Scripts\activate.bat" (
        ECHO ERROR: Virtual environment activation script not found at '%~dp0!VENV_DIR!\Scripts\activate.bat'.
        ECHO Make sure the VENV_DIR is set correctly and the venv exists in the script's directory.
        ECHO Please run the 'setup_venv.bat' script first to create the virtual environment.
        EXIT /B 1
    )
    CALL "%~dp0!VENV_DIR!\Scripts\activate.bat"
    IF !ERRORLEVEL! NEQ 0 (
        ECHO ERROR: Failed to execute activate.bat script.
        EXIT /B 1
    )
    ECHO Virtual environment activated.
EXIT /B 0
