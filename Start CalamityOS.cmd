@echo off
setlocal
cd /d "%~dp0"
if exist "runtime\python.exe" (
    "runtime\python.exe" tasks.py ui --port 0 --open
) else (
    python tasks.py ui --port 0 --open
)
if errorlevel 1 pause
