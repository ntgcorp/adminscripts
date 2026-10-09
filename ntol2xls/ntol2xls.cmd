@ECHO OFF
REM Get the base name of this batch file (without extension)
for %%F in ("%0") do set PYSCRIPT=%%~nF.py
SET PYN=k:\tools\pyn.cmd
REM Show the command with all parameters
ECHO "%PYN%" "%PYSCRIPT%" %*
REM Execute passing all parameters
"%PYN%" "%PYSCRIPT%" %*