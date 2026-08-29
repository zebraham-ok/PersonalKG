@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="" (
    python -X utf8 kb_ctl.py help
    echo.
    pause
) else (
    python -X utf8 kb_ctl.py %*
)
