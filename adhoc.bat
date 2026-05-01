@echo off
REM change CHCP to UTF-8
REM CHCP 65001

set CD="%~dp0"
cd %~dp0

set /p langliveid="Enter Lang Live ID: "

tasklist /V /fi "imagename eq python.exe" /fo csv 2>NUL | find /i "TTP %langliveid%" > NUL
if "%ERRORLEVEL%"=="0" GOTO end

echo start ttp_recorder.py %langliveid%
cmd.exe /c start "%langliveid%" python ttp_recorder.py %langliveid%

:end