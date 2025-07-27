@echo off
REM ADOC Toolkit launcher script for Windows
REM This script starts the ADOC interactive toolkit

REM Change to the parent directory (project root)
cd /d "%~dp0\.."

REM Check if we're in the right directory (look for pyproject.toml)
if not exist "pyproject.toml" (
    echo Error: pyproject.toml not found
    echo Please run this script from the adoc-toolkit root directory
    pause
    exit /b 1
)

REM Function to run with uv
:run_with_uv
echo Using uv to run ADOC Toolkit...
uv run adoc-toolkit %*
goto :eof

REM Function to run without uv (fallback)
:run_without_uv
echo uv not found, trying to run without uv...

REM Check if Python is available
python --version >nul 2>nul
if %errorlevel% neq 0 (
    python3 --version >nul 2>nul
    if %errorlevel% neq 0 (
        echo Error: Neither uv nor Python found
        echo Please install either uv (recommended) or Python
        echo uv: https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=python3
    )
) else (
    set PYTHON_CMD=python
)

echo Using %PYTHON_CMD% to run ADOC Toolkit...

REM Try to run directly from the module
if exist "adoc_toolkit" (
    %PYTHON_CMD% -m adoc_toolkit %*
) else (
    echo Error: adoc_toolkit module not found
    echo Please ensure the project is properly installed or use uv
    pause
    exit /b 1
)
goto :eof

REM Check if uv is available
where uv >nul 2>nul
if %errorlevel% equ 0 (
    REM Install dependencies if needed
    if not exist ".venv" (
        echo Installing dependencies with uv...
        uv sync
        if %errorlevel% neq 0 (
            echo Error: Failed to install dependencies with uv
            echo Falling back to direct Python execution...
            call :run_without_uv
            exit /b %errorlevel%
        )
    )
    call :run_with_uv
) else (
    echo uv not found, using fallback method...
    call :run_without_uv
)