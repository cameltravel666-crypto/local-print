#!/bin/bash
# Build script for Linux
# Run this script on a Linux machine to build the Linux executable

echo "========================================"
echo "Local Print Agent - Linux Build"
echo "========================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

python3 --version

# Install system dependencies for PyQt6 on Linux
echo ""
echo "Note: PyQt6 requires certain system libraries."
echo "If the build fails, you may need to install:"
echo "  Ubuntu/Debian: sudo apt install libxcb-cursor0 libxkbcommon0"
echo "  Fedora/RHEL: sudo dnf install xcb-util-cursor libxkbcommon"
echo ""

# Create and activate virtual environment (optional but recommended)
# python3 -m venv venv
# source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller

# Build
echo ""
echo "Building Linux executable..."
python3 build.py

echo ""
echo "Build complete!"
echo "Output location: output/builds/linux/LocalPrintAgent"
