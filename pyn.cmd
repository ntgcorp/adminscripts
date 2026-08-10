@ECHO OFF
REM ORIGINALE SU PC GOMERA - LAUNCHER PYTHON / PODMAN / ALTRO VIA CMD - BASH
REM VERSIONE 20260810 - REFACTOR: Corretti bug critici (delayed expansion, doppia exec, path hardcoded).
REM                     Aggiunte uscite OS-specifiche per comandi Windows-only.
REM                     Aggiunta variabile ambiente PYTHON per lancio da esterno
REM VERSIONE 20260714 - Aggiunto tools/pythonx64, pandoc doc2md pdf2md - corretto pyenv.cfg che usi sempre v:
REM VERSIONE 20260703 - Aggiunto BASH
REM VERSIONE 20260701 - Gestione Ambienti diversi MYENV Default, altrimenti cambiato da utente e variabile PY_ENV
REM VERSIONE 20260621 - pandoc
REM VERSIONE 20260619 - AGGIUNTI x pip_ulist che fa file di upgrade e pip_ufile che lo effeta da quel file
REM VERSIONE 20260528 - DISABILITATO UPGRADE PER PROBLEMI CON PIP-REVIEW
REM VERSIONE 20260525 - CORREZIONE GROSSA CON MYENV E CAMBIATA ZONA DI LANCIO, PIP CHECK
REM VERSIONE 20260515 - CORREZIONE INSTALL ONLY BINARY, PIP PURGE
REM VERSIONE 20260415 - CORREZIONE PAR1/PAR2/PAR3
REM VERSIONE 20260313 - AGGIUNTO PODMAN
REM VERSIONE 20260219 - AGGIUNTA W64
REM VERSIONE 20260129 - PICCOLA CORREZIONE
REM VERSIONE 20250803 - PYN MASTER che gestisce gli upgrade "SOLO su NTGCORP" con flag
REM                   - comandi x reqx - pip requirements export e x reqi - pip requirements import
REM VERSIONE 20250405 - CORREZIONI - INSTALLAZIONE CRYPTOGRAFY - FORSE PSUTIL
REM VERSIONE 20250203 - DEFAULT X64
REM VERSIONE 20250130 - GESTIONE MIGLIORE RUNTIME

SET PYN_VER=20260810

REM PER PRIMO
:SETUP
SET PY_SCRIPT=%0
SET PY_P0=%~dp0
IF "%PY_TYPE%"=="" SET PY_TYPE=X64
SET PY_PATH=
SET PAR1=%1
SET PAR2=%2
IF "%PY_ENV%"=="" SET PY_ENV=myenv

REM ALTRI COMANDI ESTESI
IF "%1"=="pod"    GOTO :POD
IF "%1"=="pandoc" GOTO :PANDOC
IF "%1"=="b"      GOTO :BASH
IF "%1"==""       GOTO :SINTASSI
IF "%1"=="chrome" GOTO :CHROME

REM POSSIBILI PATH
SET PATHP_01=D:\APPLIC\PYTHON%PY_TYPE%
SET PATHP_XX=%PATH_PADRE%\TOOLS\PYTHON%PY_TYPE%
SET PATHP_02=C:\APPLIC\PYTHON%PY_TYPE%
SET PATHP_03=K:\Tools\Python%PY_TYPE%
SET PATHP_ENV=%PATHP_ENV%
for %%I in ("%~dp0..") do set "PATH_PADRE=%%~fI"

REM CASO VDI.MACH0
IF EXIST "K:\MACH0_PROD.TXT" SET PY_PATH=%PATHP_MACH0%

FOR %%A IN ("%PATHP_ENV%" "%PATHP_01%" "%PATHP_02%" "%PATHP_03%" "%PATHP_XX%") DO (
    IF EXIST %%~A\*.* SET "PY_PATH=%%~A"
)

:PYN_1
@ECHO LAUNCHER PYTHON PORTABLE NTGCORP %PYN_VER%: Tipo %PY_TYPE%: Path: %PY_PATH% Env: %PY_ENV%
ECHO Python Path: %PY_PATH%
IF "%PY_PATH%"=="" GOTO :ERR

REM PY_CMD
SET PY_CMD=%PY_PATH%\%PY_ENV%\Scripts\PYTHON.EXE
SET PY_PIP=%PY_CMD% -m pip

REM COMANDI ESTESI
IF "%1"=="pip" GOTO :PIP
IF EXIST "%1"  GOTO :RUN
IF "%1"=="x"   GOTO :X

:RUN
IF NOT EXIST "%PY_CMD%" GOTO :ERR
ECHO START PYTHON SCRIPT: %PY_SCRIPT% - %PY_0% - %PY_CMD% - %PAR1% %PAR2% %3 %4 %5 %6 %7 %8 %9
"%PY_CMD%" "%PAR1%" "%PAR2%" "%3" "%4" "%5" "%6" "%7" "%8" "%9"
GOTO :END

:ENV
ECHO Attivazione ambiente Python
IF "%3"=="" goto :SINTASSI
SET PY_ENV=%3
IF EXIST "%PY_PATH%\%PY_ENV%\*.*" (
    echo Ambiente %PY_ENV% trovato.
    GOTO :END
)
IF NOT EXIST "%PY_PATH%\%PY_ENV%\*.*" (
    echo Ambiente %PY_ENV% non trovato. Creazione in corso...
    REM FIX: Rimosso CD e corretto path python base (non più App\python)
    "%PY_PATH%\python.exe" -m venv "%PY_PATH%\%PY_ENV%"
)
GOTO :END

:ENV_SCRIPT
REM FIX: Aggiunto setlocal enabledelayedexpansion e virgolette per gli spazi
setlocal enabledelayedexpansion
set "ALL_ARGS="
shift
shift
:loop_args
if "%~1"=="" goto :end_args
set "ALL_ARGS=!ALL_ARGS! "%~1""
shift
goto :loop_args
:end_args
if defined ALL_ARGS set "ALL_ARGS=!ALL_ARGS:~1!"
"%PY_PATH%\%PY_ENV%\Scripts\%~1" %ALL_ARGS%
endlocal
GOTO :END

:ERR
@ECHO OFF
ECHO PYN: Attenzione, non esiste la cartella PYTHON%PY_TYPE% richiesta allo stesso livello
GOTO :END

:X
IF "%2"=="upgrade" GOTO :UPGRADE
IF "%2"=="env" GOTO :ENV
IF "%2"=="script" GOTO :ENV_SCRIPT
IF "%2"=="mod" %PY_CMD% -m %3 %4 %5 %6 %7 %8 %9
IF "%2"=="pip" %PY_CMD% -m pip %3 %4 %5 %6 %7 %8 %9
IF "%2"=="version" %PY_CMD% --version
IF "%2"=="pip_check" %PY_PIP% check
IF "%2"=="pip_dna" rmdir /s /q "%PY_PATH%\Lib\site-packages\~dna" 2>nul
IF "%2"=="pip_pc" %PY_PIP% cache purge
IF "%2"=="pip_pu" %PY_PIP% install --upgrade pip
IF "%2"=="pip_i" %PY_PIP% install --upgrade --only-binary=:all: %3 %4 %5 %6 %7 %8 %9
IF "%2"=="pip_u" %PY_PIP% install %3 --upgrade --dry-run --only-binary=:all:
IF "%2"=="pip_ulist" GOTO :PIP_ULIST
IF "%2"=="pip_uexec" GOTO :PIP_UEXEC
IF "%2"=="pip_re" GOTO :PIP_RE
IF "%2"=="pip_ri" GOTO :PIP_RI
IF "%2"=="" ECHO COMANDO ESTESO (x) NON INSERITO
GOTO :END

:PIP
%PY_PIP% %2 %3 %4 %5 %6 %7 %8 %9
GOTO :END

:PIP_RE
%PY_PIP% freeze > requirements_%PY_TYPE%.txt
for /f "tokens=1 delims==" %%i in (requirements_%PY_TYPE%.txt) do @echo %%i >> requirements_%PY_TYPE%_LIGHT.txt
GOTO :END

:PIP_ULIST
REM FIX: Rimosso il path hardcoded di PY_CMD, ora usa quello globale
echo Raccolta dei pacchetti obsoleti in corso...
"%PY_CMD%" -m pip list --outdated > "%TEMP%\pip_raw.txt"
echo Generazione del file pipupgrade.txt...
if exist pipupgrade.txt del pipupgrade.txt
for /f "usebackq skip=2 tokens=1" %%a in ("%TEMP%\pip_raw.txt") do echo %%a>> pipupgrade.txt
del "%TEMP%\pip_raw.txt"
echo Operazione completata! Trovi l'elenco in: pipupgrade.txt
GOTO :END

:PIP_UEXEC
REM FIX: Rimossa doppia esecuzione. Usato delayed expansion per errorlevel corretto.
setlocal enabledelayedexpansion
set LOGFILE=pipupgrade.log
echo Inizio aggiornamento: %date% %time% > %LOGFILE%
for /f "usebackq tokens=*" %%p in ("pipupgrade.txt") do (
    echo ------------------------------------------
    echo Aggiornamento in corso: %%p
    echo ------------------------------------------
    %PY_PIP% install --upgrade %%p >> %LOGFILE% 2>&1
    if !errorlevel! equ 0 (
        echo [OK] %%p aggiornato con successo >> %LOGFILE%
    ) else (
        echo [ERRORE] %%p non aggiornato >> %LOGFILE%
    )
)
echo.
echo Processo terminato. Controlla %LOGFILE% per i dettagli.
endlocal
GOTO :END

:PIP_RI
setlocal enabledelayedexpansion
set REQ_FILE=requirements_%PY_TYPE%.txt
set SKIPPED=
for /F "tokens=*" %%i in (%REQ_FILE%) do (
    set LINE=%%i
    if not "!LINE:~0,1!"=="#" (
        if not "!LINE!"=="" (
            echo Installando %%i...
            "%PY_CMD%" -m pip install --upgrade --only-binary=:all: %%i >nul 2>&1
            if !errorlevel! neq 0 (
                echo   SALTATO: %%i
                set SKIPPED=!SKIPPED! %%i
            ) else (
                echo   OK: %%i
            )
        )
    )
)
echo.
echo --- Pacchetti saltati ---
if "!SKIPPED!"=="" (
    echo   Nessuno
) else (
    for %%p in (!SKIPPED!) do echo   - %%p
)
endlocal
GOTO :END

:UPGRADE
%PY_PIP% install --upgrade pip
%PY_PIP% list --outdated
GOTO :END

:UPGALL
ECHO VIENE IMPOSTATA VARIBILE X32 X64 W64 e upgrade per tutti e 2 i tipi
ECHO ATTUALE: %PY_TYPE%
SET PY_STACK=%PY_TYPE%
SET PY_TYPE=X32
call "%~dp0pyn.cmd" x upgrade
SET PY_TYPE=X64
call "%~dp0pyn.cmd" x upgrade
SET PY_TYPE=W64
call "%~dp0pyn.cmd" x upgrade
SET PY_TYPE=%PY_STACK%
SET PY_STACK=
ECHO ATTUALE: %PY_TYPE%
GOTO :END

REM ----------------------------------- PANDOC -------------------------------------
:PANDOC
set "ACTION=%~2"
set "FILE_MD=%~3"
IF EXIST X:\_Applic\Pandoc\pandoc.exe SET PANDOC=X:\_Applic\Pandoc\pandoc.exe
IF EXIST C:\Applic\Pandoc\pandoc.exe SET PANDOC=C:\Applic\Pandoc\pandoc.exe
if "%PANDOC%"=="" goto :eof
if NOT exist "%PANDOC%" goto :eof

if "%ACTION%"=="" (
    echo [ERRORE] Parametri insufficienti. Manca l'azione e il file.
    goto :SINTASSI
)
if /i "%ACTION%"=="pdf2md" GOTO :PANDOC_CONVERT
if /i "%ACTION%"=="docx2md" GOTO :PANDOC_CONVERT
if /i "%ACTION%"=="doc2md" GOTO :PANDOC_CONVERT

if /i "%ACTION%"=="md2html" (
    if "%FILE_MD%"=="" (
        echo [ERRORE] Manca il file .md da convertire.
        goto :SINTASSI
    )
    if NOT exist "%FILE_MD%" (
        echo [ERRORE] Il file sorgente non esiste: "%FILE_MD%"
        goto :SINTASSI
    )
    for /f "delims=" %%I in ("%FILE_MD%") do set "FILE_HTML=%%~dpnI.html"
    "%PANDOC%" "%FILE_MD%" -o "%FILE_HTML%"
)
GOTO :END

:PANDOC_CONVERT
set "SRC_FILE=%~3"
REM FIX: Corretto typo :SINTESSI in :SINTASSI
if "%PANDOC%"=="" goto :SINTASSI
if NOT exist "%PANDOC%" (
    echo [ERRORE] Eseguibile Pandoc non trovato.
    goto :SINTASSI
)
if NOT exist "%SRC_FILE%" (
    echo [ERRORE] Il file sorgente non esiste: "%SRC_FILE%"
    goto :SINTASSI
)
for /f "delims=" %%I in ("%SRC_FILE%") do set "OUT_MD=%%~dpnI.md"

if /i "%ACTION%"=="doc2md" (
    "%PANDOC%" "%SRC_FILE%" -f docx -t markdown -o "%OUT_MD%"
    goto :EOF
)
if /i "%ACTION%"=="docx2md" (
    "%PANDOC%" "%SRC_FILE%" -f docx -t markdown -o "%OUT_MD%"
    goto :EOF
)
if /i "%ACTION%"=="pdf2md" (
    "%PANDOC%" "%SRC_FILE%" -f pdf -t markdown -o "%OUT_MD%"
    goto :EOF
)
echo [ERRORE] Azione "%ACTION%" non riconosciuta.
goto :SINTASSI

REM ---------------------------------------------- BASH -------------------------------
:BASH
@ECHO LAUNCHER BASH GIT-BASH %PYN_VER%
SET "SH_EXEC="
IF EXIST "C:\APPLIC\BASH\GIT-BASH.EXE" SET "SH_EXEC=C:\APPLIC\BASH\GIT-BASH.EXE"
IF "%SH_EXEC%"=="" IF EXIST "D:\APPLIC\BASH\GIT-BASH.EXE" SET "SH_EXEC=D:\APPLIC\BASH\GIT-BASH.EXE"
IF "%SH_EXEC%"=="" IF EXIST "V:\TOOLS\BASH\GIT-BASH.EXE" SET "SH_EXEC=V:\TOOLS\BASH\GIT-BASH.EXE"
IF "%SH_EXEC%"=="" (
    ECHO [ERRORE] GIT-BASH.EXE non trovato in C:\, D:\ o V:\
    GOTO :END
)

SET "SH_NAME=%~2"
IF "%SH_NAME%"=="" (
    ECHO [ERRORE] Manca il nome dello script bash da eseguire.
    GOTO :SINTASSI
)
SHIFT
SHIFT

REM FIX: Raccolta parametri virgolettati per preservare gli spazi
SET "SH_PARAMS="
:BASH_COLLECT
IF "%~1"=="" GOTO :BASH_RUN
SET "SH_PARAMS=%SH_PARAMS% "%~1""
SHIFT
GOTO :BASH_COLLECT

:BASH_RUN
ECHO Esecuzione: "%SH_EXEC%" "%SH_NAME%" %SH_PARAMS%
"%SH_EXEC%" "%SH_NAME%" %SH_PARAMS%
GOTO :END

REM ----------------------------------------------- CHROME -------------------------------
:CHROME
@ECHO LAUNCHER CHROME %PYN_VER%
IF "%~2"=="" GOTO :SINTASSI

REM FIX: Ricerca dinamica di Chrome (non più hardcoded solo su Program Files)
SET "CH_CMD="
IF EXIST "C:\Program Files\Google\Chrome\Application\chrome.exe" SET "CH_CMD=C:\Program Files\Google\Chrome\Application\chrome.exe"
IF NOT DEFINED CH_CMD IF EXIST "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" SET "CH_CMD=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
IF NOT DEFINED CH_CMD IF EXIST "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" SET "CH_CMD=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

IF NOT DEFINED CH_CMD (
    ECHO [ERRORE] chrome.exe non trovato nei percorsi standard.
    GOTO :END
)

IF /I "%~2"=="auto" (
    ECHO [INFO] Avvio di Chrome in modalita' debug...
    "%CH_CMD%" --remote-debugging-port=9222 --user-data-dir="C:\chromedata"
)
GOTO :END

REM ----------------------------------------------- POD -------------------------------
:POD
@ECHO LAUNCHER POD %PYN_VER%
IF "%POD_PATH%"=="" SET POD_PATH=c:\podman
IF "%POD_APP%"=="" SET POD_APP=ntjobsos
IF "%2"=="" GOTO :SINTASSI
IF "%2"=="x" GOTO :POD_RUN
IF "%2"=="start" GOTO :POD_START
IF "%2"=="end" GOTO :POD_END
IF "%2"=="opt" GOTO :POD_OPT

ECHO Podman Esecuzione Standard
podman %2 %3 %4 %5 %6 %7 %8 %9
GOTO :END

:POD_RUN
ECHO Podman Esecuzione Python ntjobsos Script
podman run -it --rm -v "%POD_PATH%:/app" %POD_APP%:v1 %3
GOTO :END

:POD_END
REM USCITA OS-SPECIFICA: WSL è esclusivo di Windows
where wsl >nul 2>&1
if errorlevel 1 (
    echo [USCITA OS-SPECIFICA] WSL non trovato. Su Linux nativo Podman non usa WSL. Usa 'systemctl stop podman'.
    exit /b 1
)
ECHO Podman Stop e chiudi wsl
wsl --shutdown
GOTO :END

:POD_START
ECHO Podman Esecuzione motore
podman machine start
GOTO :END

:POD_OPT
REM USCITA OS-SPECIFICA: Optimize-VHD richiede PowerShell e Hyper-V (Windows)
where powershell >nul 2>&1
if errorlevel 1 (
    echo [USCITA OS-SPECIFICA] PowerShell non trovato. Optimize-VHD è esclusivo di Windows/Hyper-V. Su Linux usa 'fstrim' o 'qemu-img'.
    exit /b 1
)

setlocal
set VHDX_PATH=%USERPROFILE%\.local\share\containers\podman\machine\wsl\podman-machine-default_data.vhdx
echo [1/4] Avvio macchina per pulizia interna...
podman machine start
echo [2/4] Esecuzione fstrim...
podman machine ssh sudo fstrim -av
echo [3/4] Spegnimento totale WSL...
podman machine stop
wsl --shutdown
echo [4/4] Ottimizzazione disco VHDX (Richiede privilegi Admin)...
powershell -Command "Optimize-VHD -Path '%VHDX_PATH%' -Mode Full"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ATTENZIONE: Optimize-VHD e fallito. Assicurati di aver eseguito come AMMINISTRATORE.
) else (
    echo.
    echo OPERAZIONE COMPLETATA CON SUCCESSO!
)
endlocal
GOTO :END

REM ----------------------------------------- SINTASSI -------------------------------
:SINTASSI
@ECHO OFF
ECHO SCRIPT PYN.CMD di lancio PYTHON PORTABLE. X64 o X32 / PODMAN / CHROME / BASH / PANDOC - %PYN_VER%
ECHO Sintassi PYN.CMD script.py [parametri] oppure PYN.CMD dominio comando parametri
ECHO ----- Comandi Dominio Python (Dominio Base), x
ECHO PYN.CMD x [comando esteso]
ECHO PYN.CMD x script nome_script(.exe) e parametri successivi
ECHO PYN.CMD x env ambiente - Cambio o Attivazione Python ENV
ECHO PYN.CMD x version - Versione Python
ECHO PYN.CMD x pip richiamo mod pip [comandi] per gestione librerie interne, aggiornamenti, ecc.
ECHO PYN.CMD x pip_check CHECK PIP
ECHO PYN.CMD x pip_pc CACHE PURGE
ECHO PYN.CMD x pip_dna RIMUOVE dna precedente installa errato
ECHO PYN.CMD x pip_pu Upgrade solo pip
ECHO PYN.CMD x pip_i richiamo mod pip install per install librerie (fino a 7)
ECHO PYN.CMD x pip_u richiamo mod pip upgrade uno solo
ECHO PYN.CMD x pip_ulist Lista pipupgrade.txt delle librerie da upgradare
ECHO PYN.CMD x pip_uexec Eegue upgrade da pipugrade.txt
ECHO PYN.CMD x pip_re/Crea requirements_x32/x64.txt
ECHO PYN.CMD x pip_ri file Importa requirements.txt
ECHO PYN.CMD x mod modulo richiamo mod specifico
ECHO PYN.CMD %CD%\test_python.py (Esecuzione script di test)
ECHO PY_TYPE=Variabile d'ambiente per forzare 32 o 64bit (SET PY_TYPE=X32 o PY_TYPE=X64)
ECHO ----- Comandi POD/PANDOC/BASH/CHROME/PIP
ECHO PYN.CMD pip [comando pip]
ECHO PYN.CMD chrome auto. Esecuzione Chrome in modalità AUTO
ECHO PYN.CMD pod comando script . Devono essere impostate le ENV POD_PATH e POD_APP(ntjobsos default)
ECHO PYN.CMD pod end
ECHO PYN.CMD pod start
ECHO PYN.CMD pandoc doc2md file.doc
ECHO PYN.CMD pandoc pdf2md file.doc
ECHO PYN.CMD pandoc md2html file.md file.html
ECHO PYN.CMD b script.sh parametri
GOTO :END

:END