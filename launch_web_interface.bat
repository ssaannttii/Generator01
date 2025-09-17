@echo off
REM Launch the HTML interface for the star chart generator
SETLOCAL
SET SCRIPT_DIR=%~dp0
CD /D "%SCRIPT_DIR%"

IF EXIST .venv\Scripts\python.exe (
    CALL .venv\Scripts\python.exe scripts\run_web_interface.py %*
) ELSE (
    python scripts\run_web_interface.py %*
)
