# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Local Print Agent
Supports Windows and Linux builds
"""

import sys
from pathlib import Path

block_cipher = None

# Determine platform-specific settings
is_windows = sys.platform == 'win32'
is_linux = sys.platform.startswith('linux')

# Application name
app_name = 'LocalPrintAgent'
if is_windows:
    app_name += '.exe'

# Hidden imports for PyQt6 and other dependencies
hidden_imports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtWidgets',
    'PyQt6.QtGui',
    'websocket',
    'requests',
    'certifi',
    'PIL',
    'PIL.Image',
    'psutil',
    'cryptography',
    'dotenv',
    'colorlog',
    'src',
    'src.core',
    'src.core.odoo_client',
    'src.core.printer_manager',
    'src.core.print_service',
    'src.core.websocket_client',
    'src.utils',
    'src.utils.config',
    'src.utils.escpos_parser',
    'src.gui',
    'src.gui.main_window',
]

# Windows-specific imports
if is_windows:
    hidden_imports.extend([
        'win32print',
        'win32api',
        'win32con',
    ])

# Data files - only include resources if directory has content
datas = []
resources_dir = Path('resources')
if resources_dir.exists() and any(resources_dir.iterdir()):
    datas.append(('resources', 'resources'))

# Include certifi CA bundle for SSL in packaged builds
import certifi
datas.append((certifi.where(), 'certifi'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=app_name.replace('.exe', ''),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico' if is_windows and Path('resources/icon.ico').exists() else None,
)
