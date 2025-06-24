#!/bin/bash

echo "Building Regulens-AI with PyInstaller..."
echo

# Check if virtual environment exists
if [ ! -f "venv/bin/activate" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist build

# Build with PyInstaller
echo "Building executable..."
pyinstaller --clean regulens-ai.spec

# Check if build was successful
if [ -f "dist/RegulensAI" ]; then
    echo
    echo "Build successful!"
    echo "Executable location: dist/RegulensAI"
    echo
    echo "You can now run the application by executing: ./dist/RegulensAI"
else
    echo
    echo "Build failed! Please check the error messages above."
fi 