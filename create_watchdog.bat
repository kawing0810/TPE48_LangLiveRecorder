@echo off

set CD="%~dp0"
cd %~dp0

REM This watchdog will check "TTP Lang Live Checker" is still running or not every 5 minutes
REM When the "Checker" not found, launch a new "Checker"

echo Create TTP Lang Live Watchdog

schtasks /CREATE /tn "TTP Lang Live Watchdog" /tr "wscript %~dp0watchdog.vbs" /sc minute /mo 5

schtasks /run /tn "TTP Lang Live Watchdog"

