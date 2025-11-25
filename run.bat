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

:: --- Run Demo ---
echo Starting DepthAI Demo...
python depthai_demo.py --guiType qt --skipVersionCheck

if %errorlevel% neq 0 (
    echo.
    echo An error occurred while running the demo.
    pause
)
