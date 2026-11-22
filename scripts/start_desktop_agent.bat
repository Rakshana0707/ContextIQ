@echo off
title ContextIQ Desktop Behavioral Activity Collector
echo ========================================================
echo        ContextIQ Windows Desktop Behavioral Agent
echo ========================================================
echo.

set AGENT_DIR=%~dp0..\desktop-agent
cd /d "%AGENT_DIR%"

if exist "..\backend\.venv\Scripts\python.exe" (
    set PYTHON_EXE=..\backend\.venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python
)

echo Using Python runtime: %PYTHON_EXE%
echo Launching Desktop Agent...
echo.

"%PYTHON_EXE%" app\main.py %*
