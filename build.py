#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build script for Local Print Agent
Creates platform-specific executables using PyInstaller
"""

import subprocess
import sys
import shutil
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
OUTPUT_DIR = PROJECT_ROOT / "output" / "builds"


def get_platform_name():
    """Get current platform name for output directory"""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform == "darwin":
        return "macos"
    return sys.platform


def check_pyinstaller():
    """Check if PyInstaller is installed"""
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("PyInstaller is not installed.")
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return True


def install_dependencies():
    """Install project dependencies"""
    requirements_file = PROJECT_ROOT / "requirements.txt"
    if requirements_file.exists():
        print("Installing dependencies...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ])


def build():
    """Build the application"""
    print(f"Building for platform: {get_platform_name()}")

    # Ensure PyInstaller is available
    check_pyinstaller()

    # Install dependencies
    install_dependencies()

    # Clean previous builds
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    # Run PyInstaller
    spec_file = PROJECT_ROOT / "local_print.spec"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file)
    ]

    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=PROJECT_ROOT)

    # Move output to platform-specific directory
    platform_dir = OUTPUT_DIR / get_platform_name()
    platform_dir.mkdir(parents=True, exist_ok=True)

    # Find built executable
    if sys.platform == "win32":
        exe_name = "LocalPrintAgent.exe"
    else:
        exe_name = "LocalPrintAgent"

    built_exe = DIST_DIR / exe_name

    if built_exe.exists():
        dest = platform_dir / exe_name
        if dest.exists():
            dest.unlink()
        shutil.copy2(built_exe, dest)
        print(f"\nBuild successful!")
        print(f"Output: {dest}")
    else:
        print(f"Error: Built executable not found at {built_exe}")
        sys.exit(1)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Build Local Print Agent")
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Only install dependencies without building"
    )

    args = parser.parse_args()

    if args.install_deps:
        install_dependencies()
    else:
        build()


if __name__ == "__main__":
    main()
