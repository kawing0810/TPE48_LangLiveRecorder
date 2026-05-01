@echo off

set CD="%~dp0"
cd %~dp0

REM remove watchdog from task scheduler

schtasks /delete /tn "TTP Lang Live Watchdog"