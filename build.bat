@echo off
setlocal

echo ========================================
echo  GHEval Build Script (Windows)
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ first.
    pause
    exit /b 1
)

:: Check/install dependencies
echo [1/3] Checking dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Clean previous build
echo [2/3] Cleaning previous build...
if exist dist\GHEval.exe del /f dist\GHEval.exe
if exist build\gheval rmdir /s /q build\gheval

:: Build
echo [3/3] Building GHEval.exe ...
pyinstaller gheval.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Build complete!
echo  Output: dist\GHEval.exe
echo ========================================
dir dist\GHEval.exe
echo.
pause
