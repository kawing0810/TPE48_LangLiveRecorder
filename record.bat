@echo off
REM change CHCP to UTF-8
REM CHCP 65001

set CD="%~dp0"
cd %~dp0

tasklist /V /fi "imagename eq python.exe" /fo csv 2>NUL | find /i "TTP %1" > NUL
if "%ERRORLEVEL%"=="0" GOTO end

echo start ttp_recorder.py %1
cmd.exe /c start "%1" python ttp_recorder.py %1

:end