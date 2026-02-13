# -*- mode: python ; coding: utf-8 -*-
# Usage:
#   pyinstaller gheval.spec --noconfirm                   (default: onefile)
#   pyinstaller gheval.spec --noconfirm -DONEDIR=1        (onedir mode)

import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None
onedir = os.environ.get('GHEVAL_ONEDIR', '0') == '1'

# Collect all PyQt6 components to avoid missing DLLs
qt6_datas, qt6_binaries, qt6_hiddenimports = collect_all('PyQt6')
qtwe_datas, qtwe_binaries, qtwe_hiddenimports = collect_all('PyQt6.QtWebEngineWidgets')

all_datas = qt6_datas + qtwe_datas + [
    ('templates', 'templates'),
    ('migrations', 'migrations'),
]
all_binaries = qt6_binaries + qtwe_binaries
all_hiddenimports = qt6_hiddenimports + qtwe_hiddenimports + [
    'peewee',
    'cv2',
    'numpy',
    'PyQt6.QtWebChannel',
    'PyQt6.sip',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if onedir:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='GHEval',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='GHEval',
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='GHEval',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
    )
