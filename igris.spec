# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Igris AI Assistant
Builds standalone executables for all platforms.
"""

import sys
import os
from pathlib import Path

# Determine platform
PLATFORM = sys.platform
IS_WINDOWS = PLATFORM == 'win32'
IS_MACOS = PLATFORM == 'darwin'
IS_LINUX = PLATFORM.startswith('linux')

# Project paths
PROJECT_ROOT = Path(SPECPATH).resolve()
CORE_PATH = PROJECT_ROOT / 'core'
CLI_PATH = PROJECT_ROOT / 'cli'
CONFIG_PATH = PROJECT_ROOT / 'config'

# Entry point
ENTRY_POINT = str(CLI_PATH / 'igris_cli.py')

# Data files to include
datas = [
    (str(CONFIG_PATH / 'settings.example.yaml'), 'config'),
    (str(CONFIG_PATH / 'voice_commands.yaml'), 'config'),
    (str(CONFIG_PATH / 'nl_prompts.yaml'), 'config'),
    (str(CONFIG_PATH / 'approval_rules.yaml'), 'config'),
    (str(PROJECT_ROOT / 'docs' / 'USER_MANUAL.md'), 'docs'),
]

# Hidden imports (modules not detected automatically)
hiddenimports = [
    'core.secure_execution',
    'core.secrets_manager',
    'core.secure_auth',
    'core.input_validation',
    'core.approval_workflow',
    'core.voice_input',
    'core.nl_parser',
    'core.predictive_engine',
    'core.api_server',
    'core.api_auth',
    'core.secure_audit',
    'core.platform_linux',
    'core.platform_macos',
    'argon2',
    'argon2.low_level',
    'keyring',
    'keyring.backends',
    'yaml',
    'psutil',
]

# Platform-specific hidden imports
if IS_WINDOWS:
    hiddenimports.extend([
        'win32api',
        'win32con',
        'win32cred',
        'winrt',
    ])
elif IS_MACOS:
    hiddenimports.extend([
        'keyring.backends.macOS',
        'Foundation',
        'LocalAuthentication',
    ])
elif IS_LINUX:
    hiddenimports.extend([
        'keyring.backends.SecretService',
        'secretstorage',
        'dbus',
    ])

# Exclude unnecessary modules
excludes = [
    'tkinter',
    'matplotlib',
    'numpy',
    'scipy',
    'pandas',
    'PIL',
    'cv2',
]

# Analysis
a = Analysis(
    [ENTRY_POINT],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# Remove unnecessary files
a.binaries = [x for x in a.binaries if not x[0].startswith('libQt')]
a.binaries = [x for x in a.binaries if 'tcl' not in x[0].lower()]
a.binaries = [x for x in a.binaries if 'tk' not in x[0].lower()]

# PYZ archive
pyz = PYZ(a.pure, a.zipped_data)

# Executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='igris',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / 'assets' / 'icon.ico') if IS_WINDOWS else None,
)

# Collect all files
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='igris',
)

# macOS app bundle (optional)
if IS_MACOS:
    app = BUNDLE(
        coll,
        name='Igris.app',
        icon=str(PROJECT_ROOT / 'assets' / 'icon.icns'),
        bundle_identifier='com.igris.assistant',
        info_plist={
            'CFBundleName': 'Igris',
            'CFBundleDisplayName': 'Igris AI Assistant',
            'CFBundleVersion': '2.0.0',
            'CFBundleShortVersionString': '2.0.0',
            'NSHighResolutionCapable': True,
            'NSMicrophoneUsageDescription': 'Igris needs microphone access for voice commands.',
        },
    )
