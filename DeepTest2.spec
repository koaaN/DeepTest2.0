# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path


if sys.platform == 'win32':
    platform_backend = 'webview.platforms.edgechromium'
elif sys.platform == 'darwin':
    platform_backend = 'webview.platforms.cocoa'
else:
    platform_backend = 'webview.platforms.qt'

datas = [
    ('android-helper/assets/OP15', 'android-helper/assets/OP15'),
    ('android-helper/assets/ACE6T', 'android-helper/assets/ACE6T'),
    ('android-helper/assets/15T', 'android-helper/assets/15T'),
    ('src/deeptesting/assets', 'deeptesting/assets'),
    ('src/deeptesting/web', 'deeptesting/web'),
]

if Path('platform-tools').is_dir():
    datas.append(('platform-tools', 'platform-tools'))


a = Analysis(
    ['launcher.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=['webview', platform_backend],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DeepTest2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DeepTest2',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='DeepTest2.app',
        icon=None,
        bundle_identifier='com.koaan.deeptest2',
        info_plist={
            'CFBundleName': 'DeepTest 2.0',
            'CFBundleDisplayName': 'DeepTest 2.0',
            'NSHighResolutionCapable': True,
        },
    )
