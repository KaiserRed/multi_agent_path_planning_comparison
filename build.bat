@echo off
REM Build a single-file Windows .exe with PyInstaller.
REM
REM Usage:
REM   build.bat           -- release build
REM   build.bat --debug   -- keep console + debug output
REM
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "VENV_PYTHON=.venv\Scripts\python.exe"
set "PYINSTALLER=.venv\Scripts\pyinstaller.exe"

if not exist "%VENV_PYTHON%" (
    echo ERROR: virtual environment not found at .venv\
    echo   Run:  uv sync
    exit /b 1
)

if not exist "%PYINSTALLER%" (
    echo ERROR: pyinstaller not found in .venv\
    echo   Run:  uv add --dev pyinstaller
    exit /b 1
)

set "DEBUG_FLAG="
if "%~1"=="--debug" (
    set "DEBUG_FLAG=--debug=all"
    echo Building in DEBUG mode ...
) else (
    echo Building release .exe ...
)

"%PYINSTALLER%" mrse.spec ^
    --distpath dist\windows ^
    --workpath build\windows ^
    --noconfirm ^
    %DEBUG_FLAG%

if %ERRORLEVEL% neq 0 (
    echo.
    echo BUILD FAILED ^(exit code %ERRORLEVEL%^)
    exit /b %ERRORLEVEL%
)

echo.
echo Done!  Executable: dist\windows\mrse.exe
