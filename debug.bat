@echo off

set CD="%~dp0"
cd %~dp0

echo checking...

tasklist /V /fi "imagename eq python.exe" /fo csv

echo.

tasklist /V /fi "imagename eq python.exe" /fo csv 2>NUL | find /i "TTP %1" > NUL
if "%ERRORLEVEL%"=="0" GOTO recording

echo -- start ttp_recorder.py %1
goto end

:recording

echo -- %1 is recording

:end

echo done