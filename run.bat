@echo off
REM change CHCP to UTF-8
REM CHCP 65001

set CD="%~dp0"
cd %~dp0

python ttp_checker.py --interval 6