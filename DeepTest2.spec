# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path


platform_backend = (
    'webview.platforms.edgechromium'
    if os.name == 'nt'
    else 'webview.platforms.gtk'
)

datas = [
    ('android-helper/assets/OP15', 'android-helper/assets/OP15'),
    ('android-helper/assets/ACE6T', 'android-helper/assets/ACE6T'),
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
