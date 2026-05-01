@echo off
set CD="%~dp0"
cd %~dp0

python dashboard.py --port 8787
