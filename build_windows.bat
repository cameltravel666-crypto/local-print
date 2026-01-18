@echo off
REM Build script for Windows
REM Run this script on a Windows machine to build the Windows executable

echo ========================================
echo Local Print Agent - Windows Build
echo ========================================

REM Check Python
python --version 2>NUL
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Install dependencies
echo.
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

REM Build
echo.
echo Building Windows executable...
python build.py

echo.
echo Build complete!
echo Output location: output\builds\windows\LocalPrintAgent.exe
pause
