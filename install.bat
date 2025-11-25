@echo off
setlocal EnableDelayedExpansion

echo ==========================================
echo DepthAI Windows Installer
echo ==========================================

:: --- Configuration ---
set "PYTHON_VERSION=3.12.0"
set "PYTHON_INSTALLER=python-%PYTHON_VERSION%-amd64.exe"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_INSTALLER%"
set "VENV_DIR=.venv"

:: --- Check for Python 3.12 ---
echo Checking for Python 3.12...
py -3.12 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python 3.12 is already installed.
    set "PYTHON_CMD=py -3.12"
) else (
    python --version 2>nul | findstr "3.12" >nul
    if %errorlevel% equ 0 (
        echo Python 3.12 is available as 'python'.
        set "PYTHON_CMD=python"
    ) else (
        echo Python 3.12 not found.
        
        :: Check if installer exists locally
        if exist "%PYTHON_INSTALLER%" (
            echo Found local installer: %PYTHON_INSTALLER%
        ) else (
            echo Downloading Python %PYTHON_VERSION%...
            curl -o "%PYTHON_INSTALLER%" "%PYTHON_URL%"
            if %errorlevel% neq 0 (
                echo Failed to download Python installer. Please check your internet connection.
                pause
                exit /b 1
            )
        )

        echo Installing Python %PYTHON_VERSION%...
        echo Requesting administrative privileges...
        :: Install Python silently, add to PATH, install launcher
        "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
        
        if %errorlevel% neq 0 (
            echo Python installation failed. Please run this script as Administrator or install Python manually.
            pause
            exit /b 1
        )
        
        echo Python installed successfully.
        set "PYTHON_CMD=py -3.12"
    )
)

:: --- Create Virtual Environment ---
if not exist "%VENV_DIR%" (
    echo Creating virtual environment in %VENV_DIR%...
    %PYTHON_CMD% -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists.
)

:: --- Install Dependencies ---
echo Installing dependencies...
call "%VENV_DIR%\Scripts\activate.bat"

:: Upgrade pip
python -m pip install --upgrade pip

:: Install requirements
if exist "requirements.txt" (
    echo Installing requirements.txt...
    pip install -r requirements.txt
)

if exist "requirements-optional.txt" (
    echo Installing requirements-optional.txt...
    pip install -r requirements-optional.txt
)

echo.
echo ==========================================
echo Installation Complete!
echo You can now run the demo using 'run.bat'
echo ==========================================
pause
