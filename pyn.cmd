@ECHO OFF
REM LAUNCHER PYTHON / PODMAN / ALTRO VIA CMD - BASH
REM VERSIONE 20261010 - Rename x->py (test<-pytest, mod<-pymod), pip help in zona Python, stub x/pymod/pip in py
REM VERSIONE 20261011 - podman export <image> <file.tar> (save) e import <file.tar> (load)
REM VERSIONE 20261016 - Preflight PY_CMD in :RUN (venv con base mancante -> errore chiaro)
REM VERSIONE 20261016 - Fix ricerca PY_PATH a due passate: strict (python.exe/App) su tutti i path prima del fallback *.* (che fermava la ricerca al primo path esistente senza python)
REM VERSIONE 20261015 - ocode startdesk: avvia OpenCode Desktop da path fisso (Win) /opt/OpenCode (Linux, solo doc)
REM VERSIONE 20261015 - help podtips: promemoria comandi podman frequenti
REM VERSIONE 20261015 - podman stop (ferma tutti) e reset (rm -f tutti); direttiva help con sub-help pip-podman-pandoc
REM VERSIONE 20261014 - Nuova direttiva shell: podman exec -it in container attivo
REM VERSIONE 20261014 - podman list image rinominato images (all sequenziale invariato)
REM VERSIONE 20261011 - Direttiva pod rinominata podman: machine start|stop, crun, cstop, image set (POD_IMAGE), list machines|image|containers|pod|all; tolti x/end/start/passthrough-help; stub pod
REM VERSIONE 20261010 - Refactor direttive: tolti pip passthrough e pys; x pip*/mod spostati in pip <sub> e pymod; node senza npm + nuova npm dedicata; help b con Git-Bash
REM VERSIONE 20261010 - Convenzione CLI: rimossa riga dedicata Python Path; ogni esecuzione stampa CLI: + stringa comando (python, java, powershell, access, bash, chrome, podman, pandoc, ocode)
REM VERSIONE 20261010 - Aggiunto dominio node (solo Windows): Node.js portable (array V:\Tools\nodejs, D:\APPLIC\NODEJS, C:\APPLIC\NODEJS o NODEJS_PATH) + npm.cmd dallo stesso path
REM VERSIONE 20261009 - Aggiunto dominio pys: esegue script python (nomi semplici risolti in %~dp0) col python calcolato, senza richiamare pyn.cmd
REM VERSIONE 20261008 - Variabile PATH_SCRIPTS (default Windows G:\Il mio Drive\Scripts, Linux /mnt/gdrive/scripts); ocode start usa opencode.json da PATH_SCRIPTS; nuovo x pytest (test_python.py da PATH_SCRIPTS)
REM VERSIONE 20261007 - Aggiunto dominio ocode per avvio opencode (logica da opencode_start.cmd: cerca opencode_start_base.cmd nei possibili paths, cwd invariato)
REM VERSIONE 20261007 - Aggiunto dominio a (1 carattere, solo Windows) per esecuzione Microsoft Access con parametri successivi
REM VERSIONE 20260930 - Fix quoting: confronti dispatch con %~1/%~2 e argv :RUN con %~3-%~9 (path con spazi tra virgolette davano "<...> non atteso" e doppio-quoting)
REM VERSIONE 20260928 - Aggiunto dominio ps per esecuzione script PowerShell (.ps1), logica da ps_start.cmd
REM VERSIONE 20260921 - Aggiunto comando j per esecuzione Java (.java/.class/.jar)
REM VERSIONE 20260911 - Corretto launcher in calcolo py_path
REM VERSIONE 20260830 - Corretto launcher scegliendo path python accellerando
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

SET PYN_VER=20261016

REM PER PRIMO
:SETUP
SET PY_SCRIPT=%0
SET PY_P0=%~dp0
IF "%PY_TYPE%"=="" SET PY_TYPE=X64
SET PY_PATH=
SET "PAR1=%~1"
SET "PAR2=%~2"
IF "%PY_ENV%"=="" SET PY_ENV=myenv
REM Cartella script condivisi (Windows default; su Linux /mnt/gdrive/Scripts): sovrascrivibile da esterno
IF "%PATH_SCRIPTS%"=="" SET "PATH_SCRIPTS=G:\Il mio Drive\Scripts"
REM Normalizza: senza backslash finale (tranne radici tipo G:\); le composizioni usano sempre \%SEP%
IF NOT "%PATH_SCRIPTS:~3,1%"=="" IF "%PATH_SCRIPTS:~-1%"=="\" SET "PATH_SCRIPTS=%PATH_SCRIPTS:~0,-1%"

REM ALTRI COMANDI ESTESI
IF "%~1"=="podman" GOTO :PODMAN
IF "%~1"=="pandoc" GOTO :PANDOC
IF "%~1"=="b"      GOTO :BASH
IF "%~1"=="j"      GOTO :JAVA
IF "%~1"=="ps"     GOTO :PS
IF "%~1"=="a"      GOTO :A
IF "%~1"=="ocode"  GOTO :OCODE
IF "%~1"==""       GOTO :SINTASSI
IF "%~1"=="chrome" GOTO :CHROME
IF "%~1"=="node" GOTO :NODE
IF "%~1"=="npm" GOTO :NPM
IF "%~1"=="shell" GOTO :SHELL
IF "%~1"=="help" GOTO :HELP

REM POSSIBILI PATH - ordine documentato: K: (se MACH0) > D: > C: > XX (TOOLS locale)
for %%I in ("%~dp0..") do set "PATH_PADRE=%%~fI"

SET "PATHP_01=V:\Tools\PYTHON%PY_TYPE%"
SET "PATHP_02=D:\APPLIC\PYTHON%PY_TYPE%"
SET "PATHP_03=K:\Tools\Python%PY_TYPE%"
SET "PATHP_XX=%PATH_PADRE%\TOOLS\PYTHON%PY_TYPE%"

REM CASO VDI.MACH0 - priorita' assoluta a K: se flag esiste e path e' valido
IF EXIST "K:\MACH0_PROD.TXT" (
    IF EXIST "%PATHP_03%\python.exe" SET "PY_PATH=%PATHP_03%" & GOTO :PYN_1
    IF EXIST "%PATHP_03%\App\python.exe" SET "PY_PATH=%PATHP_03%" & GOTO :PYN_1
    IF EXIST "%PATHP_03%\*.*" SET "PY_PATH=%PATHP_03%" & GOTO :PYN_1
)

REM Ricerca in ordine: eventuale PATHP_ENV (override esterno) poi D:, C:, K:, XX
IF DEFINED PATHP_ENV (
    IF EXIST "%PATHP_ENV%\python.exe" SET "PY_PATH=%PATHP_ENV%" & GOTO :PYN_1
    IF EXIST "%PATHP_ENV%\App\python.exe" SET "PY_PATH=%PATHP_ENV%" & GOTO :PYN_1
    IF EXIST "%PATHP_ENV%\*.*" SET "PY_PATH=%PATHP_ENV%" & GOTO :PYN_1
)
REM Pass 1 STRICT: python.exe / App\python.exe su TUTTI i path (priorita' a chi ha python vero)
FOR %%A IN ("%PATHP_01%" "%PATHP_02%" "%PATHP_03%" "%PATHP_XX%") DO (
    IF EXIST "%%~A\python.exe" (
        SET "PY_PATH=%%~A"
        GOTO :PYN_1
    )
    IF EXIST "%%~A\App\python.exe" (
        SET "PY_PATH=%%~A"
        GOTO :PYN_1
    )
)
REM Pass 2 LENIENT: solo se nessuno ha python, accetta prima cartella esistente (fallback storico *.*)
FOR %%A IN ("%PATHP_01%" "%PATHP_02%" "%PATHP_03%" "%PATHP_XX%") DO (
    IF EXIST "%%~A\*.*" (
        SET "PY_PATH=%%~A"
        GOTO :PYN_1
    )
)

:PYN_1
@ECHO LAUNCHER PYTHON PORTABLE NTGCORP %PYN_VER%: Tipo %PY_TYPE%: Path: %PY_PATH% Env: %PY_ENV%
IF "%PY_PATH%"=="" GOTO :ERR

REM PY_CMD
SET PY_CMD=%PY_PATH%\%PY_ENV%\Scripts\PYTHON.EXE
SET PY_PIP=%PY_CMD% -m pip

REM COMANDI ESTESI
IF "%~1"=="pip" GOTO :PIP
IF "%~1"=="pymod" GOTO :PYMOD_MOVED
IF EXIST "%~1"  GOTO :RUN
IF "%~1"=="x" GOTO :X_MOVEDPY
IF "%~1"=="py"   GOTO :PY

:RUN
IF NOT EXIST "%PY_CMD%" GOTO :ERR
REM Preflight: il venv puo' esistere ma puntare a una base mancante (pyvenv.cfg: home)
"%PY_CMD%" --version >nul 2>&1
IF NOT ERRORLEVEL 1 GOTO :RUN_GO
ECHO [ERRORE] Python non avviabile: "%PY_CMD%"
ECHO   Controlla che PY_PATH esista e che il venv non punti a una base mancante (pyvenv.cfg, chiave home).
ECHO   Ricrea l'ambiente con: pyn.cmd py env %PY_ENV% (dopo aver cancellato la cartella)
GOTO :END
:RUN_GO
ECHO CLI: "%PY_CMD%" "%PAR1%" "%PAR2%" "%~3" "%~4" "%~5" "%~6" "%~7" "%~8" "%~9"
"%PY_CMD%" "%PAR1%" "%PAR2%" "%~3" "%~4" "%~5" "%~6" "%~7" "%~8" "%~9"
GOTO :END

:ENV
ECHO Attivazione ambiente Python
IF "%~3"=="" goto :SINTASSI
SET PY_ENV=%3
SET PATHP_ENV=%3
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

:PY
IF "%~2"=="upgrade" GOTO :UPGRADE
IF "%~2"=="env" GOTO :ENV
IF "%~2"=="script" GOTO :ENV_SCRIPT
IF "%~2"=="version" %PY_CMD% --version
IF "%~2"=="test" GOTO :PYTEST
IF "%~2"=="mod" GOTO :PY_MOD
IF "%~2"=="pip" GOTO :PY_PIPMOVED
IF "%~2"=="" GOTO :PY_EMPTY
SET "PYSUB=%~2"
IF "%PYSUB:~0,4%"=="pip_" GOTO :PY_PIPMOVED
GOTO :END
:PY_EMPTY
ECHO COMANDO ESTESO (py) NON INSERITO
GOTO :END

:PY_PIPMOVED
ECHO [ERRORE] py %~2 spostato in pip: usa pip ^<sub^> [args] (es. pip check)
GOTO :END

:X_MOVEDPY
ECHO [ERRORE] direttiva x rinominata in py: usa py ^<comando^>
GOTO :END

:PYMOD_MOVED
ECHO [ERRORE] pymod spostato in py: usa py mod ^<modulo^> [args]
GOTO :END

:PYTEST
IF NOT EXIST "%PY_CMD%" GOTO :ERR
SET "PYTEST_SCRIPT=%PATH_SCRIPTS%\test_python.py"
IF EXIST "%PYTEST_SCRIPT%" GOTO :PYTEST_SHIFT
ECHO [ERRORE] test_python.py non trovato in: "%PATH_SCRIPTS%"
GOTO :END
:PYTEST_SHIFT
SHIFT
SHIFT
SET "PYTEST_ARGS="
:PYTEST_COLLECT
IF "%~1"=="" GOTO :PYTEST_RUN
SET "PYTEST_ARGS=%PYTEST_ARGS% "%~1""
SHIFT
GOTO :PYTEST_COLLECT
:PYTEST_RUN
ECHO CLI: "%PY_CMD%" "%PYTEST_SCRIPT%"%PYTEST_ARGS%
"%PY_CMD%" "%PYTEST_SCRIPT%"%PYTEST_ARGS%
GOTO :END

:PY_MOD
IF NOT EXIST "%PY_CMD%" GOTO :ERR
IF "%~3"=="" GOTO :SINTASSI
ECHO CLI: "%PY_CMD%" -m %3 %4 %5 %6 %7 %8 %9
"%PY_CMD%" -m %3 %4 %5 %6 %7 %8 %9
GOTO :END

:PIP
IF "%~2"=="ulist" GOTO :PIP_ULIST
IF "%~2"=="uexec" GOTO :PIP_UEXEC
IF "%~2"=="re" GOTO :PIP_RE
IF "%~2"=="ri" GOTO :PIP_RI
IF "%~2"=="dna" GOTO :PIP_DNA
IF "%~2"=="pc" GOTO :PIP_PC
IF "%~2"=="pu" GOTO :PIP_PU
IF "%~2"=="i" GOTO :PIP_I
IF "%~2"=="u" GOTO :PIP_U
IF "%~2"=="" GOTO :SINTASSI
%PY_PIP% %2 %3 %4 %5 %6 %7 %8 %9
GOTO :END

:PIP_DNA
rmdir /s /q "%PY_PATH%\Lib\site-packages\~dna" 2>nul
GOTO :END

:PIP_PC
%PY_PIP% cache purge
GOTO :END

:PIP_PU
%PY_PIP% install --upgrade pip
GOTO :END

:PIP_I
%PY_PIP% install --upgrade --only-binary=:all: %3 %4 %5 %6 %7 %8 %9
GOTO :END

:PIP_U
%PY_PIP% install %3 --upgrade --dry-run --only-binary=:all:
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
call "%~dp0pyn.cmd" py upgrade
SET PY_TYPE=X64
call "%~dp0pyn.cmd" py upgrade
SET PY_TYPE=W64
call "%~dp0pyn.cmd" py upgrade
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
    ECHO CLI: "%PANDOC%" "%FILE_MD%" -o "%FILE_HTML%"
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
    ECHO CLI: "%PANDOC%" "%SRC_FILE%" -f docx -t markdown -o "%OUT_MD%"
    "%PANDOC%" "%SRC_FILE%" -f docx -t markdown -o "%OUT_MD%"
    goto :EOF
)
if /i "%ACTION%"=="docx2md" (
    ECHO CLI: "%PANDOC%" "%SRC_FILE%" -f docx -t markdown -o "%OUT_MD%"
    "%PANDOC%" "%SRC_FILE%" -f docx -t markdown -o "%OUT_MD%"
    goto :EOF
)
if /i "%ACTION%"=="pdf2md" (
    ECHO CLI: "%PANDOC%" "%SRC_FILE%" -f pdf -t markdown -o "%OUT_MD%"
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
ECHO CLI: "%SH_EXEC%" "%SH_NAME%" %SH_PARAMS%
"%SH_EXEC%" "%SH_NAME%" %SH_PARAMS%
GOTO :END

REM ----------------------------------------------- JAVA -------------------------------
:JAVA
@ECHO LAUNCHER JAVA %PYN_VER%
REM Risolve JAVANTG_PATH (rispetta valore gia' impostato, altrimenti versione corrente)
IF NOT DEFINED JAVANTG_PATH CALL "%~dp0java_start.cmd"
IF NOT DEFINED JAVANTG_PATH (
    ECHO [ERRORE] JAVANTG_PATH non definita. Esegui Scripts\java_start.cmd [version].
    GOTO :END
)

REM Cerca java.exe (bin\ o root ambiente)
SET "JAVA_EXE=%JAVANTG_PATH%\bin\java.exe"
IF NOT EXIST "%JAVA_EXE%" SET "JAVA_EXE=%JAVANTG_PATH%\java.exe"
IF NOT EXIST "%JAVA_EXE%" (
    ECHO [ERRORE] java.exe non trovato in: %JAVANTG_PATH%\bin o %JAVANTG_PATH%
    GOTO :END
)
SET "JAVAC_EXE=%JAVANTG_PATH%\bin\javac.exe"
IF NOT EXIST "%JAVAC_EXE%" SET "JAVAC_EXE=%JAVANTG_PATH%\javac.exe"

SET "JAVA_FILE=%~2"
IF "%JAVA_FILE%"=="" (
    ECHO [ERRORE] Manca il file .java / .class / .jar da eseguire.
    GOTO :SINTASSI
)
IF NOT EXIST "%JAVA_FILE%" (
    ECHO [ERRORE] File non trovato: "%JAVA_FILE%"
    GOTO :END
)
FOR /F "delims=" %%I IN ("%JAVA_FILE%") DO SET "JAVA_EXT=%%~xI"
SHIFT
SHIFT

REM Raccoglie parametri successivi (da %3 in poi) preservando gli spazi
SET "JAVA_PARAMS="
:JAVA_COLLECT
IF "%~1"=="" GOTO :JAVA_RUN
SET "JAVA_PARAMS=%JAVA_PARAMS% "%~1""
SHIFT
GOTO :JAVA_COLLECT

:JAVA_RUN
IF /I "%JAVA_EXT%"==".java" GOTO :JAVA_SRC
IF /I "%JAVA_EXT%"==".class" GOTO :JAVA_CLASS
IF /I "%JAVA_EXT%"==".jar" GOTO :JAVA_JAR
ECHO [ERRORE] Estensione non supportata (uso .java .class .jar): "%JAVA_FILE%"
GOTO :END

:JAVA_SRC
IF NOT EXIST "%JAVAC_EXE%" (
    ECHO [ERRORE] javac.exe non trovato in: %JAVANTG_PATH%. Serve un JDK per compilare i .java.
    GOTO :END
)
ECHO CLI: "%JAVAC_EXE%" "%JAVA_FILE%"
"%JAVAC_EXE%" "%JAVA_FILE%"
IF ERRORLEVEL 1 (
    ECHO [ERRORE] Compilazione fallita: "%JAVA_FILE%"
    GOTO :END
)

:JAVA_CLASS
FOR /F "delims=" %%I IN ("%JAVA_FILE%") DO SET "JAVA_DIR=%%~dpI"
FOR /F "delims=" %%I IN ("%JAVA_FILE%") DO SET "JAVA_CN=%%~nI"
ECHO CLI: "%JAVA_EXE%" -cp "%JAVA_DIR%" %JAVA_CN%%JAVA_PARAMS%
"%JAVA_EXE%" -cp "%JAVA_DIR%" %JAVA_CN%%JAVA_PARAMS%
GOTO :END

:JAVA_JAR
ECHO CLI: "%JAVA_EXE%" -jar "%JAVA_FILE%"%JAVA_PARAMS%
"%JAVA_EXE%" -jar "%JAVA_FILE%"%JAVA_PARAMS%
GOTO :END

REM ----------------------------------------------- PS (PowerShell) -------------------------------
:PS
@ECHO LAUNCHER POWERSHELL %PYN_VER%
REM Logica da ps_start.cmd: se %2 e' un .ps1 lo esegue con i parametri da %3 in poi,
REM altrimenti esegue ps_start.ps1 (stessa cartella di pyn.cmd) con tutti i parametri da %2 in poi
IF "%~2"=="" GOTO :PS_DEFAULT
IF /I "%~x2"==".ps1" GOTO :PS_CUSTOM
:PS_DEFAULT
SET "PS_SCRIPT=%~dp0ps_start.ps1"
SHIFT
GOTO :PS_COLLECT_ARGS
:PS_CUSTOM
SET "PS_SCRIPT=%~f2"
SHIFT
SHIFT
:PS_COLLECT_ARGS
SET "PS_ARGS="
:PS_LOOP_ARGS
IF "%~1"=="" GOTO :PS_RUN
SET "PS_ARGS=%PS_ARGS% "%~1""
SHIFT
GOTO :PS_LOOP_ARGS
:PS_RUN
IF EXIST "%PS_SCRIPT%" GOTO :PS_EXEC
ECHO [ERRORE] Script PowerShell non trovato: "%PS_SCRIPT%"
GOTO :END
:PS_EXEC
ECHO CLI: powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %PS_ARGS%
powershell -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %PS_ARGS%
GOTO :END

REM ----------------------------------------------- A (Microsoft Access, solo Windows) -------------------------------
:A
@ECHO LAUNCHER ACCESS %PYN_VER%
REM Array dei possibili percorsi di MSACCESS.EXE (vince il primo esistente)
SET "A_EXE="
FOR %%P IN (
    "C:\Program Files\Microsoft Office\root\Office16\MSACCESS.EXE"
    "C:\Program Files (x86)\Microsoft Office\root\Office16\MSACCESS.EXE"
) DO IF EXIST "%%~P" IF NOT DEFINED A_EXE SET "A_EXE=%%~P"
IF NOT DEFINED A_EXE (
    ECHO [ERRORE] MSACCESS.EXE non trovato nei percorsi standard.
    GOTO :END
)
SHIFT
REM Raccoglie tutti i parametri successivi (da %2 in poi) preservando gli spazi
SET "A_PARAMS="
:A_COLLECT
IF "%~1"=="" GOTO :A_RUN
SET "A_PARAMS=%A_PARAMS% "%~1""
SHIFT
GOTO :A_COLLECT
:A_RUN
ECHO CLI: "%A_EXE%"%A_PARAMS%
"%A_EXE%"%A_PARAMS%
GOTO :END

REM ----------------------------------------------- NODE (Node.js portable + npm, solo Windows) -------------------------------
:NODE
@ECHO LAUNCHER NODEJS %PYN_VER%
REM NODEJS_PATH esterno valido ha priorita' (come JAVANTG_PATH); altrimenti array di possibilita' (vince il primo esistente)
IF DEFINED NODEJS_PATH IF EXIST "%NODEJS_PATH%\node.exe" GOTO :NODE_DISPATCH
SET "NODEJS_PATH="
IF EXIST "V:\Tools\nodejs\node.exe" SET "NODEJS_PATH=V:\Tools\nodejs"
IF NOT DEFINED NODEJS_PATH IF EXIST "D:\APPLIC\NODEJS\node.exe" SET "NODEJS_PATH=D:\APPLIC\NODEJS"
IF NOT DEFINED NODEJS_PATH IF EXIST "C:\APPLIC\NODEJS\node.exe" SET "NODEJS_PATH=C:\APPLIC\NODEJS"
IF NOT DEFINED NODEJS_PATH GOTO :NODE_MISSING
GOTO :NODE_DISPATCH
:NODE_MISSING
ECHO [ERRORE] node.exe non trovato (array V:\Tools\nodejs, D:\APPLIC\NODEJS, C:\APPLIC\NODEJS, o NODEJS_PATH).
GOTO :END
:NODE_DISPATCH
SET "NODE_EXE=%NODEJS_PATH%\node.exe"
SET "NODE_FILE=%~2"
IF "%NODE_FILE%"=="" GOTO :SINTASSI
IF EXIST "%NODE_FILE%" GOTO :NODE_COLLECT
ECHO [ERRORE] File non trovato: "%NODE_FILE%"
GOTO :END
:NODE_COLLECT
SHIFT
SHIFT
SET "NODE_PARAMS="
:NODE_LOOP
IF "%~1"=="" GOTO :NODE_RUN
SET "NODE_PARAMS=%NODE_PARAMS% "%~1""
SHIFT
GOTO :NODE_LOOP
:NODE_RUN
ECHO CLI: "%NODE_EXE%" "%NODE_FILE%"%NODE_PARAMS%
"%NODE_EXE%" "%NODE_FILE%"%NODE_PARAMS%
GOTO :END

REM npm dedicato: usa npm.cmd dallo stesso path di node.exe
:NPM
@ECHO LAUNCHER NPM %PYN_VER%
IF DEFINED NODEJS_PATH IF EXIST "%NODEJS_PATH%\npm.cmd" GOTO :NPM_SET
SET "NODEJS_PATH="
IF EXIST "V:\Tools\nodejs\npm.cmd" SET "NODEJS_PATH=V:\Tools\nodejs"
IF NOT DEFINED NODEJS_PATH IF EXIST "D:\APPLIC\NODEJS\npm.cmd" SET "NODEJS_PATH=D:\APPLIC\NODEJS"
IF NOT DEFINED NODEJS_PATH IF EXIST "C:\APPLIC\NODEJS\npm.cmd" SET "NODEJS_PATH=C:\APPLIC\NODEJS"
IF NOT DEFINED NODEJS_PATH GOTO :NPM_MISSING
GOTO :NPM_SET
:NPM_MISSING
ECHO [ERRORE] npm.cmd non trovato (array V:\Tools\nodejs, D:\APPLIC\NODEJS, C:\APPLIC\NODEJS, o NODEJS_PATH).
GOTO :END
:NPM_SET
SET "NPM_CMD=%NODEJS_PATH%\npm.cmd"
SHIFT
SET "NPM_ARGS="
:NPM_LOOP
IF "%~1"=="" GOTO :NPM_RUN
SET "NPM_ARGS=%NPM_ARGS% "%~1""
SHIFT
GOTO :NPM_LOOP
:NPM_RUN
ECHO CLI: CALL "%NPM_CMD%"%NPM_ARGS%
CALL "%NPM_CMD%"%NPM_ARGS%
GOTO :END

REM ----------------------------------------------- SHELL (podman exec interattivo) -------------------------------
:SHELL
@ECHO LAUNCHER SHELL %PYN_VER%
REM Esegue un comando in un container gia' attivo: podman exec -it <name> <shell> [args]
IF "%~2"=="" GOTO :SINTASSI
IF "%~3"=="" GOTO :SINTASSI
SET "SHELL_CONTAINER=%~2"
SHIFT
SHIFT
SET "SHELL_ARGS="
:SHELL_COLLECT
IF "%~1"=="" GOTO :SHELL_RUN
SET "SHELL_ARGS=%SHELL_ARGS% "%~1""
SHIFT
GOTO :SHELL_COLLECT
:SHELL_RUN
ECHO CLI: podman exec -it "%SHELL_CONTAINER%"%SHELL_ARGS%
podman exec -it "%SHELL_CONTAINER%"%SHELL_ARGS%
GOTO :END

REM ----------------------------------------------- OCODE (OpenCode) -------------------------------
:OCODE
@ECHO LAUNCHER OPENCODE %PYN_VER%
REM Logica integrata da opencode_start.cmd: sottocomandi "start" (terminale) e "startdesk" (desktop),
REM altri sottocomandi futuri si aggiungono qui con IF /I "%~2"=="..."
IF "%~2"=="" GOTO :SINTASSI
IF /I "%~2"=="start" GOTO :OCODE_START
IF /I "%~2"=="startdesk" GOTO :OCODE_STARTDESK
ECHO [ERRORE] Sottocomando ocode non riconosciuto: "%~2" (uso: ocode start^|startdesk)
GOTO :END

:OCODE_START
REM Cerca opencode_start_base.cmd nei possibili paths ed eseguilo.
REM La cartella di riferimento resta quella da cui viene eseguito pyn.cmd (%CD%
REM del chiamante): nessun CD, OPENCODE_CONFIG_DIR punta al cwd, non a %~dp0.
setlocal enabledelayedexpansion
SET "OCODE_CWD=%CD%"
SHIFT
SHIFT
REM Raccoglie eventuali parametri successivi (da %3 in poi) da inoltrare allo script base
SET "OCODE_ARGS="
:OCODE_COLLECT
IF "%~1"=="" GOTO :OCODE_SEARCH
SET "OCODE_ARGS=!OCODE_ARGS! "%~1""
SHIFT
GOTO :OCODE_COLLECT
:OCODE_SEARCH
SET "PATHS[0]=C:\PortableAi\Tools\Opencode"
SET "PATHS[1]=V:\PortableAi\Tools\Opencode"
SET "PATHS[2]=X:\_applic\opencode"
SET "PATHS[3]=%~dp0..\Tools\Opencode"
SET "FOUND_SCRIPT="
FOR /L %%i IN (0,1,3) DO (
    IF EXIST "!PATHS[%%i]!\opencode_start_base.cmd" (
        SET "FOUND_SCRIPT=!PATHS[%%i]!\opencode_start_base.cmd"
        ECHO !FOUND_SCRIPT!
        GOTO :OCODE_FOUND
    )
)
:OCODE_FOUND
IF DEFINED FOUND_SCRIPT GOTO :OCODE_RUN
ECHO [ERRORE] Impossibile trovare opencode_start_base.cmd nei percorsi specificati.
ENDLOCAL
GOTO :END
:OCODE_RUN
ECHO Trovato script base in: !FOUND_SCRIPT!
SET "OPENCODE_CONFIG_DIR=!OCODE_CWD!"
ECHO OPENCODE_CONFIG_DIR=!OPENCODE_CONFIG_DIR!
REM File di config dal folder PATH_SCRIPTS (esportato per lo script base)
SET "OPENCODE_CONFIG_FILE=%PATH_SCRIPTS%\opencode.json"
IF EXIST "!OPENCODE_CONFIG_FILE!" (
    ECHO OPENCODE_CONFIG_FILE=!OPENCODE_CONFIG_FILE!
) ELSE (
    ECHO [ATTENZIONE] opencode.json non trovato in: "%PATH_SCRIPTS%"
)
ECHO CLI: CALL "!FOUND_SCRIPT!"!OCODE_ARGS!
CALL "!FOUND_SCRIPT!"!OCODE_ARGS!
PAUSE
ENDLOCAL
GOTO :END

:OCODE_STARTDESK
REM Avvia OpenCode Desktop da posizione fissa (niente terminale/base script).
REM Windows: opencode.exe in @opencode-aidesktop; Linux: /opt/OpenCode/opencode (vedi prompt).
SET "OCODE_DESKEXE=C:\Users\User\AppData\Local\Programs\@opencode-aidesktop\opencode.exe"
IF EXIST "%OCODE_DESKEXE%" GOTO :OCODE_DESKCOLLECT
ECHO [ERRORE] opencode.exe non trovato in: "C:\Users\User\AppData\Local\Programs\@opencode-aidesktop"
GOTO :END
:OCODE_DESKCOLLECT
SHIFT
SHIFT
SET "OCODE_DESKARGS="
:OCODE_DESKLOOP
IF "%~1"=="" GOTO :OCODE_DESKRUN
SET "OCODE_DESKARGS=%OCODE_DESKARGS% "%~1""
SHIFT
GOTO :OCODE_DESKLOOP
:OCODE_DESKRUN
ECHO CLI: "%OCODE_DESKEXE%"%OCODE_DESKARGS%
"%OCODE_DESKEXE%"%OCODE_DESKARGS%
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
    ECHO CLI: "%CH_CMD%" --remote-debugging-port=9222 --user-data-dir="C:\chromedata"
    "%CH_CMD%" --remote-debugging-port=9222 --user-data-dir="C:\chromedata"
)
GOTO :END

REM ----------------------------------------------- PODMAN -------------------------------
:PODMAN
@ECHO LAUNCHER PODMAN %PYN_VER%
IF "%POD_PATH%"=="" SET POD_PATH=c:\podman
IF "%POD_APP%"=="" SET POD_APP=ntjobsos
IF "%~2"=="" GOTO :SINTASSI
IF /I "%~2"=="machine" GOTO :PODMAN_MACHINE
IF /I "%~2"=="crun" GOTO :PODMAN_CRUN
IF /I "%~2"=="cstop" GOTO :PODMAN_CSTOP
IF /I "%~2"=="image" GOTO :PODMAN_IMAGE
IF /I "%~2"=="list" GOTO :PODMAN_LIST
IF /I "%~2"=="export" GOTO :PODMAN_EXPORT
IF /I "%~2"=="import" GOTO :PODMAN_IMPORT
IF /I "%~2"=="stop" GOTO :PODMAN_STOPALL
IF /I "%~2"=="reset" GOTO :PODMAN_RESET
IF /I "%~2"=="opt" GOTO :PODMAN_OPT

ECHO CLI: podman %2 %3 %4 %5 %6 %7 %8 %9
podman %2 %3 %4 %5 %6 %7 %8 %9
GOTO :END

:PODMAN_MACHINE
IF /I "%~3"=="start" GOTO :PODMAN_MACHINE_START
IF /I "%~3"=="stop" GOTO :PODMAN_MACHINE_STOP
ECHO [ERRORE] podman machine richiede start o stop.
GOTO :END
:PODMAN_MACHINE_START
ECHO CLI: podman machine start
podman machine start
GOTO :END
:PODMAN_MACHINE_STOP
ECHO CLI: podman machine stop
podman machine stop
GOTO :END

:PODMAN_CRUN
IF "%~3"=="" GOTO :SINTASSI
IF "%~4"=="" GOTO :SINTASSI
ECHO CLI: podman run -it --rm --name %3 %4 %5 %6 %7 %8 %9
podman run -it --rm --name %3 %4 %5 %6 %7 %8 %9
GOTO :END

:PODMAN_CSTOP
IF "%~3"=="" GOTO :SINTASSI
ECHO CLI: podman stop %3
podman stop %3
GOTO :END

:PODMAN_STOPALL
ECHO CLI: podman stop - ferma tutti i container attivi
FOR /F "delims=" %%c IN ('podman ps -q') DO (
    ECHO CLI: podman stop %%c
    podman stop %%c
)
GOTO :END

:PODMAN_RESET
ECHO CLI: podman rm -f - rimuove tutti i container (anche fermi)
FOR /F "delims=" %%c IN ('podman ps -a -q') DO (
    ECHO CLI: podman rm -f %%c
    podman rm -f %%c
)
GOTO :END

:PODMAN_IMAGE
IF /I "%~3"=="set" GOTO :PODMAN_IMAGE_SET
ECHO [ERRORE] podman image richiede set ^<image_name^>.
GOTO :END
:PODMAN_IMAGE_SET
IF "%~4"=="" GOTO :SINTASSI
SET "POD_IMAGE=%~4"
ECHO POD_IMAGE=%POD_IMAGE%
GOTO :END

:PODMAN_LIST
IF /I "%~3"=="machines" GOTO :PODMAN_LIST_MACHINES
IF /I "%~3"=="images" GOTO :PODMAN_LIST_IMAGES
IF /I "%~3"=="containers" GOTO :PODMAN_LIST_CONTAINERS
IF /I "%~3"=="all" GOTO :PODMAN_LIST_ALL
ECHO [ERRORE] podman list richiede machines^|images^|containers^|all.
GOTO :END
:PODMAN_LIST_MACHINES
ECHO CLI: podman machine list
podman machine list
GOTO :END
:PODMAN_LIST_IMAGES
ECHO CLI: podman images
podman images
GOTO :END
:PODMAN_LIST_CONTAINERS
ECHO CLI: podman ps -a
podman ps -a
GOTO :END
:PODMAN_LIST_ALL
ECHO CLI: podman machine list
podman machine list
ECHO CLI: podman images
podman images
ECHO CLI: podman ps -a
podman ps -a
GOTO :END

:PODMAN_EXPORT
IF "%~3"=="" GOTO :SINTASSI
IF "%~4"=="" GOTO :SINTASSI
ECHO CLI: podman save --output "%~4" "%~3"
podman save --output "%~4" "%~3"
GOTO :END

:PODMAN_IMPORT
IF "%~3"=="" GOTO :SINTASSI
IF NOT EXIST "%~3" GOTO :PODMAN_IMPORT_MISSING
ECHO CLI: podman load --input "%~3"
podman load --input "%~3"
GOTO :END
:PODMAN_IMPORT_MISSING
ECHO [ERRORE] File tar non trovato: "%~3"
GOTO :END

:PODMAN_OPT
REM USCITA OS-SPECIFICA: Optimize-VHD richiede PowerShell e Hyper-V (Windows)
where powershell >nul 2>&1
if errorlevel 1 (
    echo [USCITA OS-SPECIFICA] PowerShell non trovato. Optimize-VHD è esclusivo di Windows/Hyper-V. Su Linux usa 'fstrim' o 'qemu-img'.
    exit /b 1
)

setlocal
set VHDX_PATH=%USERPROFILE%\.local\share\containers\podman\machine\wsl\podman-machine-default_data.vhdx
echo [1/4] Avvio macchina per pulizia interna...
echo CLI: podman machine start
podman machine start
echo [2/4] Esecuzione fstrim...
echo CLI: podman machine ssh sudo fstrim -av
podman machine ssh sudo fstrim -av
echo [3/4] Spegnimento totale WSL...
echo CLI: podman machine stop
podman machine stop
echo CLI: wsl --shutdown
wsl --shutdown
echo [4/4] Ottimizzazione disco VHDX (Richiede privilegi Admin)...
echo CLI: powershell -Command "Optimize-VHD -Path '%VHDX_PATH%' -Mode Full"
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
:HELP
IF "%~2"=="" GOTO :SINTASSI
IF /I "%~2"=="pip" GOTO :HELP_PIP
IF /I "%~2"=="podman" GOTO :HELP_PODMAN
IF /I "%~2"=="pandoc" GOTO :HELP_PANDOC
IF /I "%~2"=="podtips" GOTO :HELP_PODTIPS
ECHO [ERRORE] help: sotto-parametri validi pip-podman-pandoc-podtips.
GOTO :SINTASSI

:HELP_PIP
ECHO PYN.CMD pip check CHECK PIP
ECHO PYN.CMD pip pc CACHE PURGE
ECHO PYN.CMD pip dna RIMUOVE dna precedente installa errato
ECHO PYN.CMD pip pu Upgrade solo pip
ECHO PYN.CMD pip i install librerie (solo binari)
ECHO PYN.CMD pip u upgrade singolo (dry-run, solo binari)
ECHO PYN.CMD pip ulist Lista pipupgrade.txt delle librerie da upgradare
ECHO PYN.CMD pip uexec Esegue upgrade da pipupgrade.txt
ECHO PYN.CMD pip re Crea requirements_x32/x64.txt
ECHO PYN.CMD pip ri file Importa requirements.txt
GOTO :END

:HELP_PODMAN
ECHO PYN.CMD podman machine start-stop. Gestione macchina podman
ECHO PYN.CMD podman crun nome_container nome_immagine [args]. Esegue container con nome
ECHO PYN.CMD podman cstop nome_container. Ferma il container
ECHO PYN.CMD podman stop. Ferma tutti i container attivi
ECHO PYN.CMD podman reset. Rimuove tutti i container (anche fermi)
ECHO PYN.CMD podman image set nome_immagine. Imposta POD_IMAGE
ECHO PYN.CMD podman list machines-images-containers. Elenca oggetti podman
ECHO PYN.CMD podman export nome_immagine file.tar. Esporta immagine in file tar
ECHO PYN.CMD podman import file.tar. Importa immagine da file tar
GOTO :END

:HELP_PANDOC
ECHO PYN.CMD pandoc doc2md file.doc
ECHO PYN.CMD pandoc pdf2md file.doc
ECHO PYN.CMD pandoc md2html file.md file.html
GOTO :END

:HELP_PODTIPS
ECHO podman machine list
ECHO Mostra le macchine virtuali disponibili e quella attiva.
ECHO podman machine start / stop
ECHO Accende o spegne la macchina virtuale.
ECHO podman pull ^<immagine^>
ECHO Scarica un'immagine da un registry.
ECHO podman images
ECHO Elenca le immagini presenti sul sistema.
ECHO podman run [opzioni] ^<immagine^>
ECHO Crea e avvia un nuovo container.
ECHO podman ps (-a)
ECHO Elenca i container attivi (o tutti, compresi i fermi).
ECHO podman stop / start ^<container^>
ECHO Ferma o riavvia un container esistente.
ECHO podman rm ^<container^>
ECHO Elimina un container (usa -f per forzare se attivo).
ECHO podman exec -it ^<container^> ^<shell^>
ECHO Apre una sessione interattiva dentro un container attivo.
ECHO podman volume create ^<nome^>
ECHO Crea un volume persistente.
ECHO podman volume ls
ECHO Elenca tutti i volumi presenti.
ECHO podman logs -f ^<container^>
ECHO Mostra in tempo reale l'output del container.
ECHO podman stats
ECHO Mostra il consumo di risorse in tempo reale.
ECHO podman system prune
ECHO Libera spazio rimuovendo container fermi e dati orfani.
GOTO :END

:SINTASSI
@ECHO OFF
ECHO Launcher: PYTHON PIP/PODMAN/CHROME/BASH/PANDOC/JAVA/PS/OCODE/ACCESS/NODE/NPM/SHELL. R: %PYN_VER%
ECHO Sintassi PYN.CMD script.py [parametri] oppure PYN.CMD dominio comando parametri
ECHO ----- Comandi Estesi. Sintassi pyn dominio parametri_aggiuntivi
ECHO PYN.CMD py [comando esteso]
ECHO PYN.CMD py script nome_script(.exe) e parametri successivi
ECHO PYN.CMD py env ambiente - Cambio o Attivazione Python ENV
ECHO PYN.CMD py version - Versione Python
ECHO PYN.CMD py mod modulo [args] (python -m modulo)
ECHO PYN.CMD py test esegue test_python.py da PATH_SCRIPTS con parametri successivi
ECHO PYN.CMD help pip-podman-pandoc-podtips. Help mirato per direttiva
ECHO PYN.CMD chrome auto. Esecuzione Chrome in modalità AUTO
ECHO PYN.CMD b script.sh parametri (esegue uno script bash su Windows tramite Git-Bash)
ECHO PYN.CMD j script.java/script.class/script.jar parametri (i .java vengono compilati con javac)
ECHO PYN.CMD ps [script.ps1] parametri (senza .ps1 esegue ps_start.ps1 con tutti i parametri)
ECHO PYN.CMD ocode start^|startdesk [parametri] (start=terminale, startdesk=desktop GUI)
ECHO PYN.CMD a [parametri...] (esegue MSACCESS.EXE dai possibili paths, solo Windows)
ECHO PYN.CMD node script.js parametri (Node.js portable, solo Windows)
ECHO PYN.CMD npm ^<comando^> [args] (npm dallo stesso path di node.exe, solo Windows)
ECHO PYN.CMD shell nome_container comando [args] (podman exec -it in container attivo)
GOTO :END

:END
