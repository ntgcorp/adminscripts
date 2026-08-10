@ECHO OFF
SETLOCAL EnableDelayedExpansion
REM Get the script name (relative, since we're in the same folder)
SET "PYSCRIPT=pyt.py"
REM Check if first parameter is a path to pyn.cmd
IF EXIST "%~1" (
    SET "PYN=%~1"
    SHIFT
) ELSE (
    SET "PYN=k:\tools\pyn.cmd"
)
REM Build quoted parameter string for all remaining arguments
SET "PARAMS="
:LOOP_PARAMS
IF "%~1"=="" GOTO :END_PARAMS
SET "PARAMS=!PARAMS! "%~1""
SHIFT
GOTO :LOOP_PARAMS
:END_PARAMS
REM Execute passing all parameters
call "%PYN%" "%PYSCRIPT%" !PARAMS!
ENDLOCAL