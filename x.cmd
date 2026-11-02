@ECHO OFF
SETLOCAL EnableDelayedExpansion
REM ============================================================================
REM x.cmd - Esegue uno script cercandolo per nome nelle cartelle note
REM Uso: x.cmd scriptname [parametri...]
REM VERSIONE 20261014
REM ============================================================================

REM --- Array scriptsnames: nomi file riconosciuti (case-insensitive) ---
REM     Con estensione (es. pyn.cmd) o senza (es. pyt): senza estensione,
REM     se il nome esatto non esiste, si prova fallback .cmd/.bat/.exe.
REM     Aggiungere una riga SET per ogni script: SET "SCRIPTNAMES[N]=nome"
SET "SCRIPTNAMES[0]=pyn.cmd"
SET "SCRIPTNAMES[1]=pyt.cmd"
SET "SCRIPTNAMES[2]=pyt"
SET "SCRIPTNAMES[3]=pyn"

REM --- Array folders: cartelle dove cercare, in ordine di priorita' (vince la prima) ---
SET "FOLDERS[0]=K:\Scripts"
SET "FOLDERS[1]=K:\Tools"
SET "FOLDERS[2]=V:\Scripts"
SET "FOLDERS[3]=g:\il mio Drive\Scripts"

IF "%~1"=="" GOTO :HELP

REM --- Comando speciale 's': esegue il comando successivo SOLO da G:\Il mio Drive\Scripts ---
IF /I "%~1"=="s" (
    IF "%~2"=="" (
        ECHO [ERRORE] 's' richiede un comando come secondo parametro.
        GOTO :HELP
    )
    SET "SCRIPTNAME=%~2"
    SET "PARAMS="
    SHIFT
    SHIFT
    :S_LOOP_PARAMS
    IF "%~1"=="" GOTO :S_RUN
    SET "PARAMS=!PARAMS! "%~1""
    SHIFT
    GOTO :S_LOOP_PARAMS
    :S_RUN
    SET "FOUND_SCRIPT=G:\Il mio Drive\Scripts\%SCRIPTNAME%"
    IF NOT EXIST "!FOUND_SCRIPT!" (
        FOR %%X IN (cmd bat exe) DO IF NOT DEFINED FOUND_SCRIPT IF EXIST "G:\Il mio Drive\Scripts\%SCRIPTNAME%.%%X" SET "FOUND_SCRIPT=G:\Il mio Drive\Scripts\%SCRIPTNAME%.%%X"
    )
    IF NOT EXIST "!FOUND_SCRIPT!" (
        ECHO [ERRORE] script "%SCRIPTNAME%" non trovato in G:\Il mio Drive\Scripts
        ENDLOCAL & EXIT /B 1
    )
    GOTO :RUN
)

SET "SCRIPTNAME=%~1"
SHIFT

:HANDLE_PARAMS

REM --- Parametri successivi (dal secondo in poi), virgolettati per gli spazi ---
SET "PARAMS="
:LOOP_PARAMS
IF "%~1"=="" GOTO :END_PARAMS
SET "PARAMS=!PARAMS! "%~1""
SHIFT
GOTO :LOOP_PARAMS
:END_PARAMS

REM --- 1. scriptname deve stare in tabella scriptsnames ---
SET "FOUND_IN_TABLE="
FOR /L %%i IN (0,1,20) DO (
    IF DEFINED SCRIPTNAMES[%%i] IF /I "!SCRIPTNAMES[%%i]!"=="%SCRIPTNAME%" SET "FOUND_IN_TABLE=1"
)
IF DEFINED FOUND_IN_TABLE GOTO :FIND_FOLDER
ECHO [ERRORE] scriptname "%SCRIPTNAME%" non presente in tabella scriptsnames.
ECHO.
ECHO Script riconosciuti:
FOR /L %%i IN (0,1,20) DO IF DEFINED SCRIPTNAMES[%%i] ECHO   - !SCRIPTNAMES[%%i]!
ENDLOCAL & EXIT /B 1

:FIND_FOLDER
REM --- 2. cerca nelle cartelle (vince la prima che contiene lo script) ---
SET "FOUND_SCRIPT="
FOR /L %%i IN (0,1,20) DO (
    IF DEFINED FOLDERS[%%i] IF NOT DEFINED FOUND_SCRIPT IF EXIST "!FOLDERS[%%i]!\%SCRIPTNAME%" SET "FOUND_SCRIPT=!FOLDERS[%%i]!\%SCRIPTNAME%"
)
IF DEFINED FOUND_SCRIPT GOTO :RUN
REM --- 2b. nome senza estensione e non trovato esatto: fallback .cmd/.bat/.exe ---
FOR /F "delims=" %%E IN ("%SCRIPTNAME%") DO IF NOT "%%~xE"=="" GOTO :NOT_FOUND
FOR %%X IN (cmd bat exe) DO FOR /L %%i IN (0,1,20) DO (
    IF NOT DEFINED FOUND_SCRIPT IF DEFINED FOLDERS[%%i] IF EXIST "!FOLDERS[%%i]!\%SCRIPTNAME%.%%X" SET "FOUND_SCRIPT=!FOLDERS[%%i]!\%SCRIPTNAME%.%%X"
)
IF DEFINED FOUND_SCRIPT GOTO :RUN
:NOT_FOUND
ECHO [ERRORE] script "%SCRIPTNAME%" non trovato in nessuna cartella.
ECHO.
ECHO Cartelle cercate:
FOR /L %%i IN (0,1,20) DO IF DEFINED FOLDERS[%%i] ECHO   - !FOLDERS[%%i]!
ENDLOCAL & EXIT /B 1

:RUN
REM Se e' un eseguibile (.exe) va lanciato diretto, non con CALL (riservato ai batch)
FOR %%E IN ("!FOUND_SCRIPT!") DO IF /I "%%~xE"==".exe" GOTO :RUN_EXE
ECHO CLI: CALL "!FOUND_SCRIPT!"%PARAMS%
CALL "!FOUND_SCRIPT!"%PARAMS%
ENDLOCAL
GOTO :END

:RUN_EXE
ECHO CLI: "!FOUND_SCRIPT!"%PARAMS%
"!FOUND_SCRIPT!"%PARAMS%
ENDLOCAL
GOTO :END

:HELP
ECHO Uso: x.cmd scriptname [parametri...]
ECHO Esegue scriptname cercandolo nelle cartelle note, solo se in tabella scriptsnames.
ECHO.
ECHO Comando speciale: x.cmd s comando [parametri...]
ECHO   Esegue 'comando' cercandolo SOLO in G:\Il mio Drive\Scripts (con fallback .cmd/.bat/.exe)
ECHO   e passa i parametri successivi. Non usa la tabella scriptsnames ne' le cartelle FOLDERS.
ECHO.
ECHO Cartelle (per uso senza 's'):
FOR /L %%i IN (0,1,20) DO IF DEFINED FOLDERS[%%i] ECHO   - !FOLDERS[%%i]!
ECHO.
ECHO Script riconosciuti (tabella scriptsnames):
FOR /L %%i IN (0,1,20) DO IF DEFINED SCRIPTNAMES[%%i] ECHO   - !SCRIPTNAMES[%%i]!
GOTO :END

:END
