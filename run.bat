@echo off
setlocal

set "VENV_DIR=.venv"

:: --- Check if Virtual Environment Exists ---
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Virtual environment not found!
    echo Please run 'install.bat' first.
    pause
    exit /b 1
)

:: --- Activate Virtual Environment ---
call "%VENV_DIR%\Scripts\activate.bat"

:: --- Configure FFmpeg Path ---
:: Ensure .venv\Scripts is in PATH (activate.bat should do this, but we force it to be sure)
set "PATH=%~dp0%VENV_DIR%\Scripts;%PATH%"

:: Verify FFmpeg existence
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: ffmpeg.exe not found in PATH!
    echo Video recording will fail.
    echo Please ensure 'install.bat' completed successfully.
    if exist "%VENV_DIR%\Scripts\ffmpeg.exe" (
        echo Found ffmpeg.exe in %VENV_DIR%\Scripts, but it was not in PATH.
        echo Attempting to fix PATH...
        set "PATH=%CD%\%VENV_DIR%\Scripts;%PATH%"
    )
) else (
    echo FFmpeg found in PATH.
)

:: --- Run Demo ---
echo Starting DepthAI Demo...
python depthai_demo.py --guiType qt --skipVersionCheck

if %errorlevel% neq 0 (
    echo.
    echo An error occurred while running the demo.
    pause
)
