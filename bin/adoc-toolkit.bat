@echo off
REM ADOC Toolkit launcher script for Windows
REM This script starts the ADOC interactive toolkit

REM Change to the parent directory (project root)
cd /d "%~dp0\.."

REM Check if uv is available
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: uv is not installed or not in PATH
    echo Please install uv: https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

REM Check if we're in the right directory (look for pyproject.toml)
if not exist "pyproject.toml" (
    echo Error: pyproject.toml not found
    echo Please run this script from the adoc-toolkit root directory
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist ".venv" (
    echo Installing dependencies...
    uv sync
    if %errorlevel% neq 0 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Start the ADOC toolkit
uv run adoc-toolkit %*