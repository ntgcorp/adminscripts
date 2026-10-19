REM ----- Configurazione -----
set "PYTHON=k:\tools\"
REM ----- Ricava nome script python con PATH completo -----
set "SCRIPT=%~dp0%~n0.py"
REM ----- Esecuzione -----
echo Sintassi file.sh parametri
call "%PYTHON%pyn.cmd" "%SCRIPT%" %*