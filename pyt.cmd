@ECHO OFF
SETLOCAL EnableDelayedExpansion
REM Entrambi gli script sono nella stessa cartella di questo file (%~dp0),
REM cosi' funziona da qualsiasi directory di lavoro
SET "PYSCRIPT=%~dp0pyt.py"
REM Check if first parameter is a path to pyn.cmd
IF EXIST "%~1" (
    SET "PYN=%~1"
    SHIFT
) ELSE (
    SET "PYN=%~dp0pyn.cmd"
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