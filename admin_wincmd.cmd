@echo off
setlocal

:: Verifica permessi di amministratore e auto-elevazione UAC
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Richiesta elevazione privilegi di amministratore...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Aggiunta di "Apri prompt dei comandi qui" al menu contestuale...

:: Voce cliccando sopra una cartella
reg add "HKCR\Directory\shell\OpenCmdHere" /ve /t REG_SZ /d "Apri prompt dei comandi qui" /f >nul
reg add "HKCR\Directory\shell\OpenCmdHere" /v "Icon" /t REG_SZ /d "cmd.exe" /f >nul
reg add "HKCR\Directory\shell\OpenCmdHere\command" /ve /t REG_SZ /d "cmd.exe /s /k pushd \"%%V\"" /f >nul

:: Voce cliccando sullo sfondo vuoto dentro una cartella
reg add "HKCR\Directory\Background\shell\OpenCmdHere" /ve /t REG_SZ /d "Apri prompt dei comandi qui" /f >nul
reg add "HKCR\Directory\Background\shell\OpenCmdHere" /v "Icon" /t REG_SZ /d "cmd.exe" /f >nul
reg add "HKCR\Directory\Background\shell\OpenCmdHere\command" /ve /t REG_SZ /d "cmd.exe /s /k pushd \"%%V\"" /f >nul

if %errorLevel% equ 0 (
    echo.
    echo [OK] Modifica completata con successo.
) else (
    echo.
    echo [ERRORE] Si e' verificato un problema durante l'aggiornamento del registro.
)

echo.
pause
endlocal