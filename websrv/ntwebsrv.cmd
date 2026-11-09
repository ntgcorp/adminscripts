REM @ECHO OFF
for %%F in (%0) do set PYSCRIPT=%%~nF.py
SET PYN=x pyn.cmd
ECHO "%PYN%" "%PYSCRIPT%" %1
"%PYN%" "%PYSCRIPT%" %1

