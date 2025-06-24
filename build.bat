@echo off
echo Building Regulens-AI with PyInstaller...
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

REM Build with PyInstaller
echo Building executable...
pyinstaller --clean regulens-ai.spec

REM Check if build was successful
if exist "dist\RegulensAI.exe" (
    echo.
    echo Build successful!
    echo Executable location: dist\RegulensAI.exe
    echo.
    echo You can now run the application by double-clicking RegulensAI.exe
) else (
    echo.
    echo Build failed! Please check the error messages above.
)

pause 